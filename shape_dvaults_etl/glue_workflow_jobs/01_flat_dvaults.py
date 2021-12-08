import json
import boto3


def flatten_data(y):
    out = {}

    def flatten(x, name=""):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + "_")
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + "_")
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out


def split_files(bucket, obj_key):
    predictions_arr = {"summarizer": [], "headline": [], "ste": []}
    events_arr = {"summarizer": [], "headline": [], "ste": []}
    content = []
    obj = bucket.Object(obj_key)
    obj.download_file("/tmp/tmp_file")
    with open("/tmp/tmp_file") as f:
        content = f.readlines()
    content = content[0].replace('}{"version"', '}${"version"')
    for el in content.split("}}$"):
        # remove Luca's legacy tests
        if "hello from vcoach" in el:
            continue
        # last element in array already have "}}". No need to attach it.
        if el[-2:] != "}}":
            el = el + "}}"
        try:
            flat_el = flatten_data(json.loads(el))
            if flat_el["detail-type"] == "DVaultPredictionEvent":
                predictions_arr[flat_el["detail_prediction_service"]].append(flat_el)
            elif flat_el["detail-type"] == "DVaultEvaluationEvent":
                service_name = flat_el["detail_evaluation_prediction_id"].split("#")[-1]
                events_arr[service_name].append(flat_el)
            else:
                e = f'Unrecognized event type inside file: {flat_el["detail-type"]}'
                raise e
        except Exception as e:
            raise e
    return (predictions_arr, events_arr)


s3 = boto3.resource("s3", region_name="us-east-1")
bucket = s3.Bucket("dvault-fg-test")
all_objkeys = [obj.key for obj in list(bucket.objects.all())]

for obj_key in all_objkeys:
    raw_bucketname = "dvault-fg-test"
    key = obj_key
    output_path = (
        "/home/jupyter/jupyter_default_dir/data/flat_json"  # change to prefix in bucket
    )
    file_name = key.split("/")[-1]

    s3 = boto3.resource("s3", region_name="us-east-1")
    bucket = s3.Bucket(raw_bucketname)
    try:
        predictions_arr, events_arr = split_files(bucket, key)
    except:
        print(obj_key)
    for service_name, predictions in predictions_arr.items():
        if len(predictions) > 0:
            output_key = (
                f"{output_path}/predictions/{file_name}_{service_name.upper()}.jsonl"
            )
            with open(output_key, "w") as outfile:
                for entry in predictions:
                    json.dump(entry, outfile)
                    outfile.write("\n")
            # TODO: upload to bucket
    for service_name, events in events_arr.items():
        if len(events) > 0:
            output_key = (
                f"{output_path}/events/{file_name}_{service_name.upper()}.jsonl"
            )
            with open(output_key, "w") as outfile:
                for entry in events:
                    json.dump(entry, outfile)
                    outfile.write("\n")
            # TODO: upload to bucket
