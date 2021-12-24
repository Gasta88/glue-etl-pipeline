provider "aws" {
  region  = "us-east-1"
  profile = "default"
}

terraform {
  required_version = ">= 0.14"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.0"
    }
  }
  backend "s3" {
    bucket = "terraform-ai-dev-states"
    key    = "ai-terraform-state-files/dvault-shape-staging.tfstate"
    region = "us-east-1"
  }
}

#--------------------------- S3 and S3 objects
resource "aws_s3_bucket" "dvault-bucket" {
  bucket = "dvault-landing-${terraform.workspace}"
  acl    = "private"
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
  force_destroy = true
  lifecycle {
    prevent_destroy = false
  }
  versioning {
    enabled = true
  }
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_policy" "dvault-bucket-policy" {
  bucket = aws_s3_bucket.dvault-bucket.id

  # Terraform's "jsonencode" function converts a
  # Terraform expression's result to valid JSON syntax.
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "AWSCloudTrailAclCheck",
        "Effect" : "Allow",
        "Principal" : {
          "Service" : "cloudtrail.amazonaws.com"
        },
        "Action" : "s3:GetBucketAcl",
        "Resource" : "arn:aws:s3:::${aws_s3_bucket.dvault-bucket.bucket}"
      },
      {
        "Sid" : "AWSCloudTrailWrite",
        "Effect" : "Allow",
        "Principal" : {
          "Service" : "cloudtrail.amazonaws.com"
        },
        "Action" : "s3:PutObject",
        "Resource" : "arn:aws:s3:::${aws_s3_bucket.dvault-bucket.bucket}/cloudtrail/AWSLogs/${data.aws_caller_identity.current.account_id}/*",
        "Condition" : {
          "StringEquals" : {
            "s3:x-amz-acl" : "bucket-owner-full-control",
            "aws:SourceArn" : "arn:aws:cloudtrail:us-east-1:${data.aws_caller_identity.current.account_id}:trail/${aws_cloudtrail.dvault-trail.name}"
          }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_object" "scripts-folder" {
  for_each = fileset("../shape_dvaults_etl", "*.py")
  bucket   = aws_s3_bucket.dvault-bucket.bucket
  acl      = "private"
  key      = "scripts/${each.value}"
  source   = "../shape_dvaults_etl/${each.value}"
  etag     = filemd5("../shape_dvaults_etl/${each.value}")
}

resource "aws_s3_bucket_object" "data-profiler-logs-folder" {
  bucket = aws_s3_bucket.dvault-bucket.bucket
  acl    = "private"
  key    = "data-profile-logs/"
}


#--------------------------- EventBridge and Cloudtrail
resource "aws_cloudtrail" "dvault-trail" {
  name                          = "s3-event-trail-dvault-${terraform.workspace}"
  s3_bucket_name                = aws_s3_bucket.dvault-bucket.bucket
  s3_key_prefix                 = "cloudtrail"
  include_global_service_events = false
  event_selector {
    read_write_type           = "WriteOnly"
    include_management_events = false

    data_resource {
      type = "AWS::S3::Object"

      # Make sure to append a trailing '/' to your ARN if you want
      # to monitor all objects in a bucket.
      values = ["${aws_s3_bucket.dvault-bucket.arn}/data/raw/"]
    }
  }
}

resource "aws_cloudwatch_event_rule" "glue-dvault-send-rule" {
  name = "s3-dvault-upload-trigger-rule-${terraform.workspace}"
  event_pattern = jsonencode({
    "detail-type" : ["AWS API Call via CloudTrail"],
    "source" : ["aws.s3"],
    "detail" : {
      "eventSource" : ["s3.amazonaws.com"],
      "requestParameters" : {
        "bucketName" : [aws_s3_bucket.dvault-bucket.bucket],
        "key" : [{
          "prefix" : "data/raw/"
        }]
      },
      "eventName" : ["PutObject", "CopyObject"]
    }
  })
}

resource "aws_iam_role" "glue-dvault-event-target-rule-role" {
  name               = "glue-dvault-event-target-rule-role-${terraform.workspace}"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "events.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}

resource "aws_iam_policy" "glue-dvault-event-target-rule-policy" {
  name        = "glue-dvault-event-target-rule-policy-${terraform.workspace}"
  description = "glue dvault event target rule policy"
  policy      = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "glue:notifyEvent"],
            "Resource": [
                "${aws_glue_workflow.dvault-glue-workflow.arn}"
            ]
        }
    ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "attach-dvault-event-target-role-policy" {
  role       = aws_iam_role.glue-dvault-event-target-rule-role.name
  policy_arn = aws_iam_policy.glue-dvault-event-target-rule-policy.arn
}

resource "aws_cloudwatch_event_target" "dvault-event-target" {
  arn      = aws_glue_workflow.dvault-glue-workflow.arn #Target resource arn
  rule     = aws_cloudwatch_event_rule.glue-dvault-send-rule.name
  role_arn = aws_iam_role.glue-dvault-event-target-rule-role.arn
}


#--------------------------- AWS Glue resources

resource "aws_glue_catalog_database" "aws-glue-catalog-database" {
  name = "dvault_glue_shape_${terraform.workspace}"
}

resource "aws_iam_role" "glue-role" {
  name                = "glue-service-role-${terraform.workspace}"
  path                = "/"
  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole", aws_iam_policy.s3-data-policy.arn]
  # Terraform's "jsonencode" function converts a
  # Terraform expression result to valid JSON syntax.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "glue.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_policy" "s3-data-policy" {
  name = "data-policy-dvault-${terraform.workspace}"
  path = "/"

  # Terraform's "jsonencode" function converts a
  # Terraform expression result to valid JSON syntax.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject", "s3:PutObject"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:s3:::${aws_s3_bucket.dvault-bucket.bucket}/*"
      },
      {
        Action = [
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:s3:::${aws_s3_bucket.dvault-bucket.bucket}"
      },
      {
        Action = [
          "s3:DeleteObject"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:s3:::${aws_s3_bucket.dvault-bucket.bucket}/data/*"
      }
    ]
  })
}


resource "aws_cloudwatch_log_group" "dvault-glue-log-group" {
  name              = "dvault-glue-log-group"
  retention_in_days = 7
}

resource "aws_glue_workflow" "dvault-glue-workflow" {
  name        = "s3-event-glue-dvault-workflow-${terraform.workspace}"
  description = "Glue workflow triggered by S3 PutObject Event"
  default_run_properties = {
    "landing_bucketname" : aws_s3_bucket.dvault-bucket.bucket,
    "media_bucketname" : "shape-media-library-staging",
    "dvault_filename" : "?????"
  }
}

resource "aws_glue_trigger" "prejob-trigger" {
  name          = "dvault-pre-job-trigger-${terraform.workspace}"
  type          = "EVENT"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name
  enabled       = false
  actions {
    job_name = aws_glue_job.pre-job.name
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_job" "pre-job" {
  name         = "dvault-pre-job-${terraform.workspace}"
  description  = "Glue job that updates state to STARTED in workflow run properties and set workflow global properties."
  glue_version = "1.0"
  role_arn     = aws_iam_role.glue-role.arn
  max_capacity = 0.0625

  command {
    name            = "pythonshell"
    python_version  = 3
    script_location = "s3://${aws_s3_bucket.dvault-bucket.bucket}/scripts/update_workflow_properties.py"
  }

  default_arguments = {
    "--TempDir" : "s3://${aws_s3_bucket.dvault-bucket.bucket}/tmp/",
    "--transition_state" : "STARTED",
    "--continuous-log-logGroup"          = aws_cloudwatch_log_group.dvault-glue-log-group.name,
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = ""
  }
  execution_property {
    max_concurrent_runs = 25
  }
}
resource "aws_glue_trigger" "profile-dvault-pass-trigger" {
  name          = "profile-dvault-pass-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.profile-dvault-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.pre-job.name
      state    = "SUCCEEDED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_trigger" "profile-dvault-fail-trigger" {
  name          = "profile-dvault-fail-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.clean-up-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.pre-job.name
      state    = "FAILED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_job" "profile-dvault-job" {
  name         = "profile-dvault-job-${terraform.workspace}"
  description  = "Glue job that profiles dvault files and split them in CLEAN and DIRTY."
  glue_version = "1.0"
  role_arn     = aws_iam_role.glue-role.arn
  max_capacity = 0.0625

  command {
    name            = "pythonshell"
    python_version  = 3
    script_location = "s3://${aws_s3_bucket.dvault-bucket.bucket}/scripts/data_profiling.py"
  }

  default_arguments = {
    "--TempDir" : "s3://${aws_s3_bucket.dvault-bucket.bucket}/tmp/",
    "--continuous-log-logGroup"          = aws_cloudwatch_log_group.dvault-glue-log-group.name,
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = ""
  }
  execution_property {
    max_concurrent_runs = 25
  }
}

resource "aws_glue_trigger" "flat-dvault-pass-trigger" {
  name          = "flat-dvault-pass-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.flat-dvault-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.profile-dvault-job.name
      state    = "SUCCEEDED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_trigger" "flat-dvault-fail-trigger" {
  name          = "flat-dvault-fail-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.clean-up-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.profile-dvault-job.name
      state    = "FAILED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_job" "flat-dvault-job" {
  name         = "flat-dvault-job-${terraform.workspace}"
  description  = "Glue job that explodes dvault files and split them in PREDICTIONS and EVENTS."
  glue_version = "1.0"
  role_arn     = aws_iam_role.glue-role.arn
  max_capacity = 0.0625

  command {
    name            = "pythonshell"
    python_version  = 3
    script_location = "s3://${aws_s3_bucket.dvault-bucket.bucket}/scripts/flat_dvaults.py"
  }

  default_arguments = {
    "--TempDir" : "s3://${aws_s3_bucket.dvault-bucket.bucket}/tmp/",
    "--continuous-log-logGroup"          = aws_cloudwatch_log_group.dvault-glue-log-group.name,
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = ""
  }
  execution_property {
    max_concurrent_runs = 25
  }
}

resource "aws_glue_job" "clean-up-job" {
  name         = "clean-up-job-${terraform.workspace}"
  description  = "Glue job that clean up prefixes like data/flat_dvaults/events and data/flat_dvaults/predictions."
  glue_version = "1.0"
  role_arn     = aws_iam_role.glue-role.arn
  max_capacity = 0.0625

  command {
    name            = "pythonshell"
    python_version  = 3
    script_location = "s3://${aws_s3_bucket.dvault-bucket.bucket}/scripts/clean_up.py"
  }
  default_arguments = {
    "--TempDir" : "s3://${aws_s3_bucket.dvault-bucket.bucket}/tmp/",
    "--continuous-log-logGroup"          = aws_cloudwatch_log_group.dvault-glue-log-group.name,
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = ""

  }
  execution_property {
    max_concurrent_runs = 25
  }
}

resource "aws_glue_trigger" "convert-to-parquet-pass-trigger" {
  name          = "convertion-to-parquet-pass-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.convert-to-parquet-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.flat-dvault-job.name
      state    = "SUCCEEDED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_trigger" "convert-to-parquet-fail-trigger" {
  name          = "convertion-to-parquet-fail-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.clean-up-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.flat-dvault-job.name
      state    = "FAILED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_job" "convert-to-parquet-job" {
  name              = "convert-to-parquet-job-${terraform.workspace}"
  description       = "Glue job that converts JSON to Parquet"
  glue_version      = "2.0"
  role_arn          = aws_iam_role.glue-role.arn
  number_of_workers = 2
  worker_type       = "G.1X"
  command {
    name            = "glueetl"
    python_version  = 3
    script_location = "s3://${aws_s3_bucket.dvault-bucket.bucket}/scripts/convert_to_parquet.py"
  }
  default_arguments = {
    "--job-bookmark-option" : "job-bookmark-enable",
    "--TempDir" : "s3://${aws_s3_bucket.dvault-bucket.bucket}/tmp/",
    "--continuous-log-logGroup"          = aws_cloudwatch_log_group.dvault-glue-log-group.name,
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = ""
  }
  execution_property {
    max_concurrent_runs = 25
  }
}

resource "aws_glue_trigger" "dvault-parquet-crawler-pass-trigger" {
  name          = "dvault-parquet-crawler-pass-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    crawler_name = aws_glue_crawler.dvault-parquet-crawler.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.convert-to-parquet-job.name
      state    = "SUCCEEDED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_trigger" "dvault-parquet-crawler-fail-trigger" {
  name          = "dvault-parquet-crawler-fail-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.clean-up-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.convert-to-parquet-job.name
      state    = "FAILED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_crawler" "dvault-parquet-crawler" {
  database_name = aws_glue_catalog_database.aws-glue-catalog-database.name
  name          = "parquet-clean-crawler-${terraform.workspace}"
  description   = "Crawler for Parquet cleaned and profiled"
  role          = aws_iam_role.glue-role.arn
  table_prefix  = "dvault_glue_${terraform.workspace}_"

  s3_target {
    path       = "s3://${aws_s3_bucket.dvault-bucket.bucket}/data/clean-parquet/"
    exclusions = ["**_SUCCESS", "**crc", "**csv", "**metadata"]
  }
}

resource "aws_glue_trigger" "postjob-pass-trigger" {
  name          = "dvault-post-job-pass-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.post-job.name
  }
  predicate {
    conditions {
      crawler_name = aws_glue_crawler.dvault-parquet-crawler.name
      crawl_state  = "SUCCEEDED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}

resource "aws_glue_trigger" "postjob-fail-trigger" {
  name          = "dvault-post-job-fail-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.clean-up-job.name
  }
  predicate {
    conditions {
      crawler_name = aws_glue_crawler.dvault-parquet-crawler.name
      crawl_state  = "FAILED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}


resource "aws_glue_job" "post-job" {
  name         = "dvault-post-job-${terraform.workspace}"
  description  = "Glue job that updates workflow run property"
  glue_version = "1.0"
  role_arn     = aws_iam_role.glue-role.arn
  max_capacity = 0.0625

  command {
    name            = "pythonshell"
    python_version  = 3
    script_location = "s3://${aws_s3_bucket.dvault-bucket.bucket}/scripts/update_workflow_properties.py"
  }

  default_arguments = {
    "--TempDir" : "s3://${aws_s3_bucket.dvault-bucket.bucket}/tmp/",
    "--transition_state" : "COMPLETED",
    "--continuous-log-logGroup"          = aws_cloudwatch_log_group.dvault-glue-log-group.name,
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = ""
  }
  execution_property {
    max_concurrent_runs = 25
  }
}
