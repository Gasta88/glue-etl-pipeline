import json
import boto3
import logging
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


def get_run_properties():
    """Return enhanced job properties.

    :return config: dictionary with properties used in flat_dvaults Glue Job."""
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
    config["MEDIA_BUCKETNAME"] = run_properties["media_bucketname"]
    s3 = boto3.resource("s3", region_name="us-east-1")
    config["BUCKET"] = s3.Bucket(config["LANDING_BUCKETNAME"])
    media_bucket = s3.Bucket(config["MEDIA_BUCKETNAME"])
    config["ALL_MEDIAS"] = [obj.key for obj in list(media_bucket.objects.all())]
    config["DVAULT_FILES"] = [
        obj.key
        for obj in list(config["BUCKET"].objects.filter(Prefix="data/clean_dvaults"))
    ]
    return config


def _recast_score_to_float(el, service_name):
    """
    Cast score attribute as FLOAT because missing scores are labelled as INT64 (-1).

    :param el: dictionary that represent the event.
    :param service_name: element service name (only SUMMARIZER is accepted).
    """
    if service_name == "summarizer":
        for i, sentence_score in enumerate(
            el["detail"]["prediction"]["input"]["sentences_scores"]
        ):
            if type(sentence_score["score"]) is int:
                el["detail"]["prediction"]["input"]["sentences_scores"][i][
                    "score"
                ] = float(sentence_score["score"])
    return el


def _recast_paragraph_to_str(el, service_name):
    """
    Cast to STRING the paragraph attribute in SUMMARIZER EVENTS from INT64.
    This is due to the presence of "null" values that account for STRING data type event
    if the majority of the values are numeric.

    :param el: dictionary that represent the event.
    :param service_name: element service name (only SUMMARIZER is accepted).
    :return el: corrected element, if criterias are satisfied.
    """
    if service_name == "summarizer":
        # Skip over DELETE type events since they do not have a payload attribute.
        if el["detail"]["evaluation"]["type"] != "DELETE":
            paragraph = el["detail"]["evaluation"]["payload"].get("paragraph", None)
            if type(paragraph) is int:
                el["detail"]["evaluation"]["payload"]["paragraph"] = str(paragraph)
    return el


def _convert_query_and_tags(el, service_name):
    """
    Convert query and tags attribute in STE EVENTS from string to list for all types.

    :param el: dictionary that represent the event.
    :param service_name: element service name (only STE is accepted).
    :return el: corrected element, if criterias are satisfied.
    """
    if service_name == "ste":
        query = el["detail"]["evaluation"]["payload"].get("query", None)
        if type(query) is str:
            if query == "null":
                # query can be nullable, even if it's stated otherwise in the docs
                el["detail"]["evaluation"]["payload"]["query"] = []
            else:
                el["detail"]["evaluation"]["payload"]["query"] = [query]
        tags = el["detail"]["evaluation"]["payload"].get("tags", None)
        if type(tags) is str:
            if tags == "null":
                # tags can be nullable
                el["detail"]["evaluation"]["payload"]["tags"] = []
            else:
                el["detail"]["evaluation"]["payload"]["tags"] = [tags]
    return el


def _replace_image_uri(el, service_name, media_bucketname, all_medias):
    """
    Replace media_id attribute for STE EVENTS only to the S3 URI.

    :param el: dictionary that represent the event.
    :param service_name: element service name (only STE is accepted).
    :param media_bucketname: string that define the S3 bucket with Shape media.
    :param al_medias: list of keys inside the S3 Shape media bucket.
    :return el: corrected element, if criterias are satisfied.
    """
    if service_name == "ste":
        # Skip over ADD_TAG type events since they do not have a media_id attribute.
        if el["detail"]["evaluation"]["type"] != "ADD_TAG":
            media_id_value = el["detail"]["evaluation"]["payload"]["media_id"]
            media_lib_value = el["detail"]["evaluation"]["payload"]["medialib"]
            media_lookup_value = f"{media_lib_value}/{media_id_value}"
            media_uri_value = [
                f"s3://{media_bucketname}/{key}"
                for key in all_medias
                if media_lookup_value in key
            ]
            if media_uri_value == []:
                logger.warn(f"No media with id {media_id_value} found in media bucket.")
                media_uri_value = [media_id_value]
            if len(media_uri_value) > 1:
                logger.info(
                    f"Multiple media with id {media_id_value} found: {len(media_uri_value)}"
                )
            el["detail"]["evaluation"]["payload"]["media_id"] = media_uri_value[0]
    return el


def _get_service_name(el):
    """
    Retrieve service name from dvault file.

    :param el: dictionary that represent the event.
    :return service_name: string that reresent the dvaut file service name.
    """
    service_name = None
    if el["detail"]["type"] == "DVaultPredictionEvent":
        service_name = el["detail"]["prediction"]["service"]
    if el["detail"]["type"] == "DVaultEvaluationEvent":
        service_name = el["detail"]["evaluation"].get("service", None)
        if service_name is None:
            # old style EVENT dvault files
            service_name = el["detail"]["evaluation"]["prediction_id"].split("#")[-1]
    return service_name


def split_files(tmp_filename):
    """
    Divide Firehose Kinesis file in PREDICTIONS and EVENTS files.
    Label the dedicated service name in the file name.

    :param tmp_filename: location of the tmp file where object content is stored.
    :return predictions_arr: list of JSON predictions extracted from the file
    :return events_arr: list of JSON events extracted from the file
    """
    predictions_arr = {"summarizer": [], "headline": [], "ste": []}
    events_arr = {"summarizer": [], "headline": [], "ste": []}
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
            flat_el = json.loads(el)
            service_name = _get_service_name(flat_el)
            if flat_el["detail"]["type"] == "DVaultPredictionEvent":
                predictions_arr[service_name].append(flat_el)
            elif flat_el["detail"]["type"] == "DVaultEvaluationEvent":
                events_arr[service_name].append(flat_el)
            else:
                e = f'Unrecognized event type inside file: {flat_el["detail"]["type"]}'
                logger.error(e)
                sys.exit(1)
        except Exception as e:
            logger.error(e)
            sys.exit(1)
    return (predictions_arr, events_arr)


def save_flat_json(el_dict, el_type, file_name, landing_bucketname):
    """
    Get list of dictionaries and store them to the respective S3 prefix.

    :param el_dict: dictionary made of arrays of dictionaries.
    :param el_type: either EVENTS or PREDICTIONS.
    :param file_name: dvault file name.
    :param landing_bucketname: string that refer t S3 bucket where file is going to be saved.
    """
    s3 = boto3.resource("s3", region_name="us-east-1")
    for service_name, elements in el_dict.items():
        logger.info(f"There are {len(elements)} items for {service_name}.")
        if len(elements) > 0:
            tmp_key = f"/tmp/{file_name}_{service_name.upper()}.jsonl"
            output_key = (
                f"data/flat_jsons/{el_type}/{file_name}_{service_name.upper()}.jsonl"
            )
            obj = s3.Object(landing_bucketname, output_key)
            with open(tmp_key, "wb") as outfile:
                for el in elements:
                    outfile.write(json.dumps(el).encode())
                    outfile.write("\n".encode())
            obj.put(Body=open(tmp_key, "rb"))
        else:
            logger.warn(f"No {el_type} extracted from file.")
    return


def main():
    """
    Run main steps in the flat_dvaults Glue Job.
    """
    run_props = get_run_properties()
    tmp_filename = "/tmp/tmp_file"
    for obj_key in run_props["DVAULT_FILES"]:
        logger.info(f"Splitting file {obj_key}.")
        file_name = obj_key.split("/")[-1]
        obj = run_props["BUCKET"].Object(obj_key)
        obj.download_file(tmp_filename)

        try:
            predictions_arr, events_arr = split_files(tmp_filename)
            logger.info(
                f"Extracted {len(predictions_arr)} prediction elements from file."
            )
            logger.info(f"Extracted {len(events_arr)} event elements from file.")

            logger.info("Correcting predictions elements.")
            corrected_predictions_arr = {}
            for service_name, elements in predictions_arr.items():
                corrected_predictions_arr[service_name] = [
                    _recast_score_to_float(el, service_name) for el in elements
                ]

            logger.info("Correcting events elements.")
            corrected_events_arr = {}
            for service_name, elements in events_arr.items():
                new_elements = []
                for el in elements:
                    new_el_0 = _replace_image_uri(
                        el,
                        service_name,
                        run_props["MEDIA_BUCKETNAME"],
                        run_props["ALL_MEDIAS"],
                    )
                    new_el_1 = _convert_query_and_tags(new_el_0, service_name)
                    new_el_2 = _recast_paragraph_to_str(new_el_1, service_name)
                    new_elements.append(new_el_2)
                corrected_events_arr[service_name] = new_elements

        except Exception as e:
            logger.error(
                "Something wrong with extraction of prediction/event from file. Process stopped."
            )
            sys.exit(1)

        save_flat_json(
            corrected_predictions_arr,
            "predictions",
            file_name,
            run_props["LANDING_BUCKETNAME"],
        )
        save_flat_json(
            corrected_events_arr, "events", file_name, run_props["LANDING_BUCKETNAME"]
        )


if __name__ == "__main__":
    main()
