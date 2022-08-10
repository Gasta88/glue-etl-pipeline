import boto3
import glob
import sys
import time
from pyspark.sql import SparkSession
import subprocess


def upload_files(input_dir, landing_bucketname):
    """
    Load event file files onto S3 bucket.

    :param input_dir: location of the input files.
    :param landing_bucketname: name of the destination S3 bucket.
    """
    print("Upload files.")
    cmd = f"aws s3 cp {input_dir}/ s3://{landing_bucketname}/data/raw/ --recursive"
    push = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    print(push.communicate())
    return


def start_workflow(workflow_name):
    """
    Start Glue workflow to process event files.

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


def download_output(landing_bucketname):
    """
    After the Glue workflow has been completed, download localy the output files.

    :param landing_bucketname: name of the S3 bucket where final files are stored.
    :param expected_files: list of expected final files.
    """
    print("Retrieve output files.")
    cmd = f"aws s3 cp s3://{landing_bucketname}/data/clean_parquet/ data/output/ --recursive"
    push = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    print(push.communicate())
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
        expected_df = spark.read.parquet(expected_pq).drop(
            "year", "month", "day", "hour"
        )
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
    landing_bucketname = "ef-ingestion-landing-e2e-test"
    workflow_name = "ef-ingestion-batch-e2e-test"
    expected_parquet_files = glob.glob("data/expected/*")
    # load event file into S3
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
        download_output(landing_bucketname)
        test_res = compare_files(expected_parquet_files)
        for fname, tpl in test_res.items():
            if not tpl[0]:
                print(f"{fname} has failed: {tpl[1]}")
                sys.exit(1)
    else:
        print("Wrong status to finish the workflow.")
        sys.exit(1)
    return


if __name__ == "__main__":
    main()
