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

resource "aws_s3_bucket_object" "scripts-folder" {
  for_each = fileset("../shape_dvaults_etl", "*.py")
  bucket   = aws_s3_bucket.dvault-bucket.bucket
  acl      = "private"
  key      = "scripts/${each.value}"
  source   = "../shape_dvaults_etl/${each.value}"
  etag     = filemd5("../shape_dvaults_etl/${each.value}")
}

resource "aws_s3_bucket_object" "dependencies-folder" {
  for_each = fileset("../dependencies", "*.zip")
  bucket   = aws_s3_bucket.dvault-bucket.bucket
  acl      = "private"
  key      = "dependencies/${each.value}"
  source   = "../dependencies/${each.value}"
  etag     = filemd5("../dependencies/${each.value}")
}

resource "aws_s3_bucket_object" "data-profiler-logs-folder" {
  bucket = aws_s3_bucket.dvault-bucket.bucket
  acl    = "private"
  key    = "data-profile-logs/"
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
  name        = "s3-batch-glue-dvault-workflow-${terraform.workspace}"
  description = "Glue workflow triggered by schedule or on-demand"
  default_run_properties = {
    "landing_bucketname" : aws_s3_bucket.dvault-bucket.bucket,
    "media_bucketname" : "shape-media-library-staging"
  }
}

resource "aws_glue_trigger" "prejob-trigger" {
  name          = "dvault-pre-job-trigger-${terraform.workspace}"
  type          = "ON_DEMAND"
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
  timeout = 15
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
    "--enable-metrics"                   = "",
    "--extra-py-files"                   = "s3://${aws_s3_bucket.dvault-bucket.bucket}/dependencies/cerberus.zip"
  }
  timeout = 15
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
  timeout = 15
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
  timeout = 15
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
  timeout = 15
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

  s3_target {
    path       = "s3://${aws_s3_bucket.dvault-bucket.bucket}/data/clean_parquet/"
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
  timeout = 15
}

resource "aws_glue_trigger" "cleanupjob-trigger" {
  name          = "dvault-cleanup-job-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.clean-up-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.post-job.name
      state    = "SUCCEEDED"
    }
  }
  depends_on = [
    aws_glue_workflow.dvault-glue-workflow
  ]
}
