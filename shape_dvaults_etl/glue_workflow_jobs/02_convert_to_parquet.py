import boto3
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.job import Job
import sys
import re


sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
logger = glueContext.get_logger()

logger.info("Get run properties for the Glue workflow.")
args = getResolvedOptions(
    sys.argv,
    ["WORKFLOW_NAME", "WORKFLOW_RUN_ID", "JOB_NAME"],
)
workflow_name = args["WORKFLOW_NAME"]
workflow_run_id = args["WORKFLOW_RUN_ID"]
glue = boto3.client("glue")
run_properties = glue.get_workflow_run_properties(
    Name=workflow_name, RunId=workflow_run_id
)["RunProperties"]

job = Job(glueContext)
job.init(args["JOB_NAME"], args)

bucket_name = run_properties["landing_bucketname"]
input_rootpath = f"s3a://{bucket_name}/data/flat_json"
output_path = f"s3a://{bucket_name}/data/clean_parquet"
file_name = run_properties["dvault_filename"].split("/")[-1]
table_names = [
    "HEADLINE_PRED",
    "HEADLINE_EVENT",
    "STE_PRED",
    "STE_EVENT",
    "SUMMARIZER_PRED",
    "SUMMARIZER_EVENT",
]
s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(bucket_name)
all_jsons = [
    obj.key
    for obj in list(bucket.objects.all())
    if ("flat_json" in obj.key) and (file_name in obj.key)
]

for table_name in table_names:
    service_name = table_name.split("_")[0]
    table_type = table_name.split("_")[1]
    logger.info(f"Processing {table_type} for service {service_name}.")
    file_names = [
        f for f in all_jsons if ((service_name in f) and (table_type.lower() in f))
    ]
    if file_names is not []:
        logger.info(f'Converting: {"; ".join(file_names)}')
        df = spark.read.json(file_names)
        df.write.format("parquet").mode("append").save(
            f"{output_path}/{table_name}.parquet"
        )
    else:
        logger.warn("No split JSON to convert to Parquet.")
job.commit()
