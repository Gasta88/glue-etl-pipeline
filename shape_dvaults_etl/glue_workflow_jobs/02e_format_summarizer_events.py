import json
import re
import boto3
import os

events_rootpath = "/home/jupyter/jupyter_default_dir/data/flat_json/events"
input_destpath = "/home/jupyter/jupyter_default_dir/data/split_json/event_input"
output_destpath = "/home/jupyter/jupyter_default_dir/data/split_json/event_output"
for event_file in filtered_flat_jsons:
    if event_file.endswith("_SUMMARIZER.jsonl") and "events" in event_file:
        metadata_cols = [
            "version",
            "id",
            "detail-type",
            "source",
            "account",
            "time",
            "region",
            "detail_id",
            "detail_timestamp",
            "detail_partitionKey",
        ]
        summarizer_input_cols = metadata_cols + [
            "detail_evaluation_template_dvault_version",
            "detail_evaluation_reporter",
            "detail_evaluation_type",
        ]
        summarizer_output_cols = metadata_cols + [
            "detail_evaluation_payload_paragraph",
            "detail_evaluation_payload_slide",
        ]
        CLEANR = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")

        content = []
        with open(event_file, "r") as f:
            content = f.readlines()

        input_list = []
        for line in content:
            element = json.loads(line)
            # prepare input
            input_data = {}
            input_data = {
                key: element.get(key) for key in summarizer_input_cols if key in element
            }
            input_list.append(input_data)

        file_name = os.path.join(
            input_destpath, event_file.split("/")[-1][:-6] + "_EVENT_INPUT.jsonl"
        )
        with open(file_name, "w") as outfile:
            for entry in input_list:
                json.dump(entry, outfile)
                outfile.write("\n")
        # TODO: upload to bucket

        output_list = []
        for line in content:
            element = json.loads(line)
            # prepare output
            output_data = {
                key: element.get(key)
                for key in summarizer_output_cols
                if key in element
            }
            output_data["text"] = re.sub(
                CLEANR, "", element.get("detail_evaluation_payload_text", "")
            )
            output_list.append(output_data)

        file_name = os.path.join(
            output_destpath, event_file.split("/")[-1][:-6] + "_EVENT_OUTPUT.jsonl"
        )
        with open(file_name, "w") as outfile:
            for entry in output_list:
                json.dump(entry, outfile)
                outfile.write("\n")
        # TODO: upload to bucket
