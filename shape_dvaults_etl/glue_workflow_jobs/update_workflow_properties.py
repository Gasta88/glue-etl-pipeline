import boto3
import sys
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(
    sys.argv, ["WORKFLOW_NAME", "WORKFLOW_RUN_ID", "transition_state"]
)
workflow_name = args["WORKFLOW_NAME"]
workflow_run_id = args["WORKFLOW_RUN_ID"]
transition_state = args["transition_state"]
# dvault_name = args["dvault_name"]


glue = boto3.client("glue")
state_to_set = transition_state

run_properties = glue.get_workflow_run_properties(
    Name=workflow_name, RunId=workflow_run_id
)["RunProperties"]
run_properties["run_state"] = state_to_set
# run_properties["dvault_name"] = dvault_name

glue.put_workflow_run_properties(
    Name=workflow_name, RunId=workflow_run_id, RunProperties=run_properties
)
