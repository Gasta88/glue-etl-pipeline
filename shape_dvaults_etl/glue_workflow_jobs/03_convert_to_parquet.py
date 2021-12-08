import boto3
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
import json
import sys
import re

import glob

sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

import glob

input_rootpath = "/home/jupyter/jupyter_default_dir/data/split_json"

all_split_jsons = glob.glob(f"{input_rootpath}/*/*.jsonl")

output_path = "/home/jupyter/jupyter_default_dir/data/clean_parquet"
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
for table_name in table_names:
    # it shoulf be just one element
    file_names = [f for f in all_split_jsons if table_name in f]
    if file_names is not []:
        df = spark.read.json(file_names)
        df.write.format("parquet").mode("append").save(
            f"{output_path}/{table_name}.parquet"
        )
        # TODO: upload to bucket
