import boto3
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.job import Job
import sys


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

# Job parameters
output_path = f's3a://{run_properties["landing_bucketname"]}/data/clean_parquet'
s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(run_properties["landing_bucketname"])
ALL_JSONS = [obj.key for obj in list(bucket.objects.filter(Prefix="data/flat_jsons"))]
table_names = [
    "HEADLINE_PRED",
    "HEADLINE_EVENT",
    "STE_PRED",
    "STE_EVENT",
    "SUMMARIZER_PRED",
    "SUMMARIZER_EVENT",
]


def create_parquet(spark, table_name, dest_filename):
    """
    Create Parquet file into clean-parquet prefix.

    :param spark: Spark Session object.
    :param table_name: name of the Athena table to refer.
    :param dest_filename: name final Parquet file.
    """
    service_name = table_name.split("_")[0]
    table_type = table_name.split("_")[1]
    logger.info(f"Processing {table_type} for service {service_name}.")
    file_names = [
        f's3://{run_properties["landing_bucketname"]}/{f}'
        for f in ALL_JSONS
        if ((service_name in f) and (table_type.lower() in f))
    ]
    if file_names is not []:
        logger.info(f'Converting: {"; ".join(file_names)}')
        df = spark.read.json(file_names)
        df.write.format("parquet").mode("append").save(dest_filename)
    else:
        logger.warn("No split JSON to convert to Parquet.")
    return


for table_name in table_names:
    parquet_filename = f"{output_path}/{table_name}.parquet"
    create_parquet(spark, table_name, parquet_filename)

job.commit()
