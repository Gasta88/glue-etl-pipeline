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

#--------------------------- Locals declaration
locals {
  env = {
    dev = {
      source_bucket = "dvault-staging"
      media_bucket  = "shape-media-library-staging"
    }
    e2e-test = {
      source_bucket = "None"
      media_bucket  = "shape-media-library-staging"
    }
    prod = {
      source_bucket = "ai-dvault-sync-prod-eu"
      media_bucket  = "shape-media-library-sync-prod-eu"
    }
  }
  environmentvars = contains(keys(local.env), terraform.workspace) ? terraform.workspace : "dev"
  workspace       = merge(local.env["dev"], local.env[local.environmentvars])
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


  lifecycle_rule {
    abort_incomplete_multipart_upload_days = 0
    enabled                                = true
    id                                     = "dirty-dvaults-clean-up"
    prefix                                 = "data/dirty_dvaults/"

    expiration {
      days                         = 90
      expired_object_delete_marker = false
    }
  }

  versioning {
    enabled = false
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
  for_each = fileset("../dependencies", "*.whl")
  bucket   = aws_s3_bucket.dvault-bucket.bucket
  acl      = "private"
  key      = "dependencies/${each.value}"
  source   = "../dependencies/${each.value}"
  etag     = filemd5("../dependencies/${each.value}")
}



#--------------------------- AWS Glue resources


resource "aws_iam_role" "glue-role" {
  name                = "dvault-glue-service-role-${terraform.workspace}"
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
        Resource = ["arn:aws:s3:::${aws_s3_bucket.dvault-bucket.bucket}/*", "arn:aws:s3:::${local.workspace["source_bucket"]}/*"]
      },
      {
        Action = [
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = ["arn:aws:s3:::${aws_s3_bucket.dvault-bucket.bucket}", "arn:aws:s3:::${local.workspace["source_bucket"]}"]
      },
      {
        Action = [
          "s3:DeleteObject"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:s3:::${aws_s3_bucket.dvault-bucket.bucket}/data/*"
      },
      {
        Action = [
          "logs:GetLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:log-group:/aws-glue/python-jobs/output:*"
      },
      {
        Action = [
          "logs:DescribeLogStreams"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:log-group:/aws-glue/python-jobs/output:*"
      },
      {
        Action = [
          "es:*"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:es:*:*:domain/ai-elasticsearch-6-public/*"
      },
      {
        Effect = "Allow",
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:CreateGrant"
        ],
        Resource = "arn:aws:kms:eu-west-1:228718274899:key/14ab5d75-0d44-4437-afc2-54d16377bf9f"
      },
      {
        Effect   = "Allow",
        Action   = "kms:ListAliases",
        Resource = "*"
      }
    ]
  })
}

resource "aws_glue_connection" "elasticsearch" {
  name            = "dvault-glue-connection-to-elasticsearch-${terraform.workspace}"
  connection_type = "NETWORK"

  physical_connection_requirements {
    availability_zone      = "us-east-1a"
    security_group_id_list = ["sg-05d5182f1bb185a78"]
    subnet_id              = "subnet-0f6cc8f0aae21579f"
  }

}

resource "aws_glue_workflow" "dvault-glue-workflow" {
  name        = "s3-batch-glue-dvault-workflow-${terraform.workspace}"
  description = "Glue workflow triggered by schedule or on-demand"
  default_run_properties = {
    "source_bucketname" : "${local.workspace["source_bucket"]}"
    "landing_bucketname" : aws_s3_bucket.dvault-bucket.bucket,
    "media_bucketname" : "${local.workspace["media_bucket"]}"
  }
}

resource "aws_glue_trigger" "prejob-trigger" {
  name          = "dvault-pre-job-trigger-${terraform.workspace}"
  schedule      = "cron(0 * ? * MON-FRI *)"
  type          = "SCHEDULED"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name
  actions {
    job_name = aws_glue_job.pre-job.name
  }

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
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = ""
  }
  timeout = 15
}
resource "aws_glue_trigger" "profile-dvault-pass-trigger" {
  name          = "dvault-profile-pass-trigger-${terraform.workspace}"
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

}

resource "aws_glue_trigger" "profile-dvault-fail-trigger" {
  name          = "dvault-profile-fail-trigger-${terraform.workspace}"
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

}

resource "aws_glue_job" "profile-dvault-job" {
  name         = "dvault-profile-job-${terraform.workspace}"
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
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = "",
    "--extra-py-files"                   = "s3://${aws_s3_bucket.dvault-bucket.bucket}/dependencies/Cerberus-1.3.3-py3-none-any.whl,s3://${aws_s3_bucket.dvault-bucket.bucket}/dependencies/s3fs-0.4.0-py3-none-any.whl"
  }
  timeout = 15
}

resource "aws_glue_trigger" "flat-dvault-pass-trigger" {
  name          = "dvault-flat-pass-trigger-${terraform.workspace}"
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

}

resource "aws_glue_trigger" "flat-dvault-fail-trigger" {
  name          = "dvault-flat-fail-trigger-${terraform.workspace}"
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

}

resource "aws_glue_job" "flat-dvault-job" {
  name         = "dvault-flat-job-${terraform.workspace}"
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
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = "",
    "--extra-py-files"                   = "s3://${aws_s3_bucket.dvault-bucket.bucket}/dependencies/s3fs-0.4.0-py3-none-any.whl"
  }
  timeout = 15
}

resource "aws_glue_job" "clean-up-job" {
  name         = "dvault-clean-up-job-${terraform.workspace}"
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
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = ""

  }
  timeout = 15
}

resource "aws_glue_trigger" "convert-to-parquet-pass-trigger" {
  name          = "dvault-convert-to-parquet-pass-trigger-${terraform.workspace}"
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

}

resource "aws_glue_trigger" "convert-to-parquet-fail-trigger" {
  name          = "dvault-convert-to-parquet-fail-trigger-${terraform.workspace}"
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

}

resource "aws_glue_job" "convert-to-parquet-job" {
  name              = "dvault-convert-to-parquet-job-${terraform.workspace}"
  description       = "Glue job that converts JSON to Parquet"
  glue_version      = "3.0"
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
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = "",
    "--enable-spark-ui"                  = "true",
    "--spark-event-logs-path"            = "s3://spark-history-server-logs-fghjrt/",
    "--enable-auto-scaling" : "true"
  }
  timeout = 15
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
      job_name = aws_glue_job.convert-to-parquet-job.name
      state    = "SUCCEEDED"
    }
  }

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
      job_name = aws_glue_job.convert-to-parquet-job.name
      state    = "FAILED"
    }
  }

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

}

resource "aws_glue_trigger" "eslogsjob-trigger" {
  name          = "dvault-eslogs-job-trigger-${terraform.workspace}"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.dvault-glue-workflow.name

  actions {
    job_name = aws_glue_job.eslogs-job.name
  }
  predicate {
    conditions {
      job_name = aws_glue_job.post-job.name
      state    = "SUCCEEDED"
    }
  }

}

resource "aws_glue_job" "eslogs-job" {
  name         = "dvault-eslogs-job-${terraform.workspace}"
  description  = "Glue job that send logs to ElasticSearch"
  glue_version = "1.0"
  role_arn     = aws_iam_role.glue-role.arn
  max_capacity = 0.0625
  connections  = [aws_glue_connection.elasticsearch.name]

  command {
    name            = "pythonshell"
    python_version  = 3
    script_location = "s3://${aws_s3_bucket.dvault-bucket.bucket}/scripts/process_logs.py"
  }

  default_arguments = {
    "--TempDir" : "s3://${aws_s3_bucket.dvault-bucket.bucket}/tmp/",
    "--enable-continuous-cloudwatch-log" = "true",
    "--enable-continuous-log-filter"     = "true",
    "--enable-metrics"                   = "",
    "--extra-py-files"                   = "s3://${aws_s3_bucket.dvault-bucket.bucket}/dependencies/elasticsearch-7.13.0-py2.py3-none-any.whl"
  }
  timeout = 15
}


