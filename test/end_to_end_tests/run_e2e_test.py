import boto3
import glob
import sys
import time
from pyspark.sql import SparkSession
from pyarrow import fs
import os


def upload_files(input_dir, landing_bucketname):
    """
    Load dvault files onto S3 bucket.

    :param input_dir: location of the input files.
    :param landing_bucketname: name of the destination S3 bucket.
    """
    input_files = glob.glob(f"{input_dir}/*")
    s3 = boto3.resource("s3", region_name="us-east-1")
    for f in input_files:
        f_name = f.split("/")[-1]
        output_key = f"data/raw/{f_name}"
        obj = s3.Object(landing_bucketname, output_key)
        obj.put(Body=open(f, "rb"))
    return


def start_workflow(workflow_name):
    """
    Start Glue workflow to process dvaults.

    :param workflow_name: name of the Glue workflow.
    :return run_id: workflow run id.
    """
    glue = boto3.client("glue", region_name="us-east-1")
    try:
        response = glue.start_workflow_run(Name=workflow_name)
        return response["RunId"]
    except Exception as e:
        print("Unable to start workflow.")
        print(e)
        sys.exit(1)


def get_workflow_status(workflow_name, run_id):
    """
    Rturn status of the workflow run.

    :param workflow_name: name of the Glue workflow.
    :param run_id: id of the Glue workflow run.
    :return status: current status of the workflow run.
    """
    glue = boto3.client("glue", region_name="us-east-1")
    try:
        response = glue.get_workflow_run(Name=workflow_name, RunId=run_id)
        return response["Run"]["Status"]
    except Exception as e:
        print("unable to get workflow status.")
        print(e)
        sys.exit(1)


def download_output(landing_bucketname, expected_files):
    """
    After the Glue workflow has been completed, download localy the output files.

    :param landing_bucketname: name of the S3 bucket where final files are stored.
    :param expected_files: list of expected final files.
    """
    print("Retrieve output files.")
    local_fs = fs.LocalFileSystem()
    s3_fs = fs.S3FileSystem()
    BATCH_SIZE = 1024 * 1024
    for expected_f in expected_files:
        parquet_name = expected_f.split("/")[-1]
        final_f = f"{landing_bucketname}/data/clean_parquet/{parquet_name}/"
        all_prefixes = s3_fs.get_file_info(fs.FileSelector(final_f, recursive=True))
        all_files = [p for p in all_prefixes if p.type.name == "File"]
        os.makedirs(f"data/output/{parquet_name}")
        for f in all_files:
            with s3_fs.open_input_stream(f.path) as in_file:
                with local_fs.open_output_stream(
                    f"data/output/{parquet_name}/{f.base_name}"
                ) as out_file:
                    while True:
                        buf = in_file.read(BATCH_SIZE)
                        if buf:
                            out_file.write(buf)
                        else:
                            break
    return


def compare_files(expected_parquet_files):
    """
    Compare what has been freshly generated to what it is expected.

    :param expected_parquet_files: list of expected Parquet files.
    """
    print("Compare expected vs final files.")
    spark = SparkSession.builder.master("local").getOrCreate()
    spark.sparkContext.setLogLevel("FATAL")
    results = {}
    test_flag = True
    msg = None
    for expected_pq in expected_parquet_files:
        parquet_name = expected_pq.split("/")[-1]

        final_pq = f"data/output/{parquet_name}"
        expected_df = spark.read.parquet(expected_pq)
        try:
            final_df = spark.read.parquet(final_pq)
        except Exception as e:
            test_flag = False
            msg = e
            results[parquet_name] = (test_flag, msg)
            continue
        final_table_shape = (final_df.count(), len(final_df.columns))
        expected_table_shape = (expected_df.count(), len(expected_df.columns))
        if final_table_shape[0] == 0:
            test_flag = False
            msg = "The final file is empty"
            results[parquet_name] = (test_flag, msg)
            continue
        test_flag = expected_table_shape == final_table_shape
        if test_flag == False:
            results[parquet_name] = (
                test_flag,
                f"Files are not equals. Expected table is {expected_table_shape}, final table is {final_table_shape}",
            )
        else:
            results[parquet_name] = (test_flag, msg)
    spark.stop()
    return results


def main():
    """
    Run main steps in the run_etl script.
    """
    # main properties
    input_dir = "data/input"
    landing_bucketname = "shape-dvault-ingestion-landing-e2e-test"
    workflow_name = "shape-dvault-ingestion-batch-e2e-test"
    expected_parquet_files = glob.glob("data/expected/*")
    # load dvault into S3
    upload_files(input_dir, landing_bucketname)
    # start Glue workflow
    run_id = start_workflow(workflow_name)
    status = None
    # Sleep for 60 seconds and constantly check if the worflow is completed
    while status not in ["COMPLETED", "STOPPED", "ERROR"]:
        print("Workflow is running.")
        time.sleep(60)
        status = get_workflow_status(workflow_name, run_id)
    print(f"Workflow run has finished with status: {status}")

    if status == "COMPLETED":
        download_output(landing_bucketname, expected_parquet_files)
        test_res = compare_files(expected_parquet_files)
        for fname, tpl in test_res.items():
            if not tpl[0]:
                print(f"{fname} has failed: {tpl[1]}")
                sys.exit(1)
    else:
        print("Wrong status to finish the workflow.")
        sys.exit(1)


if __name__ == "__main__":
    main()
