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
spark = glueContext.spark_session
logger = glueContext.get_logger()

job = Job(glueContext)
job.init(args["JOB_NAME"], args)

input_rootpath = f"s3a://{bucket_name}/data/split_json"
output_path = f"s3a://{bucket_name}/data/clean_parquet"
table_names = [
    "HEADLINE_PRED_INPUT",
    "HEADLINE_PRED_OUTPUT",
    "HEADLINE_EVENT",
    "STE_PRED_INPUT",
    "STE_PRED_OUTPUT",
    "STE_EVENT_INPUT",
    "STE_EVENT_OUTPUT",
    "SUMMARIZER_PRED_INPUT",
    "SUMMARIZER_PRED_OUTPUT",
    "SUMMARIZER_EVENT_INPUT",
    "SUMMARIZER_EVENT_OUTPUT",
]
s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(bucket_name)
all_split_jsons = [
    obj.key
    for obj in list(bucket.objects.all())
    if obj.key.endswith(".jsonl") and "split_jsons" in obj.key
]

for table_name in table_names:
    file_names = [f for f in all_split_jsons if table_name in f]
    if file_names is not []:
        logger.info(f'Converting: {"; ".join(file_names)}')
        df = spark.read.json(file_names)
        df.write.format("parquet").mode("append").save(
            f"{output_path}/{table_name}.parquet"
        )
    else:
        logger.warn("No split JSON to convert to Parquet.")
job.commit()
