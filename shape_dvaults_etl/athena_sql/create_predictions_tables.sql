/*HEADLINE PREDICTION INPUT*/
create external table if not exists dvault_fg_test.headline_pred_input (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_prediction_template_dvault_version VARCHAR(5),
	detail_prediction_service_version_software VARCHAR(10),
	detail_prediction_service_version_model VARCHAR(15),
	detail_prediction_input_transcript VARCHAR(250)
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/HEADLINE_PRED_INPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*HEADLINE PREDICTION OUTPUT*/
create external table if not exists dvault_fg_test.headline_pred_output (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_prediction_template_dvault_version VARCHAR(5),
	detail_prediction_service_version_software VARCHAR(10),
	detail_prediction_service_version_model VARCHAR(15),
	event INT,
	headline STRING	
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/HEADLINE_PRED_OUTPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*STE PREDICTION INPUT*/
create external table if not exists dvault_fg_test.ste_pred_input (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_prediction_template_dvault_version VARCHAR(5),
	detail_prediction_service_version_software VARCHAR(10),
	detail_prediction_service_version_model VARCHAR(15),
	detail_prediction_context_paragraph INT,
    detail_prediction_context_sentence INT,
    detail_prediction_input_paragraph STRING
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/STE_PRED_INPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*STE PREDICTION OUTPUT*/
create external table if not exists dvault_fg_test.ste_pred_output (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_prediction_template_dvault_version VARCHAR(5),
	detail_prediction_service_version_software VARCHAR(10),
	detail_prediction_service_version_model VARCHAR(15),
	detail_prediction_context_paragraph INT,
    detail_prediction_context_sentence INT,
    detail_prediction_output_sentence STRING,
    event INT,
    search_term STRING,
    score DOUBLE
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/STE_PRED_OUTPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*SUMMARIZER PREDICTION INPUT*/
create external table if not exists dvault_fg_test.summarizer_pred_input (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_prediction_template_dvault_version VARCHAR(5),
	detail_prediction_service_version_software VARCHAR(10),
	detail_prediction_service_version_model VARCHAR(15),
	detail_prediction_input_reduction_percentage DOUBLE,
	event INT,
	sentence STRING,
	score DOUBLE,
	paragraph STRING
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/SUMMARIZER_PRED_INPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*SUMMARIZER PREDICTION OUTPUT*/
create external table if not exists dvault_fg_test.summarizer_pred_output (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_prediction_template_dvault_version VARCHAR(5),
	detail_prediction_service_version_software VARCHAR(10),
	detail_prediction_service_version_model VARCHAR(15),
	detail_prediction_input_reduction_percentage DOUBLE,
	event INT,
	summary_sentence STRING,
    filtered_sentences ARRAY<STRING>,
    scores ARRAY<DOUBLE>,
    idx INT,
    skipped_paragraphs_flag INT
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/SUMMARIZER_PRED_OUTPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*HEADLINE EVENT*/
create external table if not exists dvault_fg_test.headline_event (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_type VARCHAR(25),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_evaluation_template_dvault_version VARCHAR(5),
	detail_evaluation_id VARCHAR(40),
	detail_evaluation_shape_id VARCHAR(40),
	detail_evaluation_prediction_id VARCHAR(50),
	detail_evaluation_timestamp TIMESTAMP,
	detail_evaluation_reporter VARCHAR(10),
	detail_evaluation_type VARCHAR(20),
	detail_evaluation_payload_text STRING,
	detail_tags_region VARCHAR(15)
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/HEADLINE_EVENT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*STE EVENT INPUT*/
create external table if not exists dvault_fg_test.ste_event_input (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_evaluation_template_dvault_version VARCHAR(5),
	detail_evaluation_reporter VARCHAR(15),
	detail_evaluation_type VARCHAR(25)
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/STE_EVENT_INPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*STE EVENT OUTPUT*/
create external table if not exists dvault_fg_test.ste_event_output (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	text STRING,
	query ARRAY<STRING>,
	media_lib VARCHAR(20),
	media_id STRING,
	media_type VARCHAR(50),
	caption STRING,
	slide VARCHAR(10),
	search_match INT,
	image_tags ARRAY<STRING>,
	search_terms STRING
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/STE_EVENT_OUTPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*SUMMARIZER EVENT INPUT*/
create external table if not exists dvault_fg_test.summarizer_event_input (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_evaluation_template_dvault_version VARCHAR(10),
	detail_evaluation_reporter VARCHAR(10),
	detail_evaluation_type VARCHAR(20)
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/SUMMARIZER_EVENT_INPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");

/*SUMMARIZER EVENT OUTPUT*/
create external table if not exists dvault_fg_test.summarizer_event_output (
	version VARCHAR(3),
	id VARCHAR(30),
	`detail-type` VARCHAR(25),
	source VARCHAR(15),
	account VARCHAR(15),
	`time` VARCHAR(15),
	region VARCHAR(10),
	detail_id VARCHAR(80),
	detail_timestamp TIMESTAMP, 
	detail_partitionKey VARCHAR(80),
	detail_evaluation_payload_paragraph INT,
	detail_evaluation_payload_slide VARCHAR(10),
	text STRING
)
STORED AS PARQUET
LOCATION 's3://dvault-fg-test/data/clean-parquet/SUMMARIZER_EVENT_OUTPUT.parquet/'
tblproperties ("parquet.compress"="SNAPPY");