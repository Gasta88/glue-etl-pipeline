import boto3
import sys
from awsglue.utils import getResolvedOptions
import logging

# Setup logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Get run properties for the Glue workflow.")
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
    event_id = run_properties["aws:eventIds"][0]
    logger.info(f"Workflow started by event: {event_id}")
    # TODO: extract object key from EventBridge event and store it into the run_properties
    # dictionary

logger.info("Set new set of run_properties")
glue.put_workflow_run_properties(
    Name=workflow_name, RunId=workflow_run_id, RunProperties=run_properties
)
