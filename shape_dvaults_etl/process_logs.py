import boto3
import logging
import sys
import json
from elasticsearch import Elasticsearch

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


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
        logger.info(f'Processing {workflow_detail["workflow_run_id"]}..')
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
            logger.info(f"Next tken: {next_token}")
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
                    "timestamp": le_arr[0].split(" - ")[0],
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


def main():
    """
    Run main steps in the process_logs Glue Job.
    """
    workflow_name = "s3-batch-glue-dvault-workflow-dev"
    logger.info("Get all workflow runs.")
    workflow_runs = get_valid_workflow_runs(workflow_name)
    logger.info("Get all log entries.")
    log_entries = get_log_entries(workflow_runs)
    logger.info("Format logs.")
    formatted_log_entries = format_log_entries(log_entries)
    logger.info("Write logs into file.")
    with open(
        "/Users/francesco.gastaldello/Documents/tutorials/kibana_es_experiments/data/log_dump.jsonl",
        "w",
    ) as outfile:
        for le in formatted_log_entries:
            outfile.write(json.dumps(le))
            outfile.write("\n")
    return


if __name__ == "__main__":
    main()
