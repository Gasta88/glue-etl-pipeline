import boto3
import sys
from awsglue.utils import getResolvedOptions
import logging

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Get run properties for the Glue workflow.")


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


def get_processed_efs(workflow_name):
    """
    Return list of event files that have been already processed.

    :param workflow_name: name of the Glue workflow.
    :return events: list of event file names.
    """
    glue = boto3.client("glue")
    event_arrs = []
    logger.info("Get event files already processed by older workflow runs.")
    try:
        workflow_runs = glue.get_workflow_runs(Name=workflow_name)
    except:
        logger.info(f"No runs for workflow {workflow_name}")
        return []
    for run in workflow_runs["Runs"]:
        # Get event files only if workflow run has run completelly, otherwise skip it.
        if _is_workflow_run_valid(run):
            event_arrs.append(run["WorkflowRunProperties"]["event_files"].split(";"))
    next_token = workflow_runs.get("NextToken", None)
    while next_token is not None:
        workflow_runs = glue.get_workflow_runs(Name=workflow_name, NextToken=next_token)
        for run in workflow_runs["Runs"]:
            # Get event files only if workflow run has run completelly, otherwise skip it.
            if _is_workflow_run_valid(run):
                event_arrs.append(
                    run["WorkflowRunProperties"]["event_files"].split(";")
                )
        next_token = workflow_runs.get("NextToken", None)
    events = [item for sublist in event_arrs for item in sublist]
    logger.info(f"Found {len(events)} old event files.")
    return events


def get_efs_from_source(source_bucketname):
    """
    Return list of event files ready to be processed from S3 source bucket.

    :param source_bucketname: name of source S3 bucket.
    :return events: list of event file names.
    """
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(source_bucketname)
    events = []
    logger.info("Get all available event files.")
    events = [f"{source_bucketname}/{obj.key}" for obj in bucket.objects.all()]
    logger.info(f"Found {len(events)} new event files.")
    return events


def get_efs_from_s3(landing_bucketname):
    """
    Return list of event files ready to be processed from S3 landing bucket.
    only for end-to-end test run via CI/CD pipelines

    :param source_bucketname: name of source S3 bucket.
    :return events: list of event file names.
    """
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(landing_bucketname)
    events = []
    logger.info("Get all available event files.")
    events = [
        f"{landing_bucketname}/{obj.key}"
        for obj in bucket.objects.filter(Prefix="data/raw/")
    ]
    logger.info(f"Found {len(events)} new event files.")
    return events


def main():
    """
    Run main steps in the update_workflow_properties Glue Job.
    """
    args = getResolvedOptions(
        sys.argv,
        ["WORKFLOW_NAME", "WORKFLOW_RUN_ID", "transition_state"],
    )
    workflow_name = args["WORKFLOW_NAME"]
    workflow_run_id = args["WORKFLOW_RUN_ID"]
    state_to_set = args["transition_state"]
    env = (
        f'e2e-{args["WORKFLOW_NAME"].split("-")[-1]}'
        if args["WORKFLOW_NAME"].split("-")[-1] == "test"
        else args["WORKFLOW_NAME"].split("-")[-1]
    )

    logger.info(f"Setting workflow  state to {state_to_set}.")

    glue = boto3.client("glue")

    run_properties = glue.get_workflow_run_properties(
        Name=workflow_name, RunId=workflow_run_id
    )["RunProperties"]

    run_properties["run_state"] = state_to_set
    if state_to_set == "STARTED":
        # Handle different behaviour when running PROD pipeline against E2E-TEST pipeline
        if env == "e2e-test":
            new_event_files = get_efs_from_s3(run_properties["landing_bucketname"])
        else:
            new_event_files = get_efs_from_source(run_properties["source_bucketname"])
        # If no new events are to be processed, do not start the workflow.
        if len(new_event_files) == 0:
            logger.info("No new event files in S3 bucket.")
            response = glue.stop_workflow_run(Name=workflow_name, RunId=workflow_run_id)
        else:
            old_event_files = get_processed_efs(workflow_name)
            # If no old processed events are available, use the new ones only.
            if len(old_event_files) == 0:
                logger.info("No old event files are available.")
                event_files = new_event_files
                event_files.sort()
            else:
                logger.info("Compare new against old set of event files.")
                new_event_files.sort()
                old_event_files.sort()
                event_files = [f for f in new_event_files if f not in old_event_files]
            # AWS Glue Workflow has a max 64KB per parameter, therefore only 500 files each time.
            logger.info(event_files)
            if len(event_files) == 0:
                logger.info("No pending event files are available.")
                response = glue.stop_workflow_run(
                    Name=workflow_name, RunId=workflow_run_id
                )
            else:
                run_properties["event_files"] = ";".join(event_files[:500])

    logger.info("Set new set of run_properties")
    glue.put_workflow_run_properties(
        Name=workflow_name, RunId=workflow_run_id, RunProperties=run_properties
    )


if __name__ == "__main__":
    main()
