from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.job import Job
from pyspark import SparkContext, SparkConf
from pyspark.sql import SparkSession
from awsglue.utils import getResolvedOptions
from great_expectations.data_context.types.base import (
    DataContextConfig,
    S3StoreBackendDefaults,
)
from great_expectations.data_context import BaseDataContext
from great_expectations.profile import BasicSuiteBuilderProfiler
from great_expectations.data_context.types.resource_identifiers import (
    ValidationResultIdentifier,
)
import json
import boto3
import sys

args = getResolvedOptions(sys.argv, ["JOB_NAME", "bucket_name"])
bucket_name = args["bucket_name"]
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
logger = glueContext.get_logger()
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args["JOB_NAME"], args)

events_rootpath = f"{bucket_name}/data/flat_json/events"
exceptions_path = f"{bucket_name}/data/exceptions_json/events"
s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(bucket_name)
filtered_jsons = [obj.key for obj in list(bucket.objects.all()) if "events" in obj.key]

for event_file in filtered_jsons:
    logger.info(f"Profiling file {event_file}.")

    # First load your table data
    df = spark.read.json(event_file)

    # Initiate great_expectations context
    data_context_config = DataContextConfig(
        config_version=2,
        plugins_directory=None,
        config_variables_file_path=None,
        datasources={
            "my_spark_datasource": {
                "data_asset_type": {
                    "class_name": "SparkDFDataset",
                    "module_name": "great_expectations.dataset",
                },
                "class_name": "SparkDFDatasource",
                "module_name": "great_expectations.datasource",
                "batch_kwargs_generators": {
                    "example": {
                        "class_name": "S3GlobReaderBatchKwargsGenerator",
                        "bucket": bucket_name,  # Bucket with the data to profile
                        "assets": {
                            "example_asset": {
                                "prefix": "data/flat_json/events/",  # Prefix of the data to profile. Trailing slash is important
                                "regex_filter": ".*jsonl",  # Filter by type csv, parquet....
                            }
                        },
                    },
                },
            }
        },
        stores={
            "expectations_S3_store": {
                "class_name": "ExpectationsStore",
                "store_backend": {
                    "class_name": "TupleS3StoreBackend",
                    "bucket": bucket_name,  # Bucket storing great_expectations suites results
                    "prefix": "data/data-profiling/expectations-results/",  # Trailing slash is important
                },
            },
            "validations_S3_store": {
                "class_name": "ValidationsStore",
                "store_backend": {
                    "class_name": "TupleS3StoreBackend",
                    "bucket": bucket_name,
                    "prefix": "data/data-profiling/validation-results/",
                },
            },
            "evaluation_parameter_store": {"class_name": "EvaluationParameterStore"},
        },
        expectations_store_name="expectations_S3_store",
        validations_store_name="validations_S3_store",
        evaluation_parameter_store_name="evaluation_parameter_store",
        store_backend_defaults=S3StoreBackendDefaults(default_bucket_name=bucket_name),
    )
    logger.info(f"Great Expectations data context config: {data_context_config}")

    context = BaseDataContext(project_config=data_context_config)
    logger.info(f"Great Expectations data context: {context}")
    logger.info(f"Great Expectations datasources {context.list_datasources()}")

    batch_kwargs = {"dataset": df, "datasource": "my_spark_datasource"}

    expectation_suite_name = f"{event_file}_profiling"

    suite = context.create_expectation_suite(
        expectation_suite_name, overwrite_existing=True
    )

    # Here where you can define expectations for your table columns
    batch = context.get_batch(batch_kwargs, suite)
    batch.expect_column_to_exist("an_example_column")
    batch.expect_column_values_to_not_be_null("an_example_column")
    batch.expect_column_values_to_be_unique("an_example_column")

    # Include all the columns to be profiled
    included_columns = ["an_example_column"]
    scaffold_config = {
        "included_columns": included_columns,
    }
    # Build your suites
    suite, evr = BasicSuiteBuilderProfiler().profile(
        batch, profiler_configuration=scaffold_config
    )

    # Save GE demo file
    context.save_expectation_suite(suite, expectation_suite_name)

    # Build GE data docs
    context.build_data_docs()

    print("Expecations well generated and stored on S3 bucket !")
