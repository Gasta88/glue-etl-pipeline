from awsglue.context import GlueContext
from pyspark.context import SparkContext
import unittest
import warnings
from shape_dvaults_etl.convert_to_parquet import create_parquet
import os
import shutil

TEST_DATA_DIR = "test/data/convert_to_parquet"
MEDIA_BUCKETNAME = "shape-media-library-staging"


class ConvertToParquetTestCase(unittest.TestCase):
    """Test suite for first step in Glue Workflow."""

    def setUp(self):
        """Initialize the test settings."""
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        sc = SparkContext.getOrCreate()
        glueContext = GlueContext(sc)
        self.spark = glueContext.spark_session
        self.spark.sparkContext.setLogLevel("ERROR")
        self.dest_folder = os.mkdir(f"{TEST_DATA_DIR}/dest")
        self.ALL_JSONS = [f for f in os.listdir(TEST_DATA_DIR) if os.path.isfile(f)]
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
        shutil.rmtree(self.dest_folder)

    def test_create_paruet(self):
        """Test shape_dvaults_etl.glue_workflow_jobs.convert_to_parquet.create_parquet method."""
        for table_name in self.table_names:
            parquet_filename = f"{self.dest_folder}/{table_name}.parquet"
            create_parquet(self.spark, table_name, parquet_filename)
            df = self.spark.read.parquet(parquet_filename)
            self.assertTrue(len(df.columns) > 0)
            self.asserTrue(df.count() > 0)
