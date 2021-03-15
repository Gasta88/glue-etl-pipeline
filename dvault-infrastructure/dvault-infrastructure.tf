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

#Create S3 bucket for dvault files
resource "aws_s3_bucket" "dvault-staging-bucket" {
  bucket = "dvault-staging"
  acl    = "private"
}

#Create Kinesis Firehose delivery stream with s3 destination
resource "aws_iam_role" "firehose_role" {
  name = "firehose_dvault_role"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "firehose.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}

resource "aws_kinesis_firehose_delivery_stream" "dvault-staging-stream" {
  name        = "dvault-staging-stream"
  destination = "s3"

  s3_configuration {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.dvault-staging-bucket.arn
  }
}

resource "aws_iam_policy" "firehose-role-policy" {
  name        = "firehose-dvault-role-policy"
  description = "firehose-dvault-role-policy"

  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {      
            "Effect": "Allow",      
            "Action": [
                "s3:AbortMultipartUpload",
                "s3:GetBucketLocation",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:ListBucketMultipartUploads",
                "s3:PutObject"
            ],      
            "Resource": [        
                "${aws_s3_bucket.dvault-staging-bucket.arn}",
                "${aws_s3_bucket.dvault-staging-bucket.arn}/*"		    
            ]    
        }, 
        {
            "Effect": "Allow",
            "Action": [
                "kinesis:DescribeStream",
                "kinesis:GetShardIterator",
                "kinesis:GetRecords",
                "kinesis:ListShards"
            ],
            "Resource": "${aws_kinesis_firehose_delivery_stream.dvault-staging-stream.arn}"
        }
    ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "attach-dvault-firehose-policy" {
  role       = aws_iam_role.firehose_role.name
  policy_arn = aws_iam_policy.firehose-role-policy.arn
}

#Event bus configuration
resource "aws_cloudwatch_event_bus" "ai-dvault-eventbus" {
  name = "ai-dvault-eventbus-staging"
}

resource "aws_cloudwatch_event_permission" "ai-dvault-eventbus-permission" {
  for_each  = var.cloudwatch-eventpermission-map
  principal = each.value.principal
  #principal = var.source-account-id
  statement_id = "DVaultAccess-${each.key}"

  event_bus_name = aws_cloudwatch_event_bus.ai-dvault-eventbus.name
}

resource "aws_cloudwatch_event_rule" "ai-dvault-send-rule" {
  name        = "ai-dvault-send-rule"
  description = "AI rule for receiving dvault events"

  event_bus_name = aws_cloudwatch_event_bus.ai-dvault-eventbus.name

  event_pattern = <<EOF
  {
  
  "detail-type": [
    "shape.dvault"
  ]
  }
  EOF
}

#Iam role for event target
resource "aws_iam_role" "ai-dvault-event-target-rule-role" {
  name = "ai-dvault-event-target-rule-role"

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

resource "aws_iam_policy" "ai-dvault-event-target-rule-policy" {
  name        = "ai-dvault-event-target-rule-policy"
  description = "ai-dvault-event-target-rule-role"

  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "firehose:PutRecord",
                "firehose:PutRecordBatch"
            ],
            "Resource": [
                "${aws_kinesis_firehose_delivery_stream.dvault-staging-stream.arn}"
            ]
        }
    ]
}
EOF

}

resource "aws_iam_role_policy_attachment" "attach-dvault-event-target-role-policy" {
  role       = aws_iam_role.ai-dvault-event-target-rule-role.name
  policy_arn = aws_iam_policy.ai-dvault-event-target-rule-policy.arn
}

resource "aws_cloudwatch_event_target" "dvault-event-target" {
  arn  = aws_kinesis_firehose_delivery_stream.dvault-staging-stream.arn #Target resource arn
  rule = aws_cloudwatch_event_rule.ai-dvault-send-rule.name

  event_bus_name = aws_cloudwatch_event_bus.ai-dvault-eventbus.name

  role_arn = aws_iam_role.ai-dvault-event-target-rule-role.arn
}
