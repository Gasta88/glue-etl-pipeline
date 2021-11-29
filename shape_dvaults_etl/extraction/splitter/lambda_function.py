import boto3
from botocore.client import BaseClient
import urllib
import json
from logging import getLogger
from typing import Union, Optional
from doceboai_commons.exceptions import ExecutionTimeLimit
from doceboai_commons.logging import LogConfigLoader, LogContext, AdditionalData
from doceboai_commons.util.aws_lambda import LambdaUtils, LambdaResponse


LogConfigLoader.load()
logger = getLogger(__name__)


def flatten_data(y: str) -> dict:
    """
    Flatten highly nested JSON structure into a 1-level.

    :param y: JSON string to format
    """
    out = {}

    def flatten(x: Union[list, dict], name: str = "") -> dict:
        """
        Helping function inside flatten_data() main function. Handles dict and list to
        explode the JSON structure.

        :param x: dict or list fromthe JSON
        :param name: attribute name for different levels
        :return out: flat JSON dictionary
        """
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


def split_files(bucket, obj_key: str) -> tuple:
    logger.debug(
        f"File {obj_key} in bucket {bucket.name} is been initialized for process..."
    )
    predictions_arr: list = []
    events_arr: list = []
    content: list = []
    obj = bucket.Object(obj_key)
    obj.download_file("/tmp/tmp_file")
    logger.debug("File has been downloaded into /tmp...")
    with open("/tmp/tmp_file") as f:
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
            flat_el: dict = flatten_data(json.loads(el))
            if flat_el["detail-type"] == "DVaultPredictionEvent":
                predictions_arr.append(flat_el)
            elif flat_el["detail-type"] == "DVaultEvaluationEvent":
                events_arr.append(flat_el)
            else:
                e = f'Unrecognized event type inside file: {flat_el["detail-type"]}'
                logger.exception(
                    e,
                    extra=AdditionalData(event=el),
                )
                raise e
        except Exception as e:
            logger.exception(
                f"Unable to flatten the JSON structure.",
                extra=AdditionalData(event=el),
            )
            raise e
    return (predictions_arr, events_arr)


@LogContext(context_id_generator=LambdaUtils.generate_log_id)
def lambda_handler(event, context):  # noqa
    response: Optional[LambdaResponse] = None
    try:
        with ExecutionTimeLimit.from_lambda_context(context, offset=5):
            s3: BaseClient = boto3.client("s3", region_name="us-east-1")
            bucket = s3.Bucket(event["Records"][0]["s3"]["bucket"]["name"])
            key: str = urllib.parse.unquote_plus(
                event["Records"][0]["s3"]["object"]["key"], encoding="utf-8"
            )
            file_name: str = key.split("/")[-1]
            predictions_filename: str = f"{file_name}_PRED.json"
            predictions_targetkey: str = f"/splitted-files/{predictions_filename}"
            events_filename: str = f"{file_name}_EVENTS.json"
            events_targetkey: str = f"/splitted-files/{events_filename}"

            predictions_arr, events_arr = split_files(bucket, key)
            with open(f"/tmp/{predictions_filename}", "wb") as f:
                json.dumps(predictions_arr, f)
            with open(f"/tmp/{events_filename}", "wb") as f:
                json.dumps(events_arr, f)

            s3.meta.client.upload_file(
                f"/tmp/{predictions_filename}", "/splitted_files", predictions_targetkey
            )
            s3.meta.client.upload_file(
                f"/tmp/{events_filename}", "/splitted_files", events_targetkey
            )
            response = LambdaResponse(200, {})
    except Exception as e:  # noqa
        response = LambdaResponse.from_error(e)
        logger.exception(
            "An error occurred during lambda handler processing (Split Firehose Kinesis files)",
            extra=AdditionalData(event=event),
        )
