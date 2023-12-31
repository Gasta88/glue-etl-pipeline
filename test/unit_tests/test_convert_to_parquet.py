from pyspark.sql import SparkSession
import unittest
import warnings
from ef_ingestion_etl.convert_to_parquet import (
    get_spark_dataframe,
    get_refined_dataframe,
)
import os
import glob
import shutil
import logging


TEST_DATA_DIR = "test/unit_tests/data/convert_to_parquet"
MEDIA_BUCKETNAME = "media-library-staging"
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
            "MICROTWO_PRED",
            "MICROTWO_EVENT",
            "MICROTHREE_PRED",
            "MICROTHREE_EVENT",
            "MICROONE_PRED",
            "MICROONE_EVENT",
        ]
        self.sql_dict = {
            "MICROTWO_PRED": """
                            select
                            account,
                            detail.id as id,
                            detail.partitionkey as partition_key,
                            detail.prediction.service as service,
                            detail.prediction.service_version as service_version,
                            detail.prediction.timestamp as unix_timestamp,
                            detail.prediction.shape_id as shape_id,
                            detail.prediction.input.transcript as transcript,
                            detail.prediction.output.microtwo as headline,
                            time as date_time
                            from microtwo_pred
                        """,
            "MICROTWO_EVENT": """
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
                            from microtwo_event
                        """,
            "MICROTHREE_PRED": """
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
                            from microthree_pred
                        """,
            "MICROTHREE_EVENT": """
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
                            detail.evaluation.payload.search_terms as payload_search_terms,
                            detail.evaluation.payload.media_id as payload_media_id,
                            detail.evaluation.payload.media_type as payload_media_type,
                            detail.evaluation.payload.medialib as payload_medialib,
                            detail.evaluation.payload.search_match as payload_search_match,
                            detail.evaluation.payload.tags as payload_tags,
                            detail.evaluation.payload.caption as payload_caption,
                            time as date_time
                            from microthree_event
                        """,
            "MICROONE_PRED": """
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
                            from microone_pred
                        """,
            "MICROONE_EVENT": """
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
                            from microone_event
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

        self.assertTrue(len(dfs["MICROTWO_PRED"].columns) > 0)
        self.assertTrue(len(dfs["MICROTWO_EVENT"].columns) > 0)
        self.assertTrue(len(dfs["MICROTHREE_PRED"].columns) > 0)
        self.assertTrue(len(dfs["MICROTHREE_EVENT"].columns) > 0)
        self.assertTrue(len(dfs["MICROONE_PRED"].columns) > 0)
        self.assertTrue(len(dfs["MICROONE_EVENT"].columns) > 0)

        self.assertTrue(dfs["MICROTWO_PRED"].count() > 0)
        self.assertTrue(dfs["MICROTWO_EVENT"].count() > 0)
        self.assertTrue(dfs["MICROTHREE_PRED"].count() > 0)
        self.assertTrue(dfs["MICROTHREE_EVENT"].count() > 0)
        self.assertTrue(dfs["MICROONE_PRED"].count() > 0)
        self.assertTrue(dfs["MICROONE_EVENT"].count() > 0)

    def test_get_refined_dataframe(self):
        """Test shape_dvaults_etl.convert_to_parquet.get_refined_dataframe method."""
        # microtwo event
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/events/ef-prod-stream-1-2022-04-27-15-07-12-731903ee-9d63-47fe-b7ae-b5e4aa2f8a80_CLEAN_MICROTWO.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "MICROTWO_EVENT"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # microtwo pred
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/predictions/ef-prod-stream-1-2022-03-04-18-40-16-65ec32bc-83a5-4fcc-a113-b731b40aee97_CLEAN_MICROTWO.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "MICROTWO_PRED"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # MICROTHREE event
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/events/ef-prod-stream-1-2022-03-04-18-40-16-65ec32bc-83a5-4fcc-a113-b731b40aee97_CLEAN_MICROTHREE.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "MICROTHREE_EVENT"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # MICROTHREE pred
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/predictions/ef-prod-stream-1-2022-03-04-18-40-16-65ec32bc-83a5-4fcc-a113-b731b40aee97_CLEAN_MICROTHREE.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "MICROTHREE_PRED"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # MICROONE event
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/events/ef-prod-stream-1-2022-04-19-18-20-03-193a495d-f9a1-4289-ad92-ec3235140511_CLEAN_MICROONE.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "MICROONE_EVENT"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)

        # MICROONE pred
        df = self.spark.read.json(
            "test/unit_tests/data/convert_to_parquet/predictions/ef-prod-stream-1-2022-03-04-18-40-16-65ec32bc-83a5-4fcc-a113-b731b40aee97_CLEAN_MICROONE.jsonl"
        )
        refined_df = get_refined_dataframe(
            self.spark, df, self.sql_dict, "MICROONE_PRED"
        )

        self.assertTrue(len(refined_df.columns) > 0)
        self.assertTrue(refined_df.count() > 0)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=3)
    unittest.main(testRunner=runner)
