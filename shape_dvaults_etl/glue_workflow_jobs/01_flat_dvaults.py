import json
import boto3
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.job import Job
import sys

args = getResolvedOptions(sys.argv, ["JOB_NAME", "landing_bucketname"])
landing_bucketname = args["landing_bucketname"]
sc = SparkContext()
glueContext = GlueContext(sc)
logger = glueContext.get_logger()

job = Job(glueContext)
job.init(args["JOB_NAME"], args)


def flatten_data(y):
    """
    Recursive function to flatten the JSON structure.

    :param y: nested JSON element.
    :return: flat JSON element.
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


def split_files(bucket, obj_key):
    """
    Divide Firehose Kinesis file in PREDICTIONS and EVENTS files.
    Label the dedicated service name in the file name.

    :param bucket: S3 bucket here the file is stored.
    :param obj_key: String that identigy the file to be split.
    :return predictions_arr: list of JSON predictions extracted from the file
    :return events_arr: list of JSON events extracted from the file
    """
    predictions_arr = {"summarizer": [], "headline": [], "ste": []}
    events_arr = {"summarizer": [], "headline": [], "ste": []}
    content = []
    obj = bucket.Object(obj_key)
    obj.download_file("/tmp/tmp_file")
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
            flat_el = flatten_data(json.loads(el))
            if flat_el["detail-type"] == "DVaultPredictionEvent":
                predictions_arr[flat_el["detail_prediction_service"]].append(flat_el)
            elif flat_el["detail-type"] == "DVaultEvaluationEvent":
                service_name = flat_el["detail_evaluation_prediction_id"].split("#")[-1]
                events_arr[service_name].append(flat_el)
            else:
                e = f'Unrecognized event type inside file: {flat_el["detail-type"]}'
                logger.error(e)
                sys.exit(0)
        except Exception as e:
            logger.error(e)
            sys.exit(0)
    return (predictions_arr, events_arr)


# Main instructions for the Glue Job
logger.info("Splitting Firehose Kinesis file in predictions and events.")
s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(landing_bucketname)
all_objkeys = [obj.key for obj in list(bucket.objects.all())]

for obj_key in all_objkeys:
    logger.info(f"Splititng file {obj_key}.")
    raw_bucketname = landing_bucketname
    key = obj_key
    output_path = f"{landing_bucketname}/flat_json"
    file_name = key.split("/")[-1]

    s3 = boto3.resource("s3", region_name="us-east-1")
    bucket = s3.Bucket(raw_bucketname)
    try:
        predictions_arr, events_arr = split_files(bucket, key)
        logger.info(f"Extracted {len(predictions_arr)} prediction elements from file.")
        logger.info(f"Extracted {len(events_arr)} event elements from file.")
    except Exception as e:
        logger.error(
            "Something wrong with extraction of prediction/event from file. Process stopped."
        )
        sys.exit(0)
    for service_name, predictions in predictions_arr.items():
        logger.info(f"There are {len(predictions)} items for {service_name}.")
        if len(predictions) > 0:
            tmp_key = f"/tmp/{file_name}_{service_name.upper()}.jsonl"
            output_key = f"predictions/{file_name}_{service_name.upper()}.jsonl"
            obj = s3.Object(landing_bucketname, output_key)
            with open(tmp_key, "wb") as outfile:
                for entry in predictions:
                    json.dump(entry, outfile)
                    outfile.write("\n")
            obj.put(Body=open(tmp_key, "rb"))
        else:
            logger.warn("No predictions extracted from file.")

    for service_name, events in events_arr.items():
        logger.info(f"There are {len(events)} items for {service_name}.")
        if len(events) > 0:
            tmp_key = f"/tmp/{file_name}_{service_name.upper()}.jsonl"
            output_key = f"events/{file_name}_{service_name.upper()}.jsonl"
            with open(tmp_key, "wb") as outfile:
                for entry in events:
                    json.dump(entry, outfile)
                    outfile.write("\n")
            obj.put(Body=open(tmp_key, "rb"))
        else:
            logger.warn("No events extracted from file.")
job.commit()
