import json
import boto3
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.job import Job
import sys
import re

args = getResolvedOptions(sys.argv, ["JOB_NAME", "bucket_name"])
bucket_name = args["bucket_name"]
sc = SparkContext()
glueContext = GlueContext(sc)
logger = glueContext.get_logger()

job = Job(glueContext)
job.init(args["JOB_NAME"], args)

events_rootpath = f"{bucket_name}/data/flat_json/events"
input_destpath = f"{bucket_name}/data/split_json/event_input"
output_destpath = f"{bucket_name}/data/split_json/event_output"
s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(bucket_name)
filtered_flat_jsons = [
    obj.key
    for obj in list(bucket.objects.all())
    if obj.key.endswith("_SUMMARIZER.jsonl" and "events" in obj.key)
]
if len(filtered_flat_jsons) > 0:
    logger.info(f"Found {len(filtered_flat_jsons)} files.")
    for event_file in filtered_flat_jsons:
        metadata_cols = [
            "version",
            "id",
            "detail-type",
            "source",
            "account",
            "time",
            "region",
            "detail_id",
            "detail_timestamp",
            "detail_partitionKey",
        ]
        summarizer_input_cols = metadata_cols + [
            "detail_evaluation_template_dvault_version",
            "detail_evaluation_reporter",
            "detail_evaluation_type",
        ]
        summarizer_output_cols = metadata_cols + [
            "detail_evaluation_payload_paragraph",
            "detail_evaluation_payload_slide",
        ]
        # Used to remove HTML tags from any sentence
        CLEANR = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")

        content = []
        with open(event_file, "r") as f:
            content = f.readlines()

        input_list = []
        for line in content:
            element = json.loads(line)
            # prepare input
            input_data = {}
            input_data = {
                key: element.get(key) for key in summarizer_input_cols if key in element
            }
            input_list.append(input_data)

        file_name = f'{event_file.split("/")[-1][:-6]}_EVENT_INPUT.jsonl'
        obj = s3.Object(bucket_name, f"{input_destpath}/{file_name}")
        with open(file_name, "w") as outfile:
            for entry in input_list:
                json.dump(entry, outfile)
                outfile.write("\n")
        obj.put(Body=open(f"tmp/{file_name}", "rb"))

        output_list = []
        for line in content:
            element = json.loads(line)
            # prepare output
            output_data = {
                key: element.get(key)
                for key in summarizer_output_cols
                if key in element
            }
            output_data["text"] = re.sub(
                CLEANR, "", element.get("detail_evaluation_payload_text", "")
            )
            output_list.append(output_data)

        file_name = f'{event_file.split("/")[-1][:-6]}_EVENT_OUTPUT.jsonl'
        obj = s3.Object(bucket_name, f"{output_destpath}/{file_name}")
        with open(file_name, "w") as outfile:
            for entry in output_list:
                json.dump(entry, outfile)
                outfile.write("\n")
        obj.put(Body=open(f"tmp/{file_name}", "rb"))
else:
    logger.warn("No SUMMARIZER prediction files available.")
job.commit()
