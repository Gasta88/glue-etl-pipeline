import json
import boto3
import logging
from awsglue.utils import getResolvedOptions
import sys

# Setup logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Get run properties for the Glue workflow.")
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

# Job parameters
LANDING_BUCKETNAME = run_properties["landing_bucketname"]
s3 = boto3.resource("s3", region_name="us-east-1")
BUCKET = s3.Bucket(LANDING_BUCKETNAME)
DVAULT_PREFIX = {
    "dirty": "data/dirty_dvaults",
    "clean": "data/clean_dvaults",
}
DVAULT_FILES = run_properties["dvault_files"].split(";")


def flatten_data(y):
    """
    Flatten nested dictionary into a linear schema.

    :param y: nested JSON data.
    :return out: linear JSON data.
    """
    out = {}

    def flatten(x, name=""):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + "_")
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + "_")
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out


def split_files(tmp_filename):
    """
    Split agglomerated dvault from Firehose Kinesis.

    :param tmp_filename: dvault filename to process.
    :return data_arr: list of dictionaries representing dvault elements.
    """
    data_arr = []
    content = []
    with open(tmp_filename) as f:
        content = f.readlines()
    content = content[0].replace('}{"version"', '}${"version"')
    for el in content.split("}}$"):
        # remove Luca's legacy tests
        if "hello from vcoach" in el:
            continue
        # last element in array already have "}}". No need to attach it.
        if el[-2:] != "}}":
            el = el + "}}"
        try:
            data_arr.append(json.loads(el))
        except Exception as e:
            logger.error(e)
            sys.exit(0)
    return data_arr


def save_dvaults(el_list, el_type, file_name):
    """
    Save onto the correct prefix the dvault profiled.

    :param el_list: list of dvaults profiled.
    :param el_type: either dirty or clean dvaults.
    :param file_name: name of the dvault file.
    """
    if len(el_list) > 0:
        logger.info(f"There are {len(el_list)} {el_type.upper()} elements.")
        tmp_key = f"/tmp/{file_name}_{el_type.upper()}"
        output_key = f"{DVAULT_PREFIX.get(el_type)}/{file_name}_{el_type.upper()}"
        obj = s3.Object(LANDING_BUCKETNAME, output_key)
        with open(tmp_key, "wb") as outfile:
            outfile.write("".join(el_list).encode())
        obj.put(Body=open(tmp_key, "rb"))
    else:
        logger.warn(f"No {el_type.upper()} extracted from file.")
    return


# Main instructions for the Glue Job
for obj_key in DVAULT_FILES:
    logger.info(f"Profiling file {obj_key}.")
    file_name = obj_key.split("/")[-1]
    tmp_filename = "/tmp/tmp_file"
    obj = BUCKET.Object(obj_key)
    obj.download_file(tmp_filename)

    try:
        events_arr = split_files(tmp_filename)
        dirty_dvaults = []
        clean_dvaults = []
        for p, event in enumerate(events_arr):
            dvault_type = (
                "event"
                if event["detail"]["type"] == "DVaultEvaluationEvent"
                else "prediction"
            )
            if dvault_type == "event":
                # new feature added to EVENT dvault files
                service_name = event["detail"]["evaluation"].get("service", None)
                if service_name is None:
                    # old style EVENT dvault files
                    if (event["detail"]["evaluation"]["prediction_id"] is None) or (
                        "#" not in event["detail"]["evaluation"]["prediction_id"]
                    ):
                        # if dvault file does not have a reference to the service, then it can't be processed
                        service_name = "na"
                    else:
                        service_name = event["detail"]["evaluation"][
                            "prediction_id"
                        ].split("#")[-1]
            else:
                service_name = event["detail"]["prediction"]["service"]
            if service_name == "na":
                dirty_dvaults.append(json.dumps(event))
            else:
                clean_dvaults.append(json.dumps(event))
            # TODO: define profiling strategy here
            # suite = get_expectation_suite(event, service_name, dvault_type)
            # if suite:
            #     failures =[k for k,v in suite.items() if not(v.success)]
            #     if len(failures) > 0:
            #         for f in failures:
            #             print(f'Event {event["detail"]["id"]} at position {p} failed check "{f}"')
            #         dirty_dvaults.append(json.dumps(event))
            # else:
            #     dirty_dvaults.append(json.dumps(event))
            # clean_dvaults.append(json.dumps(event))
    except Exception as e:
        logger.error(
            "Something wrong with extraction of dvaults from file. Process stopped."
        )
        sys.exit(0)
    save_dvaults(clean_dvaults, "clean", file_name)
    save_dvaults(dirty_dvaults, "dirty", file_name)
