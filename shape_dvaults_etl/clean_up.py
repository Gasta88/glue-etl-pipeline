import boto3
import sys
import logging

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

    :return config: dictionary with properties used in flat_dvaults Glue Job."""
    from awsglue.utils import getResolvedOptions

    config = {}
    logger.info("Get run properties for the Glue workflow.")
    args = getResolvedOptions(sys.argv, ["WORKFLOW_NAME", "WORKFLOW_RUN_ID"])
    workflow_name = args["WORKFLOW_NAME"]
    workflow_run_id = args["WORKFLOW_RUN_ID"]
    glue = boto3.client("glue")
    run_properties = glue.get_workflow_run_properties(
        Name=workflow_name, RunId=workflow_run_id
    )["RunProperties"]

    config["BUCKET_NAME"] = run_properties["landing_bucketname"]
    # DVAULT_FILES = run_properties["dvault_files"].split(";")
    return config


def main():
    """
    Run main steps in the flat_dvaults Glue Job.
    """
    logger.info("Starting environment clean-up.")
    # for key in DVAULT_FILES:
    #     s3.Object(bucket_name, key).delete()
    # logger.info("data/raw/ prefix clean-up is complete.")
    run_props = get_run_properties()
    s3 = boto3.resource("s3", region_name="us-east-1")
    bucket = s3.Bucket(run_props["BUCKET_NAME"])
    for key in [
        obj.key for obj in list(bucket.objects.filter(Prefix="data/flat_jsons"))
    ]:
        s3.Object(run_props["BUCKET_NAME"], key).delete()
    logger.info("data/flat_jsons/ prefix clean-up is complete.")

    for key in [
        obj.key for obj in list(bucket.objects.filter(Prefix="data/clean_dvaults"))
    ]:
        s3.Object(run_props["BUCKET_NAME"], key).delete()
    logger.info("data/clean_dvaults/ prefix clean-up is complete.")

    logger.info("Finishing environment clean-up.")


if __name__ == "__main__":
    main()
