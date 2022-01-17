import unittest
import warnings
from shape_dvaults_etl.data_profiling import run_data_profiling
import os

TEST_DATA_DIR = "test/data/flat_dvaults"


class DataProfilingTestCase(unittest.TestCase):
    """Test suite for data profiling step in Glue Workflow."""

    maxDiff = None

    def setUp(self):
        """Initialize the test settings."""
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)

    def tearDown(self):
        """Remove test settings."""
        pass

    def test_run_data_profiling_event_1_pass(self):
        """Test shape_dvaults_etl.data_profiling.run_data_profiling method.

        Test event dvault with prediction_id attribute and no service attribute.
        """
        event = {
            "version": "0",
            "id": "ee412e96-45e2-7a35-7d06-83f254728373",
            "detail-type": "DVaultEvaluationEvent",
            "source": "SHAPE.DVault",
            "account": "767115741234",
            "time": "2021-11-17T20:37:06Z",
            "region": "eu-west-1",
            "resources": [],
            "detail": {
                "id": "9d38ef9e-9ac2-4960-a356-d47018bdf42d",
                "type": "DVaultEvaluationEvent",
                "timestamp": 1637181418425,
                "partitionKey": "3fb1d9a8-1535-4dfc-966c-67bda8a99bd1",
                "evaluation": {
                    "template_dvault_version": "1.0",
                    "id": "9d38ef9e-9ac2-4960-a356-d47018bdf42d",
                    "shape_id": "3fb1d9a8-1535-4dfc-966c-67bda8a99bd1",
                    "prediction_id": "3fb1d9a8-1535-4dfc-966c-67bda8a99bd1#summarizer",
                    "timestamp": 1637181418425,
                    "reporter": "user",
                    "type": "PUBLISH",
                    "payload": {
                        "text": 'In "<strong>The Waterfall</strong>" <strong>approach</strong>, the whole <strong>process</strong> of <strong>software development</strong> is divided into separate <strong>phases</strong>.',
                        "paragraph": 5,
                        "slide": "gn",
                    },
                },
                "tags": {"region": "eu-west-1"},
            },
        }

        flag, errors = run_data_profiling(event, "event")
        self.assertTrue(flag)
        self.assertDictEqual(errors, {})

    def test_run_data_profiling_event_2_pass(self):
        """Test shape_dvaults_etl.data_profiling.run_data_profiling method.

        Test event dvault without prediction_id attribute and with service attribute.
        """
        event = {
            "version": "0",
            "id": "ee412e96-45e2-7a35-7d06-83f254728373",
            "detail-type": "DVaultEvaluationEvent",
            "source": "SHAPE.DVault",
            "account": "767115741234",
            "time": "2021-11-17T20:37:06Z",
            "region": "eu-west-1",
            "resources": [],
            "detail": {
                "id": "9d38ef9e-9ac2-4960-a356-d47018bdf42d",
                "type": "DVaultEvaluationEvent",
                "timestamp": 1637181418425,
                "partitionKey": "3fb1d9a8-1535-4dfc-966c-67bda8a99bd1",
                "evaluation": {
                    "template_dvault_version": "1.0",
                    "id": "9d38ef9e-9ac2-4960-a356-d47018bdf42d",
                    "shape_id": "3fb1d9a8-1535-4dfc-966c-67bda8a99bd1",
                    "prediction_id": None,
                    "service": "ste",
                    "timestamp": 1637181418425,
                    "reporter": "user",
                    "type": "PUBLISH",
                    "payload": {
                        "text": 'In "<strong>The Waterfall</strong>" <strong>approach</strong>, the whole <strong>process</strong> of <strong>software development</strong> is divided into separate <strong>phases</strong>.',
                        "paragraph": 5,
                        "slide": "gn",
                    },
                },
                "tags": {"region": "eu-west-1"},
            },
        }

        flag, errors = run_data_profiling(event, "event")
        self.assertTrue(flag)
        self.assertDictEqual(errors, {})

    def test_run_data_profiling_event_fail(self):
        """Test shape_dvaults_etl.data_profiling.run_data_profiling method.

        Test event dvault without prediction_id attribute nor service attribute.
        """
        event = {
            "version": "0",
            "id": "ee412e96-45e2-7a35-7d06-83f254728373",
            "detail-type": "DVaultEvaluationEvent",
            "source": "SHAPE.DVault",
            "account": "767115741234",
            "time": "2021-11-17T20:37:06Z",
            "region": "eu-west-1",
            "resources": [],
            "detail": {
                "id": "9d38ef9e-9ac2-4960-a356-d47018bdf42d",
                "type": "DVaultEvaluationEvent",
                "timestamp": 1637181418425,
                "partitionKey": "3fb1d9a8-1535-4dfc-966c-67bda8a99bd1",
                "evaluation": {
                    "template_dvault_version": "1.0",
                    "id": "9d38ef9e-9ac2-4960-a356-d47018bdf42d",
                    "shape_id": "3fb1d9a8-1535-4dfc-966c-67bda8a99bd1",
                    "prediction_id": None,
                    "timestamp": 1637181418425,
                    "reporter": "user",
                    "type": "PUBLISH",
                    "payload": {
                        "text": 'In "<strong>The Waterfall</strong>" <strong>approach</strong>, the whole <strong>process</strong> of <strong>software development</strong> is divided into separate <strong>phases</strong>.',
                        "paragraph": 5,
                        "slide": "gn",
                    },
                },
                "tags": {"region": "eu-west-1"},
            },
        }

        flag, errors = run_data_profiling(event, "event")
        self.assertFalse(flag)
        self.assertTrue(len(errors) > 0)

    def test_run_data_profiling_prediction_pass(self):
        """Test shape_dvaults_etl.data_profiling.run_data_profiling method.

        Test prediction dvault for success.
        """
        event = {
            "version": "0",
            "id": "63ee6147-c5a8-dbce-ddcd-badc8f6371fb",
            "detail-type": "DVaultPredictionEvent",
            "source": "SHAPE.DVault",
            "account": "767115741234",
            "time": "2021-11-11T20:43:33Z",
            "region": "eu-west-1",
            "resources": [],
            "detail": {
                "id": "9fe96b26-d49e-416d-97e2-0327b058daca#headline",
                "type": "DVaultPredictionEvent",
                "timestamp": 1636663411000,
                "partitionKey": "9fe96b26-d49e-416d-97e2-0327b058daca",
                "prediction": {
                    "template_dvault_version": "1.0",
                    "id": "9fe96b26-d49e-416d-97e2-0327b058daca#headline",
                    "shape_id": "9fe96b26-d49e-416d-97e2-0327b058daca",
                    "timestamp": 1636663411000,
                    "service": "headline",
                    "service_version": {"software": "0.1.0", "model": "distill-bart"},
                    "context": {},
                    "input": {
                        "transcript": "Transcription/9fe96b26-d49e-416d-97e2-0327b058daca"
                    },
                    "output": {
                        "headline": [
                            " The Klingon alphabet has been revealed in a new online dictionary.",
                            " The Klingon alphabet is based on the Latin alphabet, but on the television series The Klingons use a different writing system.",
                        ]
                    },
                },
                "tags": {"region": "eu-west-1"},
            },
        }

        flag, errors = run_data_profiling(event, "prediction")
        self.assertTrue(flag)
        self.assertDictEqual(errors, {})

    def test_run_data_profiling_prediction_fail(self):
        """Test shape_dvaults_etl.data_profiling.run_data_profiling method.

        Test prediction dvault for failure.
        """
        event = {
            "version": "0",
            "id": "63ee6147-c5a8-dbce-ddcd-badc8f6371fb",
            "detail-type": "DVaultPredictionEvent",
            "source": "SHAPE.DVault",
            "account": "767115741234",
            "time": "2021-11-11T20:43:33Z",
            "region": "eu-west-1",
            "resources": [],
            "detail": {
                "id": "9fe96b26-d49e-416d-97e2-0327b058daca#headline",
                "type": "DVaultPredictionEvent",
                "timestamp": 1636663411000,
                "partitionKey": "9fe96b26-d49e-416d-97e2-0327b058daca",
                "prediction": {
                    "template_dvault_version": "1.0",
                    "id": "9fe96b26-d49e-416d-97e2-0327b058daca#headline",
                    "shape_id": "9fe96b26-d49e-416d-97e2-0327b058daca",
                    "timestamp": 1636663411000,
                    "service": "not_headline",
                    "service_version": {"software": "0.1.0", "model": "distill-bart"},
                    "context": {},
                    "input": {
                        "transcript": "Transcription/9fe96b26-d49e-416d-97e2-0327b058daca"
                    },
                    "output": {
                        "headline": [
                            " The Klingon alphabet has been revealed in a new online dictionary.",
                            " The Klingon alphabet is based on the Latin alphabet, but on the television series The Klingons use a different writing system.",
                        ]
                    },
                },
                "tags": {"region": "eu-west-1"},
            },
        }

        flag, errors = run_data_profiling(event, "prediction")
        self.assertFalse(flag)
        self.assertTrue(len(errors) > 0)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=3)
    unittest.main(testRunner=runner)
