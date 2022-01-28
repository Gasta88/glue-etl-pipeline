from pyspark.sql import SparkSession
import unittest
import warnings
from shape_dvaults_etl.convert_to_parquet import create_parquet
import os
import glob

TEST_DATA_DIR = "test/unit_tests/data/convert_to_parquet"
MEDIA_BUCKETNAME = "shape-media-library-staging"


class ConvertToParquetTestCase(unittest.TestCase):
    """Test suite for first step in Glue Workflow."""

    maxDiff = None

    def setUp(self):
        """Initialize the test settings."""
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        self.spark = SparkSession.builder.master("local").getOrCreate()
        self.spark.sparkContext.setLogLevel("FATAL")
        self.dest_folder = os.mkdir(f"{TEST_DATA_DIR}/dest")
        self.ALL_JSONS = [
            f for f in glob.glob(f"{TEST_DATA_DIR}/*") if os.path.isfile(f)
        ]
        self.table_names = [
            "HEADLINE_PRED",
            "HEADLINE_EVENT",
            "STE_PRED",
            "STE_EVENT",
            "SUMMARIZER_PRED",
            "SUMMARIZER_EVENT",
        ]

    def tearDown(self):
        """Remove test settings."""
        self.spark.stop()

    def test_create_parquet(self):
        """Test shape_dvaults_etl.glue_workflow_jobs.convert_to_parquet.create_parquet method."""
        for table_name in self.table_names:
            parquet_filename = f"{self.dest_folder}/{table_name}.parquet"
            create_parquet(
                self.spark, table_name, parquet_filename, TEST_DATA_DIR, self.ALL_JSONS
            )
            df = self.spark.read.parquet(parquet_filename)
            self.assertTrue(len(df.columns) > 0)
            self.asserTrue(df.count() > 0)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=3)
    unittest.main(testRunner=runner)
