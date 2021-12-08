import os
import json
import os
import re
import boto3

# Inputs to change inthe Glue Job context
preds_rootpath = "/home/jupyter/jupyter_default_dir/data/flat_json/predictions"
input_destpath = "/home/jupyter/jupyter_default_dir/data/split_json/prediction_input"
output_destpath = "/home/jupyter/jupyter_default_dir/data/split_json/prediction_output"
for pred_file in filtered_flat_jsons:
    if pred_file.endswith("_STE.jsonl") and "predictions" in pred_file:
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
            "detail_prediction_template_dvault_version",
            "detail_prediction_service_version_software",
            "detail_prediction_service_version_model",
            "detail_prediction_context_paragraph",
            "detail_prediction_context_sentence",
        ]
        ste_input_cols = metadata_cols + ["detail_prediction_input_paragraph"]
        ste_output_cols = metadata_cols + [
            "detail_prediction_output_sentence",
            "detail_prediction_output_search_terms",
            "detail_prediction_output_scores",
        ]
        CLEANR = re.compile("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")

        content = []
        with open(pred_file, "r") as f:
            content = f.readlines()

        input_list = []
        for line in content:
            element = json.loads(line)
            # prepare input
            input_data = {}
            input_data = {
                key: element.get(key) for key in ste_input_cols if key in element
            }
            input_data["detail_prediction_input_paragraph"] = re.sub(
                CLEANR, "", input_data.get("detail_prediction_input_paragraph", "")
            )
            input_list.append(input_data)

        file_name = os.path.join(
            input_destpath, pred_file.split("/")[-1][:-6] + "_PRED_INPUT.jsonl"
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
                key: element.get(key) for key in ste_output_cols if key in element
            }
            # I don't need the exact column names, but the number of instances for each output column
            output_cols = [
                key
                for key in element
                if key.startswith("detail_prediction_output_scores_")
            ]
            for i, _ in enumerate(output_cols):
                tmp_data = {}
                tmp_data = dict(output_data)
                tmp_data["detail_prediction_output_sentence"] = re.sub(
                    CLEANR, "", tmp_data["detail_prediction_output_sentence"]
                )
                tmp_data["event"] = i
                tmp_data["search_term"] = element.get(
                    f"detail_prediction_output_search_terms_{i}", None
                )
                tmp_data["score"] = element.get(
                    f"detail_prediction_output_scores_{i}", None
                )
                output_list.append(tmp_data)

        file_name = os.path.join(
            output_destpath, pred_file.split("/")[-1][:-6] + "_PRED_OUTPUT.jsonl"
        )
        with open(file_name, "w") as outfile:
            for entry in output_list:
                json.dump(entry, outfile)
                outfile.write("\n")
        # TODO: upload to bucket
