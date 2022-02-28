from pyspark.sql import SparkSession
import unittest
import warnings
from shape_dvaults_etl.convert_to_parquet import (
    get_spark_dataframe,
    get_refined_dataframe,
)
import os
import glob
import shutil
import logging


TEST_DATA_DIR = "test/unit_tests/data/convert_to_parquet"
MEDIA_BUCKETNAME = "shape-media-library-staging"
logging.getLogger("py4j").setLevel(logging.ERROR)


class ConvertToParquetTestCase(unittest.TestCase):
    """Test suite for first step in Glue Workflow."""

    maxDiff = None

    def setUp(self):
        """Initialize the test settings."""
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        self.spark = SparkSession.builder.master("local").getOrCreate()
        self.spark.sparkContext.setLogLevel("FATAL")
        self.dest_folder = f"{TEST_DATA_DIR}/dest"
        os.mkdir(self.dest_folder)
        self.ALL_JSONS = [
            "/".join(f.split("/")[-2:])
            for f in glob.glob(f"{TEST_DATA_DIR}/*/*")
            if os.path.isfile(f)
        ]
        self.table_names = [
            "HEADLINE_PRED",
            "HEADLINE_EVENT",
            "STE_PRED",
            "STE_EVENT",
            "SUMMARIZER_PRED",
            "SUMMARIZER_EVENT",
        ]
        self.sql_dict = {
            "HEADLINE_PRED": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.prediction.service as service,
                            detail.prediction.service_version as service_version,
                            detail.prediction.timestamp as unix_timestamp,
                            detail.prediction.shape_id as shape_id,
                            detail.prediction.input.transcript as transcript,
                            detail.prediction.output.headline as headline,
                            time as date_time
                            from headline_pred
                        """,
            "HEADLINE_EVENT": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.evaluation.prediction_id as prediction_id,
                            detail.evaluation.reporter as reporter,
                            detail.evaluation.type as event_type,
                            detail.evaluation.timestamp as unix_timestamp,
                            detail.evaluation.shape_id as shape_id,
                            detail.evaluation.payload.text as payload_text,
                            time as date_time
                            from headline_event
                        """,
            "STE_PRED": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.prediction.service as service,
                            detail.prediction.service_version as service_version,
                            detail.prediction.timestamp as unix_timestamp,
                            detail.prediction.shape_id as shape_id,
                            detail.prediction.context as context,
                            detail.prediction.input.paragraph as paragraph,
                            detail.prediction.output.scores as scores,
                            detail.prediction.output.search_terms as search_terms,
                            detail.prediction.output.sentence as sentence,
                            time as date_time
                            from ste_pred
                        """,
            "STE_EVENT": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.evaluation.prediction_id as prediction_id,
                            detail.evaluation.reporter as reporter,
                            detail.evaluation.type as event_type,
                            detail.evaluation.timestamp as unix_timestamp,
                            detail.evaluation.shape_id as shape_id,
                            detail.evaluation.payload.text as payload_text,
                            detail.evaluation.payload.query as payload_query,
                            detail.evaluation.payload.media_id as payload_media_id,
                            detail.evaluation.payload.media_type as payload_media_type,
                            detail.evaluation.payload.medialib as payload_medialib,
                            detail.evaluation.payload.tags as payload_tags,
                            detail.evaluation.payload.caption as payload_caption,
                            time as date_time
                            from ste_event
                        """,
            "SUMMARIZER_PRED": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.prediction.service as service,
                            detail.prediction.service_version as service_version,
                            detail.prediction.timestamp as unix_timestamp,
                            detail.prediction.shape_id as shape_id,
                            detail.prediction.input.paragraphs as input_paragraphs,
                            detail.prediction.input.sentences_scores as input_sentences_scores,
                            detail.prediction.output.summary as output_summary,
                            detail.prediction.output.metadata as output_metadata,
                            detail.prediction.output.skipped_paragraphs as output_skipped_paragraphs,
                            time as date_time
                            from summarizer_pred
                        """,
            "SUMMARIZER_EVENT": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.evaluation.prediction_id as prediction_id,
                            detail.evaluation.timestamp as unix_timestamp,
                            detail.evaluation.shape_id as shape_id,
                            detail.evaluation.type as event_type,
                            detail.evaluation.reporter as reporter,
                            detail.evaluation.payload.paragraph as paragraph,
                            detail.evaluation.payload.slide as slide,
                            detail.evaluation.payload.text as text,
                            time as date_time
                            from summarizer_event
                        """,
        }

    def tearDown(self):
        """Remove test settings."""
        shutil.rmtree(self.dest_folder)
        self.spark.stop()

    def test_get_spark_dataframe(self):
        """Test shape_dvaults_etl.convert_to_parquet.get_spark_dataframe method."""
        dfs = {}
        for table_name in self.table_names:
            dfs[table_name] = get_spark_dataframe(
                self.spark, table_name, TEST_DATA_DIR, self.ALL_JSONS
            )

        self.assertTrue(len(dfs["HEADLINE_PRED"].columns) > 0)
        self.assertTrue(len(dfs["HEADLINE_EVENT"].columns) > 0)
        self.assertTrue(len(dfs["STE_PRED"].columns) > 0)
        self.assertTrue(len(dfs["STE_EVENT"].columns) > 0)
        self.assertTrue(len(dfs["SUMMARIZER_PRED"].columns) > 0)
        self.assertTrue(len(dfs["SUMMARIZER_EVENT"].columns) > 0)

        self.assertTrue(dfs["HEADLINE_PRED"].count() > 0)
        self.assertTrue(dfs["HEADLINE_EVENT"].count() > 0)
        self.assertTrue(dfs["STE_PRED"].count() > 0)
        self.assertTrue(dfs["STE_EVENT"].count() > 0)
        self.assertTrue(dfs["SUMMARIZER_PRED"].count() > 0)
        self.assertTrue(dfs["SUMMARIZER_EVENT"].count() > 0)

    def test_get_refined_dataframe(self):
        """Test shape_dvaults_etl.convert_to_parquet.get_refined_dataframe method."""
        # headline event
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/events/dvault-staging-stream-1-2021-11-24-20-38-12-0b9e3c9b-8e2a-4437-8000-9d423632119f_HEADLINE.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "HEADLINE_EVENT"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # headline pred
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/predictions/dvault-staging-stream-1-2021-11-24-00-42-04-e376bb8c-f13d-47f6-8d29-1950ba3a07b2_HEADLINE.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "HEADLINE_PRED"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # STE event
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/events/dvault-staging-stream-1-2021-11-24-16-24-00-d2a1c999-af9f-47bb-88a8-fadedc9c3bc9_STE.jsonl"
        )
        refined_df = get_refined_dataframe(self.spark, df, self.sql_dict, "STE_EVENT")

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # STE pred
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/predictions/dvault-staging-stream-1-2021-11-24-00-48-07-b5fe5db7-776f-42ec-b7e6-e75eb0f4eacf_STE.jsonl"
        )
        refined_df = get_refined_dataframe(self.spark, df, self.sql_dict, "STE_PRED")

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # SUMMARIZER event
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/events/dvault-staging-stream-1-2021-11-24-20-38-12-0b9e3c9b-8e2a-4437-8000-9d423632119f_SUMMARIZER.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "SUMMARIZER_EVENT"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # SUMMARIZER pred
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/predictions/dvault-staging-stream-1-2021-11-24-00-52-48-9999ffa7-b9f6-4cd0-bc57-f6a658caac96_SUMMARIZER.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "SUMMARIZER_PRED"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=3)
    unittest.main(testRunner=runner)
