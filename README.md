[![coverage report](https://git.docebo.info/ai/shape-dvault/badges/<branch>/coverage.svg)](https://git.docebo.info/ai/shape-dvault/commits/<branch>)

# Shape dvaults ETL pipeline

## Purpose/Goals

Shape is one of the application that compose the Docebo Learning Suite. In a nutshell, it can take several media formats and create meterials for courses and presentations on demand thanks to the use of several AI models coupled together. The tool is maintained by the _shape-ai_ team, but the models beneath are developed by the AI team.

This project will help to collect the dvaults, files generated by the Shape application, and present them in a useful way to the data scientists of the AI team so that they can make educated guesses on the current models performances and/or initiate models re-training.

### Dvaults:

A _dvault_ is a highly nested JSON file that is generated by one of the AI services that is used in the Shape application. These services are:

- Summarizer
- Headline
- STE
- Semantic Image Matcher

More can be added in the future and each one of them present some common attributes, while others are very specific to the service.
Furthermore, the dvaults can be divided between **predictions** (generated by the AI service) or **events** (generated by the user actions on the Shape application).

More details are available on the [dvault Confluence page](https://docebo.atlassian.net/wiki/spaces/AI/pages/1698332715/D-Vault+events).

## Pipeline design

![shape dvault pipeline](ShapeDvaultGitlabSchema.png "Shape DVault Pipeline")

### Data assumptions

- The dvault files arrive a the _source_ bucket already decoded.
- Data profiling is carried on batches of events, which are exploded on the fly to make sure that data expectations are met. Successful events are collected in _data/clean_dvaults_, while problematic events are stored in _data/dirty_dvaults_.
- Data exception must be investigated manually. Manual re-upload has to be done at the _source_ bucket.
- Media files might be missing from STE events due to the nature of the user action.
- At minimum the dvault must have the following fields:
  - identifier for either **prediction** or **event**.
  - identifier for the service of origin
- Parquet are appended and queries via Jupyter notebook by the data scientist. If there is a schema change, the files must be re-processed all together.

### Final parquet files

Each parquet file in _data/clean_parquet_ holds data for an individual AI service involved in Shape. Each AI service is divided in **prediction** and **event**.

Therefore the tables so far are:

- HEADLINER_EVENT
- HEADLINER_PRED
- STE_EVENT
- STE_PRED
- SUMMARIZER_EVENT
- SUMMARIZER_PRED
- SIM_EVENT

In the first version of the ETL pipeline, the data scientist must investigate the content of the parquet files and decide which data should be deserialized fromt he dvault structure. Down the line, it will be useful to integrate ML model re-training pipelines to these files to automate the training/deployment process of new model versions.

### Data observability

In order to keep an eye into the data movement inside the ETL pipeline, the final step of a succesful workflow run is to load the data-profiling logs into an [ElastichSearch cluster](https://search-ai-elasticsearch-6-public-whkzoh3jmwiwidqwvzag2jxse4.us-east-1.es.amazonaws.com).

A Kibana board is provided to inspect common metrics while data is profiled inside the pipeline. The index name inside ElasticSeach is _dvault*logs*{env}_, where _{env}_ represent the differnet version of the pipeline (ex: dev, prod, e2e-test).

## Future improvements

**TBD**

## Testing the pipeline

At the current state, the project is tested via CI/CD pipeline in Gitlab. Tests are allocated in _test/_ folder.

Two types of tests are run:

- Unit tests.
- End-to-end tests.

### Unit testing:

The unit testing of the project occurs at two levels:

- Terraform plan output.
- Glue Job scripts.

Inside the CI/CD pipeline, on can use the command `./push_tags.sh unit-test` to run just these type of tests inside the project.

### End to end testing:

The E2E testing performed inside the project comprise a dev deployment of the infrastructure in AWS, along with a helping script located in _test/end_to_end_tests/run_e2e_test.py_ to perform these actions:

- Upload testing input from _test/end_to_end_tests/data/input_ into AWS.
- Start Glue workflow via boto3.
- Wait until the workflow has processed the files.
- Compare content of final Parquet files with expected results in _test/end_to_end_tests/data/expected_.

If final and expected files are different in their own content, the job fails.
