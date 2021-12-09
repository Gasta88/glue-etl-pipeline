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

# Inputs to change inthe Glue Job context
preds_rootpath = f"{bucket_name}/data/flat_json/predictions"
input_destpath = f"{bucket_name}/data//split_json/prediction_input"
output_destpath = f"{bucket_name}/data/split_json/prediction_output"

s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(bucket_name)
filtered_flat_jsons = [
    obj.key
    for obj in list(bucket.objects.all())
    if obj.key.endswith("_STE.jsonl" and "predictions" in obj.key)
]
if len(filtered_flat_jsons) > 0:
    logger.info(f"Found {len(filtered_flat_jsons)} files.")

    for pred_file in filtered_flat_jsons:
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
            "detail_prediction_template_dvault_version",
            "detail_prediction_service_version_software",
            "detail_prediction_service_version_model",
            "detail_prediction_context_paragraph",
            "detail_prediction_context_sentence",
        ]
        ste_input_cols = metadata_cols + ["detail_prediction_input_paragraph"]
        ste_output_cols = metadata_cols + [
            "detail_prediction_output_sentence",
            "detail_prediction_output_search_terms",
            "detail_prediction_output_scores",
        ]
        # Used to remove HTML tags from any sentence
        CLEANR = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")

        content = []
        with open(pred_file, "r") as f:
            content = f.readlines()

        input_list = []
        for line in content:
            element = json.loads(line)
            # prepare input
            input_data = {}
            input_data = {
                key: element.get(key) for key in ste_input_cols if key in element
            }
            input_data["detail_prediction_input_paragraph"] = re.sub(
                CLEANR, "", input_data.get("detail_prediction_input_paragraph", "")
            )
            input_list.append(input_data)

        file_name = f'{pred_file.split("/")[-1][:-6]}_PRED_INPUT.jsonl'
        obj = s3.Object(bucket_name, f"{input_destpath}/{file_name}")
        with open(f"tmp/{file_name}", "wb") as outfile:
            for entry in input_list:
                json.dump(entry, outfile)
                outfile.write("\n")
        obj.put(Body=open(f"tmp/{file_name}", "rb"))

        output_list = []
        for line in content:
            element = json.loads(line)
            # prepare output
            output_data = {
                key: element.get(key) for key in ste_output_cols if key in element
            }
            # I don't need the exact column names, but the number of instances for each output column
            output_cols = [
                key
                for key in element
                if key.startswith("detail_prediction_output_scores_")
            ]
            for i, _ in enumerate(output_cols):
                tmp_data = {}
                tmp_data = dict(output_data)
                tmp_data["detail_prediction_output_sentence"] = re.sub(
                    CLEANR, "", tmp_data["detail_prediction_output_sentence"]
                )
                tmp_data["event"] = i
                tmp_data["search_term"] = element.get(
                    f"detail_prediction_output_search_terms_{i}", None
                )
                tmp_data["score"] = element.get(
                    f"detail_prediction_output_scores_{i}", None
                )
                output_list.append(tmp_data)

        file_name = f'{pred_file.split("/")[-1][:-6]}_PRED_OUTPUT.jsonl'
        obj = s3.Object(bucket_name, f"{output_destpath}/{file_name}")
        with open(f"tmp/{file_name}", "w") as outfile:
            for entry in output_list:
                json.dump(entry, outfile)
                outfile.write("\n")
        obj.put(Body=open(f"tmp/{file_name}", "rb"))
else:
    logger.warn("No STE prediction files available.")
job.commit()
