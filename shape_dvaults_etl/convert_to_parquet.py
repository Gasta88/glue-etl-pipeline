import boto3
import logging
import sys


# Setup logger
logger = logging.getLogger(__name__)
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
    config["SQL_DICT"] = {
        "HEADLINE_PRED": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.prediction.service as service,
                            detail.prediction.service_version as service_version,
                            detail.prediction.timestamp as unix_timestamp,
                            detail.prediction.shape_id as shape_id,
                            detail.prediction.input.transcript as transcript,
                            detail.prediction.output.headline as headline,
                            time as date_time
                            from headline_pred
                        """,
        "HEADLINE_EVENT": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.evaluation.prediction_id as prediction_id,
                            detail.evaluation.reporter as reporter,
                            detail.evaluation.type as event_type,
                            detail.evaluation.timestamp as unix_timestamp,
                            detail.evaluation.shape_id as shape_id,
                            detail.evaluation.payload.text as payload_text,
                            time as date_time
                            from headline_event
                        """,
        "STE_PRED": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.prediction.service as service,
                            detail.prediction.service_version as service_version,
                            detail.prediction.timestamp as unix_timestamp,
                            detail.prediction.shape_id as shape_id,
                            detail.prediction.context as context,
                            detail.prediction.input.paragraph as paragraph,
                            detail.prediction.output.scores as scores,
                            detail.prediction.output.search_terms as search_terms,
                            detail.prediction.output.sentence as sentence,
                            time as date_time
                            from ste_pred
                        """,
        "STE_EVENT": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.evaluation.prediction_id as prediction_id,
                            detail.evaluation.reporter as reporter,
                            detail.evaluation.type as event_type,
                            detail.evaluation.timestamp as unix_timestamp,
                            detail.evaluation.shape_id as shape_id,
                            detail.evaluation.payload.text as payload_text,
                            detail.evaluation.payload.query as payload_query,
                            detail.evaluation.payload.media_id as payload_media_id,
                            detail.evaluation.payload.media_type as payload_media_type,
                            detail.evaluation.payload.medialib as payload_medialib,
                            detail.evaluation.payload.tags as payload_tags,
                            detail.evaluation.payload.caption as payload_caption,
                            time as date_time
                            from ste_event
                        """,
        "SUMMARIZER_PRED": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.prediction.service as service,
                            detail.prediction.service_version as service_version,
                            detail.prediction.timestamp as unix_timestamp,
                            detail.prediction.shape_id as shape_id,
                            detail.prediction.input.paragraphs as input_paragraphs,
                            detail.prediction.input.sentences_scores as input_sentences_scores,
                            detail.prediction.output.summary as output_summary,
                            detail.prediction.output.metadata as output_metadata,
                            detail.prediction.output.skipped_paragraphs as output_skipped_paragraphs,
                            time as date_time
                            from summarizer_pred
                        """,
        "SUMMARIZER_EVENT": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.evaluation.prediction_id as prediction_id,
                            detail.evaluation.timestamp as unix_timestamp,
                            detail.evaluation.shape_id as shape_id,
                            detail.evaluation.type as event_type,
                            detail.evaluation.reporter as reporter,
                            detail.evaluation.payload.paragraph as paragraph,
                            detail.evaluation.payload.slide as slide,
                            detail.evaluation.payload.text as text,
                            time as date_time
                            from summarizer_event
                        """,
    }
    return config


def get_spark_dataframe(spark, table_name, landing_bucketname, all_jsons):
    """
    Create Spark dataframe by using the table name (service type/service name).

    :param spark: Spark Session object.
    :param table_name: name of the table to refer.
    :landing_bucketname: name of the S3 bucket wehre to store parquet files.
    :all_jsons: array of flat JSON files generated from the ETL pipeline so far
    :return df: Spark dataframe
    """
    service_name = table_name.split("_")[0]
    table_type = table_name.split("_")[1]
    logger.info(f"Processing {table_type} for service {service_name}.")
    file_names = [
        f"{landing_bucketname}/{f}"
        for f in all_jsons
        if ((service_name in f) and (table_type.lower() in f))
    ]
    if len(file_names) > 0:
        logger.info(f'Converting: {"; ".join(file_names)}')
        df = spark.read.json(file_names)
    else:
        logger.warn(f"No available files for {table_name}")
        sys.exit(1)
    return df


def get_refined_dataframe(spark, df, sql_dict, table_name):
    """
    Clean up and refine the data inside the dataframe

    :param spark: Spark Session object.
    :param df: source dataframe.
    :param sql_dict: collection of SQL statements to refine the df.
    :param table_name: name of the table to refer.
    :return refined_df: cleaned dataframe to store on S3.
    """
    logger.info(f"Refining dataset {table_name}")
    df.createOrReplaceTempView(table_name.lower())
    try:
        refined_df = spark.sql(sql_dict[table_name])
    except:
        logger.error(f"Refinement of dataset {table_name} failed.")
        sys.exit(1)
    return refined_df


def main():
    """
    Run main steps in the convert_to_parquet Glue Job.
    """
    run_props = get_run_properties()
    for table_name in run_props["TABLE_NAMES"]:
        parquet_filename = f'{run_props["OUTPUT_PATH"]}/{table_name}.parquet'
        df = get_spark_dataframe(
            run_props["SPARK"],
            table_name,
            f's3://{run_props["LANDING_BUCKETNAME"]}',
            run_props["ALL_JSONS"],
        )
        refined_df = get_refined_dataframe(
            run_props["SPARK"], df, run_props["SQL_DICT"], table_name
        )
        refined_df.write.format("parquet").mode("append").save(parquet_filename)
    return


if __name__ == "__main__":
    main()
