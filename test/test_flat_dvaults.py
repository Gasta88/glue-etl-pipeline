import boto3
import json
import boto3
import unittest
import warnings
from shape_dvaults_etl.glue_workflow_jobs.01_flat_dvaults import split_files
import os
import shutil

TEST_DATA_DIR = "test/data"
MEDIA_BUCKETNAME = "shape-media-library-staging"

class FlatDvaultTestCase(unittest.TestCase):
    """Test suite for first step in Glue Workflow."""

    def setUp(self):
        """Initialize the test settings."""
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        s3 = boto3.resource("s3", region_name="us-east-1")
        self.dest_folder = os.mkdir(f'{TEST_DATA_DIR}/dest')
        media_bucket = s3.Bucket(MEDIA_BUCKETNAME)
        self.all_medias = [obj.key for obj in list(media_bucket.objects.all())]
        self.all_testfiles = [f for f in os.listdir(TEST_DATA_DIR) if os.path.isfile(f)]
    
    def tearDown(self):
        """Remove test settings."""
        shutil.rmtree(self.dest_folder)
    
    def test_split_files(self):
        """Test shape_dvaults_etl.glue_workflow_jobs.01_flat_dvaults.split_files method."""
        predictions = {}
        events = {}
        for f in self.all_testfiles:
            tmp_predictions, tmp_events = split_files(self.bucket, f, self.all_medias)
            for k,v in tmp_predictions.items():
                predictions[k] = predictions.get(k,[]) + v
            for k,v in tmp_events.items():
                events[k] = events.get(k, []) + v
        # predictions checks
        for service_name in predictions:
            self.assertTrue(len(predictions[service_name]) > 0)
        # events checks
        for service_name in events:
            self.assertTrue(len(events[service_name]) > 0)
