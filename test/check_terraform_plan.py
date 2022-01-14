import unittest
import json


class CheckTerraformPlan(unittest.TestCase):
    """Test suite to check the layout of the Terraform deployment from the JSON plan."""

    def setUp(self):
        with open("../deployments/plan.json") as f:
            self.plan = json.load(f)

    def test_landing_bucket(self):
        """Test configuration of S3 landing bucket."""
        buckets = {
            resource["address"]: resource
            for resource in self.plan["planned_values"]["root_module"]["resources"]
            if resource["type"] == "aws_s3_bucket"
        }
        landing_bucket = buckets.get("aws_s3_bucket.dvault-bucket", None)
        self.assertIsNotNone(landing_bucket)
        # add more tests if more buckets are created

    def test_prefixes(self):
        """Test configuration of S3 bucket prefixes."""
        prefixes = {
            resource["address"]: resource
            for resource in self.plan["planned_values"]["root_module"]["resources"]
            if resource["type"] == "aws_s3_bucket_object"
        }
        self.assertEqual(len(prefixes), 7)

        data_profiler_prefix = prefixes.get(
            "aws_s3_bucket_object.data-profiler-logs-folder", None
        )
        self.assertIsNotNone(data_profiler_prefix)
        # add more tests if more prefixes are created

    def test_glue_ecosystem(self):
        """Test configuration of Glue workflow/jobs/triggers/crawlers."""
        workflows = {
            resource["address"]: resource
            for resource in self.plan["planned_values"]["root_module"]["resources"]
            if resource["type"] == "aws_glue_workflow"
        }
        dvault_workflow = workflows.get("aws_glue_workflow.dvault-glue-workflow", None)
        self.assertIsNotNone(dvault_workflow)

        jobs = {
            resource["address"]: resource
            for resource in self.plan["planned_values"]["root_module"]["resources"]
            if resource["type"] == "aws_glue_job"
        }
        pre_job = jobs.get("aws_glue_job.pre-job")
        self.assertIsNotNone(pre_job)
        profile_job = jobs.get("aws_glue_job.profile-dvault-job")
        self.assertIsNotNone(profile_job)
        flat_job = jobs.get("aws_glue_job.flat-dvault-job")
        self.assertIsNotNone(flat_job)
        convert_job = jobs.get("aws_glue_job.convert-to-parquet-job")
        self.assertIsNotNone(convert_job)
        post_job = jobs.get("aws_glue_job.post-job")
        self.assertIsNotNone(post_job)
        clean_job = jobs.get("aws_glue_job.clean-up-job")
        self.assertIsNotNone(clean_job)

        triggers = {
            resource["address"]: resource
            for resource in self.plan["planned_values"]["root_module"]["resources"]
            if resource["type"] == "aws_glue_trigger"
        }
        pre_trigger = triggers.get("aws_glue_trigger.prejob-trigger", None)
        self.assertIsNotNone(pre_trigger)
        profile_pass_trigger = triggers.get(
            "aws_glue_trigger.profile-dvault-pass-trigger", None
        )
        self.assertIsNotNone(profile_pass_trigger)
        profile_fail_trigger = triggers.get(
            "aws_glue_trigger.profile-dvault-fail-trigger", None
        )
        self.assertIsNotNone(profile_fail_trigger)
        flat_pass_trigger = triggers.get(
            "aws_glue_trigger.flat-dvault-pass-trigger", None
        )
        self.assertIsNotNone(flat_pass_trigger)
        flat_fail_trigger = triggers.get(
            "aws_glue_trigger.flat-dvault-fail-trigger", None
        )
        self.assertIsNotNone(flat_fail_trigger)
        convert_pass_trigger = triggers.get(
            "aws_glue_trigger.convert-to-parquet-pass-trigger", None
        )
        self.assertIsNotNone(convert_pass_trigger)
        convert_fail_trigger = triggers.get(
            "aws_glue_trigger.convert-to-parquet-fail-trigger", None
        )
        self.assertIsNotNone(convert_fail_trigger)
        post_pass_trigger = triggers.get("aws_glue_trigger.postjob-pass-trigger", None)
        self.assertIsNotNone(post_pass_trigger)
        post_fail_trigger = triggers.get("aws_glue_trigger.postjob-fail-trigger", None)
        self.assertIsNotNone(post_fail_trigger)

        crawlers = {
            resource["address"]: resource
            for resource in self.plan["planned_values"]["root_module"]["resources"]
            if resource["type"] == "aws_glue_crawler"
        }
        dvault_crawler = crawlers.get("aws_glue_crawler.dvault-parquet-crawler", None)
        self.assertIsNotNone(dvault_crawler)

        data_catalogs = {
            resource["address"]: resource
            for resource in self.plan["planned_values"]["root_module"]["resources"]
            if resource["type"] == "aws_glue_catalog_database"
        }
        dvault_catalog = data_catalogs.get(
            "aws_glue_catalog_database.aws-glue-catalog-database", None
        )
        self.assertIsNotNone(dvault_catalog)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=3)
    unittest.main(testRunner=runner)
