import boto3
import sys
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ["bucket_name"])

bucket_name = args["bucket_name"]
prefixes_to_cleanup = ["data/raw/", "data/flat-dvault"]

s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket(bucket_name)

for prefix in prefixes_to_cleanup:
    object_keys = [obj.key for obj in list(bucket.objects.all()) if prefix in obj.key]
    for key in object_keys:
        s3.Object(bucket_name, key).delete()
