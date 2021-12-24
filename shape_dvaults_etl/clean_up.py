import boto3
import sys
from awsglue.utils import getResolvedOptions
import logging

# Setup logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Get run properties for the Glue workflow.")
args = getResolvedOptions(sys.argv, ["WORKFLOW_NAME", "WORKFLOW_RUN_ID"])
workflow_name = args["WORKFLOW_NAME"]
workflow_run_id = args["WORKFLOW_RUN_ID"]
glue = boto3.client("glue")
run_properties = glue.get_workflow_run_properties(
    Name=workflow_name, RunId=workflow_run_id
)["RunProperties"]

bucket_name = run_properties["landing_bucketname"]
prefixes_to_cleanup = ["data/raw/", "data/flat_json"]
file_name = run_properties["dvault_filename"].split("/")[-1]

s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(bucket_name)
keys_to_remove = []

logger.info("Starting environment clean-up.")
for prefix in prefixes_to_cleanup:
    tmp_arr = [
        obj.key
        for obj in list(bucket.objects.all())
        if (prefix in obj.key) and (file_name in obj.key)
    ]
    keys_to_remove += tmp_arr

for key in keys_to_remove:
    s3.Object(bucket_name, key).delete()

logger.info("Finishing environment clean-up.")
