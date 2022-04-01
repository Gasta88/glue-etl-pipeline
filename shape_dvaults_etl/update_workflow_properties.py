import boto3
import sys
from awsglue.utils import getResolvedOptions
import logging
import os

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


def get_processed_dvaults(workflow_name):
    """
    Return list of dvault files that have been already processed.

    :param workflow_name: name of the Glue workflow.
    :return dvaults: list of dvault file names.
    """
    glue = boto3.client("glue")
    dvault_arrs = []
    logger.info("Get dvault files already processed by older workflow runs.")
    try:
        workflow_runs = glue.get_workflow_runs(Name=workflow_name)
    except:
        logger.info(f"No runs for workflow {workflow_name}")
        return []
    for run in workflow_runs["Runs"]:
        # Get dvault files only if workflow run has run completelly, otherwise skip it.
        if _is_workflow_run_valid(run):
            dvault_arrs.append(run["WorkflowRunProperties"]["dvault_files"].split(";"))
    next_token = workflow_runs.get("NextToken", None)
    while next_token is not None:
        workflow_runs = glue.get_workflow_runs(Name=workflow_name, NextToken=next_token)
        for run in workflow_runs["Runs"]:
            # Get dvault files only if workflow run has run completelly, otherwise skip it.
            if _is_workflow_run_valid(run):
                dvault_arrs.append(
                    run["WorkflowRunProperties"]["dvault_files"].split(";")
                )
        next_token = workflow_runs.get("NextToken", None)
    dvaults = [item for sublist in dvault_arrs for item in sublist]
    logger.info(f"Found {len(dvaults)} old dvaults.")
    return dvaults


def get_dvaults_from_source(source_bucketname):
    """
    Return list of dvault files ready to be processed from S3 source bucket.

    :param source_bucketname: name of source S3 bucket.
    :return dvaults: list of dvault file names.
    """
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(source_bucketname)
    dvaults = []
    logger.info("Get all available dvault files.")
    dvaults = [f"{source_bucketname}/{obj.key}" for obj in bucket.objects.all()]
    logger.info(f"Found {len(dvaults)} new dvaults.")
    return dvaults


def get_dvaults_from_s3(landing_bucketname):
    """
    Return list of dvault files ready to be processed from S3 landing bucket.
    only for end-to-end test run via CI/CD pipelines

    :param source_bucketname: name of source S3 bucket.
    :return dvaults: list of dvault file names.
    """
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(landing_bucketname)
    dvaults = []
    logger.info("Get all available dvault files.")
    dvaults = [f"{landing_bucketname}/{obj.key}" for obj in bucket.objects.all()]
    logger.info(f"Found {len(dvaults)} new dvaults.")
    return dvaults


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

    logger.info(f"Setting workflow  state to {state_to_set}.")

    glue = boto3.client("glue")

    run_properties = glue.get_workflow_run_properties(
        Name=workflow_name, RunId=workflow_run_id
    )["RunProperties"]

    run_properties["run_state"] = state_to_set
    if state_to_set == "STARTED":
        # Handle different behaviour when running PROD pipeline against CI_CD pipeline
        ci_cd = os.environ.get("CI_CD", None)
        if ci_cd is not None:
            new_dvault_files = get_dvaults_from_source(
                run_properties["landing_bucketname"]
            )
        else:
            new_dvault_files = get_dvaults_from_source(
                run_properties["source_bucketname"]
            )
        # If no new dvaults are to be processed, do not start the workflow.
        if len(new_dvault_files) == 0:
            logger.info("No new dvault files in S3 bucket.")
            response = glue.stop_workflow_run(Name=workflow_name, RunId=workflow_run_id)
        else:
            old_dvault_files = get_processed_dvaults(workflow_name)
            # If no old processed dvaults are available, use the new ones only.
            if len(old_dvault_files) == 0:
                logger.info("No old dvault files are available.")
                dvault_files = new_dvault_files
                dvault_files.sort()
            else:
                logger.info("Compare new against old set of dvault files.")
                new_dvault_files.sort()
                old_dvault_files.sort()
                dvault_files = [
                    f for f in new_dvault_files if f not in old_dvault_files
                ]
            # AWS Glue Workflow has a max 64KB per parameter, therefore only 500 files each time.
            logger.info(dvault_files)
            if len(dvault_files) == 0:
                logger.info("No pending dvault files are available.")
                response = glue.stop_workflow_run(
                    Name=workflow_name, RunId=workflow_run_id
                )
            else:
                run_properties["dvault_files"] = ";".join(dvault_files[:500])

    logger.info("Set new set of run_properties")
    glue.put_workflow_run_properties(
        Name=workflow_name, RunId=workflow_run_id, RunProperties=run_properties
    )


if __name__ == "__main__":
    main()
