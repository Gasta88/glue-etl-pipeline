import boto3
import logging
import sys
import json
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
    return config


def _is_workflow_run_valid(workflow_run):
    """
    Check if workflow run is valid.

    :param workflow_run: dictionary that represent the workflow run metadata.
    :return is_valid: whether the workflow run is valid or not.
    """
    is_valid = False
    failed_actions = workflow_run["Statistics"]["FailedActions"]
    run_state = workflow_run["WorkflowRunProperties"].get("run_state", "STARTED")
    # No failed jobs and workflow run has been completed.
    if failed_actions == 0 and run_state == "COMPLETED":
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


def get_valid_workflow_runs(workflow_name, job_name="profile-dvault-job-dev"):
    """
    Return all valid workflow runs from CloudWatch by iterating through pages.

    :param workflow_name: name of the workflow to capture.
    :param job_name: data profiling job name.
    :return valid_workflow_runs: list of valid Glue workflows.
    """
    glue = boto3.client("glue")
    valid_workflow_runs = []
    try:
        all_workflow_runs = glue.get_workflow_runs(
            Name=workflow_name, IncludeGraph=True
        )
    except:
        logger.warn(f"No runs for workflow {workflow_name}")
        return []
    for workflow_run in all_workflow_runs["Runs"]:
        if _is_workflow_run_valid(workflow_run):
            logger.info(f'{workflow_run["WorkflowRunId"]} is valid.')
            workflow_details = _extract_workflow_details(workflow_run, job_name)
            valid_workflow_runs.append(workflow_details)
        else:
            logger.info(f'{workflow_run["WorkflowRunId"]} is NOT valid.')
    next_token = all_workflow_runs.get("NextToken", None)
    while next_token is not None:
        all_workflow_runs = glue.get_workflow_runs(
            Name=workflow_name, IncludeGraph=True, NextToken=next_token
        )
        for workflow_run in all_workflow_runs["Runs"]:
            if _is_workflow_run_valid(workflow_run):
                logger.info(f'{workflow_run["WorkflowRunId"]} is valid.')
                workflow_details = _extract_workflow_details(workflow_run, job_name)
                valid_workflow_runs.append(workflow_details)
            else:
                logger.info(f'{workflow_run["WorkflowRunId"]} is NOT valid.')
        next_token = all_workflow_runs.get("NextToken", None)
    return valid_workflow_runs


def get_log_entries(
    workflow_run_details, log_group_name="/aws-glue/python-jobs/output"
):
    """
    Extract log entries from the PROFILER and attach them to the workflow details.

    :param workflow_run_details: information releted to all successful workflows for Shape ETL.
    :param log_group_name: group of logs used by CloudWatch.
    :return workflow_run_details: enhanced workflow details with raw log entries.
    """
    logs = boto3.client("logs")
    for workflow_detail in workflow_run_details:
        logger.info(f'Processing {workflow_detail["workflow_run_id"]}')
        log_entries = []
        response = logs.get_log_events(
            logGroupName=log_group_name, logStreamName=workflow_detail["job_run_id"]
        )
        for event in response["events"]:
            if "- root - INFO - PROFILER -" in event["message"][:60]:
                log_entries.append(event["message"])
        next_token = response.get("nextForwardToken", None)
        while next_token is not None:
            logger.info("Go to next set of events.")
            response = logs.get_log_events(
                logGroupName=log_group_name,
                logStreamName=workflow_detail["job_run_id"],
                nextToken=next_token,
                startFromHead=True,
            )
            for event in response["events"]:
                if "- root - INFO - PROFILER -" in event["message"][:60]:
                    log_entries.append(event["message"])
            new_next_token = response.get("nextForwardToken", None)
            if next_token == new_next_token:
                next_token = None
            else:
                next_token = new_next_token
            logger.info(f"Next token: {next_token}")
        logger.info(f"Fetched {len(log_entries)} logs enties.")
        workflow_detail["log_entries"] = log_entries
    return workflow_run_details


def format_log_entries(log_entries):
    """
    Process log entries in a nicer format.

    :param log_entries: raw log entries for each dvault event.
    :return new_logs: newly formatted logs.
    """
    new_logs = []
    for e in log_entries:
        for le in e["log_entries"]:
            le_arr = le.split("|")
            new_logs.append(
                {
                    "workflow_run_id": e["workflow_run_id"],
                    "job_run_id": e["job_run_id"],
                    "timestamp": datetime.strptime(
                        le_arr[0].split(" - ")[0], "YYYY-MM-DD hh:mm:ss[.nnn]"
                    ),
                    "event_id": le_arr[0].split(" - ")[-1].split(":")[-1],
                    "passed": le_arr[1].split(":")[-1],
                    "dvault_filename": le_arr[2].split(":")[-1],
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
    es_url="https://search-ai-elasticsearch-6-public-whkzoh3jmwiwidqwvzag2jxse4.us-east-1.es.amazonaws.com",
    index_name="dvault_logs",
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
    workflow_name = run_props["workflow_name"]
    workflow_run_id = run_props["workflow_run_id"]
    logger.info("Get all workflow runs.")
    workflow_runs = get_valid_workflow_runs(workflow_name)
    if len(workflow_runs) == 0:
        logger.warn(f"No available runs for workflow: {workflow_name}")
        glue = boto3.client("glue")
        response = glue.stop_workflow_run(Name=workflow_name, RunId=workflow_run_id)
    else:
        logger.info("Get all log entries.")
        log_entries = get_log_entries(workflow_runs)
        logger.info("Format logs.")
        formatted_log_entries = format_log_entries(log_entries)
        logger.info("Write logs into ES.")
        send_log_to_es(formatted_log_entries)
    return


if __name__ == "__main__":
    main()
