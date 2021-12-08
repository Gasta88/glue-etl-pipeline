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