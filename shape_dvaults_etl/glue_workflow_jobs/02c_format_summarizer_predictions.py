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
    if obj.key.endswith("_SUMMARIZER.jsonl" and "predictions" in obj.key)
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
        ]
        summarizer_input_cols = metadata_cols + [
            "detail_prediction_input_paragraphs",
            "detail_prediction_input_sentences_scores",
            "detail_prediction_input_reduction_percentage",
        ]
        summarizer_output_cols = metadata_cols + [
            "detail_prediction_output_summary",
            "detail_prediction_output_metadata",
        ]
        summarizer_skipped_cols = metadata_cols + [
            "detail_prediction_output_skipped_paragraphs"
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
                key: element.get(key) for key in summarizer_input_cols if key in element
            }
            # I don't need the exact column names, but the number of instances for each input column
            # There no relationship 1:1 between "sentences_scores" and "paragraphs", but the former will have an higher count
            # in comparison to the latter (ASSUMPTION)
            input_cols = [
                key
                for key in element
                if key.startswith("detail_prediction_input_sentences_scores_")
                and key.endswith("_score")
            ]
            all_paragraphs = [
                element[key]
                for key in element
                if key.startswith("detail_prediction_input_paragraphs_")
            ]
            for i, _ in enumerate(input_cols):
                tmp_data = {}
                tmp_data = dict(input_data)
                tmp_data["event"] = i
                tmp_data["sentence"] = element.get(
                    f"detail_prediction_input_sentences_scores_{i}_sentence", None
                )
                tmp_data["score"] = element.get(
                    f"detail_prediction_input_sentences_scores_{i}_score", None
                )
                if tmp_data["sentence"] is not None:
                    for paragraph in all_paragraphs:
                        if tmp_data["sentence"] in paragraph:
                            tmp_data["paragraph"] = re.sub(CLEANR, "", paragraph)
                            tmp_data["sentence"] = re.sub(
                                CLEANR, "", tmp_data["sentence"]
                            )
                        else:
                            tmp_data["paragraph"] = None
                else:
                    tmp_data["paragraph"] = None
                input_list.append(tmp_data)

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
                key: element.get(key)
                for key in summarizer_output_cols
                if key in element
            }
            # I don't need the exact column names, but the number of instances for each output column
            output_cols = [
                key
                for key in element
                if key.startswith("detail_prediction_output_summary_")
            ]
            for i, _ in enumerate(output_cols):
                tmp_data = {}
                tmp_data = dict(output_data)
                tmp_data["event"] = i
                tmp_data["summary_sentence"] = re.sub(
                    CLEANR,
                    "",
                    element.get(f"detail_prediction_output_summary_{i}", ""),
                )
                filtered_sentences_value = [
                    element[key]
                    for key in element
                    if key.startswith(
                        f"detail_prediction_output_metadata_{i}_filtered_sentences_"
                    )
                ]
                tmp_data["filtered_sentences"] = (
                    filtered_sentences_value
                    if len(filtered_sentences_value) > 0
                    else None
                )
                scores_value = [
                    element[key]
                    for key in element
                    if key.startswith(f"detail_prediction_output_metadata_{i}_scores_")
                ]
                tmp_data["scores"] = scores_value if len(scores_value) > 0 else None
                tmp_data["idx"] = element.get(
                    f"detail_prediction_output_metadata_{i}_idx", None
                )
                tmp_data["skipped_paragraphs_flag"] = 0
                if (
                    element.get(
                        f"detail_prediction_output_skipped_paragraphs_0_text", None
                    )
                    is not None
                ):
                    tmp_data["skipped_paragraphs_flag"] = 1
                output_list.append(tmp_data)

        file_name = os.path.join(
            output_destpath, pred_file.split("/")[-1][:-6] + "_PRED_OUTPUT.jsonl"
        )
        file_name = f'{pred_file.split("/")[-1][:-6]}_PRED_OUTPUT.jsonl'
        obj = s3.Object(bucket_name, f"{output_destpath}/{file_name}")
        with open(f"tmp/{file_name}", "w") as outfile:
            for entry in output_list:
                json.dump(entry, outfile)
                outfile.write("\n")
        obj.put(Body=open(f"tmp/{file_name}", "rb"))

        skipped_list = []
        for line in content:
            element = json.loads(line)
            # prepare output
            skipped_data = {
                key: element.get(key)
                for key in summarizer_skipped_cols
                if key in element
            }
            # I don't need the exact column names, but the number of instances for each output column
            skipped_cols = [
                key
                for key in element
                if key.startswith("detail_prediction_output_skipped_paragraphs_")
            ]
            for i, _ in enumerate(skipped_cols):
                tmp_data = {}
                tmp_data = dict(skipped_data)
                tmp_data["event"] = i
                tmp_data["text"] = re.sub(
                    CLEANR,
                    "",
                    element.get(
                        f"detail_prediction_output_skipped_paragraphs_{i}_text", ""
                    ),
                )
                tmp_data["index"] = element.get(
                    f"detail_prediction_output_skipped_paragraphs_{i}_index", None
                )
                tmp_data["language"] = element.get(
                    f"detail_prediction_output_skipped_paragraphs_{i}_language",
                    None,
                )
                tmp_data["text_language"] = element.get(
                    f"detail_prediction_output_skipped_paragraphs_{i}_text_language",
                    None,
                )
                tmp_data["original_paragraph"] = int(
                    element.get(
                        f"detail_prediction_output_skipped_paragraphs_{i}_language",
                        None,
                    )
                    == "true"
                )
                skipped_list.append(tmp_data)
        # not alway present in Summarizer files
        if len(skipped_list) > 0:
            file_name = f'{pred_file.split("/")[-1][:-6]}_PRED_SKIP_PAR_OUTPUT.jsonl'
            obj = s3.Object(bucket_name, f"{output_destpath}/{file_name}")
            with open(f"tmp/{file_name}", "w") as outfile:
                for entry in output_list:
                    json.dump(entry, outfile)
                    outfile.write("\n")
            obj.put(Body=open(f"tmp/{file_name}", "rb"))
else:
    logger.warn("No SUMMARIZER prediction files available.")
job.commit()
