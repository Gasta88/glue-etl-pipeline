import boto3
import logging
import sys
from elasticsearch import Elasticsearch
from datetime import datetime

# Setup logging
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
    args = getResolvedOptions(
        sys.argv,
        ["WORKFLOW_NAME", "WORKFLOW_RUN_ID"],
    )
    config["workflow_name"] = args["WORKFLOW_NAME"]
    config["workflow_run_id"] = args["WORKFLOW_RUN_ID"]
    env = args["WORKFLOW_NAME"].split("-")[-1]
    config["ENVIRONMENT"] = f"e2e-{env}" if env == "test" else env
    return config


def _is_workflow_run_valid(workflow_run):
    """
    Check if workflow run is valid.

    :param workflow_run: dictionary that represent the workflow run metadata.
    :return is_valid: whether the workflow run is valid or not.
    """
    is_valid = False
    succeeded_actions = workflow_run["Statistics"]["SucceededActions"]
    run_state = workflow_run["WorkflowRunProperties"].get("run_state", "STARTED")
    # Workflow run has been completed and most of the jobs are succeeded (sending logs to ES is not mandatory)
    if succeeded_actions >= 5 and run_state == "COMPLETED":
        is_valid = True
    return is_valid


def _extract_workflow_details(workflow_run, job_name):
    """
    Extract workflow id and profile run job id for each valid workflow.

    :param workflow_run: dictionary with workflow run information.
    :param job_name: data profile job name.
    :return workflow_details: dictionary of workflow run id and job run id.
    """
    workflow_details = {"workflow_run_id": None, "job_run_id": None}
    workflow_details["workflow_run_id"] = workflow_run["WorkflowRunId"]
    for node in workflow_run["Graph"]["Nodes"]:
        if node["Name"] == job_name:
            workflow_details["job_run_id"] = node["JobDetails"]["JobRuns"][0]["Id"]
    return workflow_details


def get_valid_workflow_run(workflow_name, workflow_run_id, env):
    """
    Return all valid workflow runs from CloudWatch by iterating through pages.

    :param workflow_name: name of the current workflow to capture.
    :param workflow_run_id: is of the current workflow run to capture.
    :param env: name of the current environment
    :return workflow_details: details of valid Glue workflow.
    """
    glue = boto3.client("glue")
    job_name = f"ef-ingestion-profile-job-{env}"
    try:
        workflow_run = glue.get_workflow_run(
            Name=workflow_name, RunId=workflow_run_id, IncludeGraph=True
        )
    except:
        logger.warn(f"No run for workflow {workflow_name}")
        sys.exit(1)
    if _is_workflow_run_valid(workflow_run["Run"]):
        logger.info(f"{workflow_run_id} is valid.")
        workflow_details = _extract_workflow_details(workflow_run["Run"], job_name)
    else:
        logger.info(f"{workflow_run_id} is NOT valid.")
    return workflow_details


def get_log_entries(workflow_details, log_group_name="/aws-glue/python-jobs/output"):
    """
    Extract log entries from the PROFILER and attach them to the workflow details.

    :param workflow_details: information releted to successful workflow for Shape ETL.
    :param log_group_name: group of logs used by CloudWatch.
    :return workflow_details: enhanced workflow details with raw log entries.
    """
    logs = boto3.client("logs")
    logger.info(f'Processing {workflow_details["workflow_run_id"]}')
    log_entries = []
    response = logs.get_log_events(
        logGroupName=log_group_name, logStreamName=workflow_details["job_run_id"]
    )
    for event in response["events"]:
        if "- __main__ - INFO - PROFILER -" in event["message"][:60]:
            log_entries.append(event["message"])
    next_token = response.get("nextForwardToken", None)
    while next_token is not None:
        response = logs.get_log_events(
            logGroupName=log_group_name,
            logStreamName=workflow_details["job_run_id"],
            nextToken=next_token,
            startFromHead=True,
        )
        for event in response["events"]:
            if "- __main__ - INFO - PROFILER -" in event["message"][:60]:
                log_entries.append(event["message"])
        new_next_token = response.get("nextForwardToken", None)
        if next_token == new_next_token:
            next_token = None
        else:
            next_token = new_next_token
    logger.info(f"Fetched {len(log_entries)} logs enties.")
    workflow_details["log_entries"] = log_entries
    return workflow_details


def format_log_entries(workflow_logs):
    """
    Process log entries in a nicer format.

    :param workflow_logs: raw log entries for each dvault event.
    :return new_logs: newly formatted logs.
    """
    new_logs = []
    for le in workflow_logs["log_entries"]:
        le_arr = le.split("|")
        new_logs.append(
            {
                "workflow_run_id": workflow_logs["workflow_run_id"],
                "job_run_id": workflow_logs["job_run_id"],
                "timestamp": datetime.strptime(
                    le_arr[0].split(" - ")[0][:-4], "%Y-%m-%d %H:%M:%S"
                ),
                "event_id": le_arr[0].split(" - ")[-1].split(":")[-1],
                "passed": le_arr[1].split(":")[-1],
                "event_filename": le_arr[2].split(":")[-1],
                "service_name": le_arr[3].split(":")[-1].upper(),
                "service_type": le_arr[4].split(":")[-1].upper(),
                "errors": "{}"
                if le_arr[1].split(":")[-1] == "True"
                else le_arr[5][7:].replace("\n", ""),
            }
        )
    return new_logs


def send_log_to_es(
    nice_logs,
    index_name,
    es_url="https://search-ai-elasticsearch-6-public-whkzoh3jmwiwidqwvzag2jxse4.us-east-1.es.amazonaws.com",
):
    """
    Send formatted logs to ElasticSearch cluster.

    :param es_url: URL for the AWS OpenSearch cluster.
    :param nice_logs: formatted logs to create the index.
    :param index_name: string that represent the name of the ES index.
    """
    es = Elasticsearch(es_url)
    if not es.ping():
        logger.error(f"No cluster available at {es_url}")
        sys.exit(1)
    else:
        logger.info("Cluster available.")
    for nice_log in nice_logs:
        res = es.index(index=index_name, body=nice_log)
    return


def main():
    """
    Run main steps in the process_logs Glue Job.
    """
    run_props = get_run_properties()
    # Skip job run if running end-to-end test and dev pipeline
    if run_props["ENVIRONMENT"] in ["e2e-test", "dev"]:
        return
    workflow_name = run_props["workflow_name"]
    workflow_run_id = run_props["workflow_run_id"]
    index_name = f'efs_ingestion_logs_{run_props["ENVIRONMENT"]}'
    logger.info(f"Get all info on workflow run {workflow_run_id}.")
    workflow_run = get_valid_workflow_run(
        workflow_name, workflow_run_id, run_props["ENVIRONMENT"]
    )
    logger.info("Get all log entries.")
    workflow_logs = get_log_entries(workflow_run)
    logger.info("Format logs.")
    formatted_log_entries = format_log_entries(workflow_logs)
    logger.info("Write logs into ES.")
    send_log_to_es(formatted_log_entries, index_name)
    return


if __name__ == "__main__":
    main()
