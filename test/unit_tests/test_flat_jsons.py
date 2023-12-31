import boto3
import os
import unittest
import warnings
from ef_ingestion_etl.flat_jsons import (
    split_files,
    _recast_score_to_float,
    _recast_paragraph_to_str,
    _convert_query_and_tags,
    _replace_image_uri,
    _get_service_name,
)
import os
import logging

TEST_DATA_DIR = "test/unit_tests/data/flat_jsons"
MEDIA_BUCKETNAME = "media-library-staging"
logging.getLogger("botocore").setLevel(logging.CRITICAL)
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


class FlatDvaultTestCase(unittest.TestCase):
    """Test suite for first step in Glue Workflow."""

    maxDiff = None

    def setUp(self):
        """Initialize the test settings."""
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        s3 = boto3.resource("s3")
        self.media_bucketname = MEDIA_BUCKETNAME
        media_bucket = s3.Bucket(MEDIA_BUCKETNAME)
        self.all_medias = [obj.key for obj in list(media_bucket.objects.all())]
        self.all_testfiles = [f for f in os.listdir(TEST_DATA_DIR) if os.path.isfile(f)]

    def tearDown(self):
        """Remove test settings."""
        pass

    def test_split_files(self):
        """Test ef_ingestion_etl.glue_workflow_jobs.flat_jsons.split_files method."""
        predictions = {}
        events = {}
        for f in self.all_testfiles:
            tmp_predictions, tmp_events = split_files(f)
            for k, v in tmp_predictions.items():
                predictions[k] = predictions.get(k, []) + v
            for k, v in tmp_events.items():
                events[k] = events.get(k, []) + v
        # predictions checks
        for service_name in predictions:
            self.assertTrue(len(predictions[service_name]) > 0)
        # events checks
        for service_name in events:
            self.assertTrue(len(events[service_name]) > 0)

    def test_recast_score_to_float(self):
        """Test ef_ingestion_etl.glue_workflow_jobs.flat_jsons._recast_score_to_float method."""
        predictions = {
            "microone": [
                {
                    "detail": {
                        "prediction": {
                            "input": {
                                "sentences_scores": [{"score": -1}, {"score": 0.5845}]
                            }
                        }
                    }
                },
                {
                    "detail": {
                        "prediction": {
                            "input": {
                                "sentences_scores": [{"score": 0.44447}, {"score": -1}]
                            }
                        }
                    }
                },
            ],
            "microtwo": [{"test": "ignore"}, {"test": "ignore_again"}],
            "microthree": [{"test": "ignore"}, {"test": "ignore_again"}],
        }
        expected_predictions = {
            "microone": [
                {
                    "detail": {
                        "prediction": {
                            "input": {
                                "sentences_scores": [{"score": -1.0}, {"score": 0.5845}]
                            }
                        }
                    }
                },
                {
                    "detail": {
                        "prediction": {
                            "input": {
                                "sentences_scores": [
                                    {"score": 0.44447},
                                    {"score": -1.0},
                                ]
                            }
                        }
                    }
                },
            ],
            "microtwo": [{"test": "ignore"}, {"test": "ignore_again"}],
            "microthree": [{"test": "ignore"}, {"test": "ignore_again"}],
        }
        test_predictions = {}
        for service_name, elements in predictions.items():
            test_predictions[service_name] = [
                _recast_score_to_float(el, service_name) for el in elements
            ]
        self.assertDictEqual(test_predictions, expected_predictions)

    def test_recast_paragraph_to_str(self):
        """Test ef_ingestion_etl.glue_workflow_jobs.flat_jsons._recast_paragraph_to_str method."""
        events = {
            "microone": [
                {
                    "detail": {
                        "evaluation": {"type": "PUBLISH", "payload": {"paragraph": 1}}
                    }
                },
                {
                    "detail": {
                        "evaluation": {"type": "PUBLISH", "payload": {"paragraph": 2}}
                    }
                },
            ],
            "microtwo": [{"test": "ignore"}, {"test": "ignore_again"}],
            "microthree": [{"test": "ignore"}, {"test": "ignore_again"}],
        }
        expected_events = {
            "microone": [
                {
                    "detail": {
                        "evaluation": {"type": "PUBLISH", "payload": {"paragraph": "1"}}
                    }
                },
                {
                    "detail": {
                        "evaluation": {"type": "PUBLISH", "payload": {"paragraph": "2"}}
                    }
                },
            ],
            "microtwo": [{"test": "ignore"}, {"test": "ignore_again"}],
            "microthree": [{"test": "ignore"}, {"test": "ignore_again"}],
        }
        test_events = {}
        for service_name, elements in events.items():
            test_events[service_name] = [
                _recast_paragraph_to_str(el, service_name) for el in elements
            ]
        self.assertDictEqual(test_events, expected_events)

    def test_convert_query_and_tags(self):
        """Test ef_ingestion_etl.glue_workflow_jobs.flat_jsons._convert_query_and_tags method."""
        events = {
            "microthree": [
                {
                    "detail": {
                        "evaluation": {
                            "payload": {
                                "query": "look at this query",
                                "tags": "unittest",
                            }
                        }
                    }
                },
                {
                    "detail": {
                        "evaluation": {
                            "payload": {"query": "my query is amazing", "tags": "ci/cd"}
                        }
                    }
                },
            ],
            "microtwo": [{"test": "ignore"}, {"test": "ignore_again"}],
            "microone": [{"test": "ignore"}, {"test": "ignore_again"}],
        }
        expected_events = {
            "microthree": [
                {
                    "detail": {
                        "evaluation": {
                            "payload": {
                                "query": ["look at this query"],
                                "tags": ["unittest"],
                            }
                        }
                    }
                },
                {
                    "detail": {
                        "evaluation": {
                            "payload": {
                                "query": ["my query is amazing"],
                                "tags": ["ci/cd"],
                            }
                        }
                    }
                },
            ],
            "microtwo": [{"test": "ignore"}, {"test": "ignore_again"}],
            "microone": [{"test": "ignore"}, {"test": "ignore_again"}],
        }
        test_events = {}
        for service_name, elements in events.items():
            test_events[service_name] = [
                _convert_query_and_tags(el, service_name) for el in elements
            ]
        self.assertDictEqual(test_events, expected_events)

    def test_replace_image_uri(self):
        """Test ef_ingestion_etl.glue_workflow_jobs.flat_jsons._replace_image_uri method."""
        events = {
            "microthree": [
                {
                    "detail": {
                        "evaluation": {
                            "type": "PUBLISH",
                            "payload": {
                                "media_id": "67e319a0-33b0-478a-b0fa-35a337ae5fc1",
                                "medialib": "MYLIB",
                            },
                        },
                    }
                },
                {
                    "detail": {
                        "evaluation": {
                            "type": "PUBLISH",
                            "payload": {
                                "media_id": "1546195",
                                "medialib": "EXTERNALLIB",
                            },
                        },
                    }
                },
            ],
            "microtwo": [{"test": "ignore"}, {"test": "ignore_again"}],
            "microone": [[{"test": "ignore"}, {"test": "ignore_again"}]],
        }
        expected_events = {
            "microthree": [
                {
                    "detail": {
                        "evaluation": {
                            "type": "PUBLISH",
                            "payload": {
                                "media_id": "s3://media-library-staging/77e34376-ddc0-4710-8088-c426fb669951/MYLIB/67e319a0-33b0-478a-b0fa-35a337ae5fc1",
                                "medialib": "MYLIB",
                                "search_match": None,
                            },
                        },
                    }
                },
                {
                    "detail": {
                        "evaluation": {
                            "type": "PUBLISH",
                            "payload": {
                                "media_id": "s3://media-library-staging/77e34376-ddc0-4710-8088-c426fb669951/EXTERNALLIB/1546195",
                                "medialib": "EXTERNALLIB",
                                "search_match": None,
                            },
                        },
                    }
                },
            ],
            "microtwo": [{"test": "ignore"}, {"test": "ignore_again"}],
            "microone": [[{"test": "ignore"}, {"test": "ignore_again"}]],
        }
        test_events = {}
        for service_name, elements in events.items():
            test_events[service_name] = [
                _replace_image_uri(
                    el, service_name, self.media_bucketname, self.all_medias
                )
                for el in elements
            ]
        self.assertDictEqual(test_events, expected_events)

    def test_get_service_name(self):
        """Test ef_ingestion_etl.glue_workflow_jobs.flat_jsons._get_service_name method."""
        el = {
            "detail": {
                "type": "EFPredictionEvent",
                "prediction": {"service": "microthree"},
            }
        }
        self.assertEqual(_get_service_name(el), "microthree")

        el = {
            "detail": {
                "type": "EFEvaluationEvent",
                "evaluation": {"service": "microtwo"},
            }
        }
        self.assertEqual(_get_service_name(el), "microtwo")

        el = {
            "detail": {
                "type": "EFEvaluationEvent",
                "evaluation": {"prediction_id": "blablabla#microtwo"},
            }
        }
        self.assertEqual(_get_service_name(el), "microtwo")

    def test_save_flat_json(self):
        """Test ef_ingestion_etl.glue_workflow_jobs.flat_jsons.save_flat_json method."""
        pass


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=3)
    unittest.main(testRunner=runner)
