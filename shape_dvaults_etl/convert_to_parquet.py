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


def get_run_properties():
    """Return enhanced job properties.

    :return config: dictionary with properties used in flat_dvaults Glue Job.
    """
    from awsglue.utils import getResolvedOptions
    from awsglue.context import GlueContext
    from pyspark.context import SparkContext

    config = {}
    sc = SparkContext.getOrCreate()
    glueContext = GlueContext(sc)
    config["SPARK"] = glueContext.spark_session
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

    config[
        "OUTPUT_PATH"
    ] = f's3a://{run_properties["landing_bucketname"]}/data/clean_parquet'
    config["LANDING_BUCKETNAME"] = run_properties["landing_bucketname"]
    s3 = boto3.resource("s3", region_name="us-east-1")
    bucket = s3.Bucket(run_properties["landing_bucketname"])
    config["ALL_JSONS"] = [
        obj.key for obj in list(bucket.objects.filter(Prefix="data/flat_jsons"))
    ]
    config["TABLE_NAMES"] = [
        "HEADLINE_PRED",
        "HEADLINE_EVENT",
        "STE_PRED",
        "STE_EVENT",
        "SUMMARIZER_PRED",
        "SUMMARIZER_EVENT",
    ]
    return config


def create_parquet(spark, table_name, dest_filename, landing_bucketname, all_jsons):
    """
    Create Parquet file into clean-parquet prefix.

    :param spark: Spark Session object.
    :param table_name: name of the Athena table to refer.
    :param dest_filename: name final Parquet file.
    :landing_bucketname: name of the S3 bucket wehre to store parquet files.
    :all_jsons: array of flat JSON files generated from the ETL pipeline so far.
    """
    service_name = table_name.split("_")[0]
    table_type = table_name.split("_")[1]
    logger.info(f"Processing {table_type} for service {service_name}.")
    file_names = [
        f"{landing_bucketname}/{f}"
        for f in all_jsons
        if ((service_name in f) and (table_type.lower() in f))
    ]
    if file_names is not []:
        logger.info(f'Converting: {"; ".join(file_names)}')
        df = spark.read.json(file_names)
        df.write.format("parquet").mode("append").save(dest_filename)
    else:
        logger.warn("No split JSON to convert to Parquet.")
    return


def main():
    """
    Run main steps in the convert_to_parquet Glue Job.
    """
    run_props = get_run_properties()
    for table_name in run_props["TABLE_NAMES"]:
        parquet_filename = f'{run_props["OUTPUT_PATH"]}/{table_name}.parquet'
        create_parquet(
            run_props["SPARK"],
            table_name,
            parquet_filename,
            f's3://{run_props["LANDING_BUCKETNAME"]}',
            run_props["ALL_JSONS"],
        )


if __name__ == "__main__":
    main()
