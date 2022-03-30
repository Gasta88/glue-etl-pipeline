import boto3
import glob
import sys
import time
import pyarrow.parquet as pq
from elasticsearch import Elasticsearch
import os


def upload_files(input_dir, landing_bucketname):
    """
    Load dvault files onto S3 bucket.

    :param input_dir: location of the input files.
    :param landing_bucketname: name of the destination S3 bucket.
    """
    input_files = glob.glob(f"{input_dir}/*")
    s3 = boto3.resource("s3")
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
    glue = boto3.client("glue")
    try:
        response = glue.get_workflow_run(Name=workflow_name, RunId=run_id)
        return response["Run"]["Status"]
    except Exception as e:
        print("unable to get workflow status.")
        print(e)
        sys.exit(1)


def compare_files(landing_bucketname, expected_parquet_files):
    """
    Compare what has been freshly generated to what it is expected.

    :param landing_bucketname: name of the S3 bucket where Parquet files are stored.
    :param expected_parquet_files: list of expected Parquet files.
    """
    results = {}
    test_flag = True
    msg = None
    for expected_pq in expected_parquet_files:
        parquet_name = expected_pq.split("/")[-1]

        final_pq = f"s3://{landing_bucketname}/data/clean_parquet/{parquet_name}"
        expected_table = pq.read_table(expected_pq)
        try:
            final_table = pq.read_table(final_pq)
        except Exception as e:
            test_flag = False
            msg = e
            results[parquet_name] = (test_flag, msg)
            continue
        if (final_table.num_rows + final_table.num_columns) == 0:
            test_flag = False
            msg = "The final Parquet file is empty"
            results[parquet_name] = (test_flag, msg)
            continue
        test_flag = expected_table.shape == final_table.shape
        if test_flag == False:
            results[parquet_name] = (
                test_flag,
                f"Parquet files are not equals. Expected table is {expected_table.shape}, final table is {final_table.shape}",
            )
        else:
            results[parquet_name] = (test_flag, msg)
    return results


def clean_up_es_index(
    es_url="https://search-ai-elasticsearch-6-public-whkzoh3jmwiwidqwvzag2jxse4.us-east-1.es.amazonaws.com",
    index_name="dvault_logs",
):
    """
    During E2E the dvault_logs index must be purged.

    :param es_url: URL of the ElasticSearch domain.
    """
    ci_cd = os.environ.get("CI_CD", None)
    if ci_cd is not None:
        index_name = "dvault_logs_test"
    es = Elasticsearch(es_url)
    if not es.ping():
        sys.exit(1)
    es.indices.delete(index=index_name, ignore=[400, 404])
    return


def main():
    """
    Run main steps in the run_etl script.
    """
    # main properties
    input_dir = "data/input"
    landing_bucketname = "dvault-landing-e2e-test"
    workflow_name = "s3-batch-glue-dvault-workflow-e2e-test"
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
        test_res = compare_files(landing_bucketname, expected_parquet_files)
        for fname, tpl in test_res.items():
            if not tpl[0]:
                print(f"{fname} has failed: {tpl[1]}")
                sys.exit(1)
    else:
        print("Wrong status to finish the workflow.")
        sys.exit(1)
    clean_up_es_index()


if __name__ == "__main__":
    main()
