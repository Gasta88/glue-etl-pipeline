import json
import boto3
import logging
import sys
from cerberus import Validator
import s3fs

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Get run properties for the Glue workflow.")


def get_run_properties():
    """Return enhanced job properties.

    :return config: dictionary with properties used in flat_efs Glue Job."""
    from awsglue.utils import getResolvedOptions

    config = {}
    args = getResolvedOptions(
        sys.argv,
        ["WORKFLOW_NAME", "WORKFLOW_RUN_ID"],
    )
    workflow_name = args["WORKFLOW_NAME"]
    workflow_run_id = args["WORKFLOW_RUN_ID"]
    glue = boto3.client("glue")
    run_properties = glue.get_workflow_run_properties(
        Name=workflow_name, RunId=workflow_run_id
    )["RunProperties"]
    config["LANDING_BUCKETNAME"] = run_properties["landing_bucketname"]
    config["EF_PREFIX"] = {
        "dirty": "data/dirty_efs",
        "clean": "data/clean_efs",
    }
    config["EVENT_FILES"] = run_properties["event_files"].split(";")
    return config


def run_data_profiling(event, validator_schema):
    """Perform data profiling with Cerberus package.

    :param event: nested dictionary representation of the dvault.
    :param validator_schema: JSON schema to be use to validate dvault.
    :return bool: data profiling flag when is successful/unsuccessful.
    :return errors: dictionaries of exceptions encoutered in the profiling.
    """
    v = Validator(validator_schema, allow_unknown=True)
    flag = v.validate(event)
    if not flag:
        return (flag, v.errors)
    return (flag, {})


def _get_service_name_and_type(el):
    """
    Retrieve service name from dvault file.

    :param el: dictionary that represent the event.
    :return service_name: string that reresent the dvaut file service name.
    :return service_type: string for EVENT or PREDICTION.
    """
    service_name = None
    if el["detail"]["type"] == "EFPredictionEvent":
        service_name = el["detail"]["prediction"]["service"]
        service_type = "prediction"
    if el["detail"]["type"] == "EFEvaluationEvent":
        service_name = el["detail"]["evaluation"].get("service", None)
        if service_name is None:
            # old style EVENT dvault files
            if (el["detail"]["evaluation"]["prediction_id"] is None) or (
                "#" not in el["detail"]["evaluation"]["prediction_id"]
            ):
                # if dvault file does not have a reference to the service, then it can't be processed
                service_name = None
            else:
                service_name = el["detail"]["evaluation"]["prediction_id"].split("#")[
                    -1
                ]
        service_type = "event"
    return (service_name, service_type)


def split_files(file_content):
    """
    Split agglomerated dvault from Firehose Kinesis.

    :param file_content: dvault file content.
    :return data_arr: list of dictionaries representing dvault elements.
    """
    decoder = json.JSONDecoder()
    data_arr = []
    content_length = len(file_content)
    decode_index = 0

    while decode_index < content_length:
        try:
            obj, decode_index = decoder.raw_decode(file_content, decode_index)
            data_arr.append(obj)
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError: {e}")
            # Scan forward and keep trying to decode
            decode_index += 1
    return data_arr


def save_efs(el_list, el_type, file_name, ef_prefix, landing_bucketname):
    """
    Save onto the correct prefix the dvault profiled.

    :param el_list: list of dvaults profiled.
    :param el_type: either dirty or clean dvaults.
    :param file_name: name of the dvault file.
    """
    if len(el_list) > 0:
        s3 = boto3.resource("s3")
        logger.info(f"There are {len(el_list)} {el_type.upper()} elements.")
        tmp_key = f"/tmp/{file_name}_{el_type.upper()}"
        output_key = f"{ef_prefix.get(el_type)}/{file_name}_{el_type.upper()}"
        obj = s3.Object(landing_bucketname, output_key)
        with open(tmp_key, "wb") as outfile:
            outfile.write("".join(el_list).encode())
        obj.put(Body=open(tmp_key, "rb"))
    else:
        logger.warn(f"No {el_type.upper()} extracted from file.")
    return


def main():
    """
    Run main steps in the data_profiling Glue Job.
    """
    run_props = get_run_properties()
    s3 = s3fs.S3FileSystem()
    validator_schemas = [
        f"s3://{f}"
        for f in s3.glob(f's3://{run_props["LANDING_BUCKETNAME"]}/dependencies/*.json')
    ]
    for obj_key in run_props["EVENT_FILES"]:
        logger.info(f"Profiling file {obj_key}.")
        file_name = obj_key.split("/")[-1]
        file_content = s3.cat_file(f"s3://{obj_key}").decode("utf-8")

        events_arr = split_files(file_content)
        dirty_efs = []
        clean_efs = []
        for event in events_arr:
            dvault_source = event.get("source", "")
            if dvault_source.lower() != "app.event.file":
                logger.info("Discard event unrelated to Shape.")
                continue
            else:
                try:
                    service_name, service_type = _get_service_name_and_type(event)
                    schema_files = [
                        s
                        for s in validator_schemas
                        if f"{service_name}_{service_type}.json" in s
                    ]
                    if len(schema_files) > 1:
                        logger.error(
                            f"Multiple schema files found for {service_name}_{service_type}"
                        )
                        sys.exit(1)
                    else:
                        validator_schema = json.loads(
                            s3.cat_file(schema_files[0]).decode("utf-8")
                        )
                    profile_flag, errors = run_data_profiling(event, validator_schema)
                    if (service_name is None) or not (profile_flag):
                        dirty_efs.append(json.dumps(event))
                    else:
                        clean_efs.append(json.dumps(event))
                    info_msg = (
                        f"PROFILER - "
                        f'EventId:{event["id"]}|'
                        f"HasPassed:{profile_flag}|"
                        f"EventFile:{file_name}|"
                        f"ServiceName:{service_name}|"
                        f"ServiceType:{service_type}|"
                        f"Errors:{json.dumps(errors)}"
                    )
                    logger.info(info_msg)
                except Exception as e:
                    # Luca's tests or completelly unrelated files might be stored in S3 bucket. Skip them.
                    logger.warn("Unable to process event file. Skipped.")
                    info_msg = (
                        f"PROFILER - "
                        f'EventId:{event["id"] if "id" in event else None}|'
                        f"HasPassed:{False}|"
                        f"EventFile:{file_name}|"
                        f"ServiceName:{None}|"
                        f"ServiceType:{None}|"
                        f"Errors:{e}"
                    )
                    logger.info(info_msg)
        save_efs(
            clean_efs,
            "clean",
            file_name,
            run_props["EF_PREFIX"],
            run_props["LANDING_BUCKETNAME"],
        )
        save_efs(
            dirty_efs,
            "dirty",
            file_name,
            run_props["EF_PREFIX"],
            run_props["LANDING_BUCKETNAME"],
        )


if __name__ == "__main__":
    main()
