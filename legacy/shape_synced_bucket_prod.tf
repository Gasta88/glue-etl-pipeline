#Alternative provider for different region
provider "aws" {
  alias   = "europe"
  region  = "eu-west-1"
  profile = "default"
}

#Create KMS key to bucket ecryption
resource "aws_kms_key" "key" {
  provider                = aws.europe
  description             = "sync-prod-key"
  deletion_window_in_days = 7
}

resource "aws_kms_alias" "kms_key_alias" {
  provider      = aws.europe
  name          = "alias/sync-prod-key"
  target_key_id = aws_kms_key.key.key_id
}
#Create s3 bucket that should contain the buckets access logging
resource "aws_s3_bucket" "log_bucket" {
  provider = aws.europe
  bucket   = "sync-prod-access-logging"
  acl      = "private"
}
#Create s3 bucket that should be sync with
resource "aws_s3_bucket" "shape-media-library-sync-prod" {
  provider = aws.europe
  bucket   = "shape-media-library-sync-prod-eu"
  acl      = "private"
  logging {
    target_bucket = aws_s3_bucket.log_bucket.id
    target_prefix = "log/shape-media-library-sync-prod/"
  }
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.key.key_id
        sse_algorithm     = "aws:kms"
      }
    }
  }
  versioning {
    enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "shape-media-library-sync-prod" {
  provider                = aws.europe
  bucket                  = aws_s3_bucket.shape-media-library-sync-prod.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
# resource "aws_s3_bucket_policy" "shape-media-library-bucket-policy" {
#   bucket = aws_s3_bucket.shape-media-library.id

#   # Terraform's "jsonencode" function converts a
#   # Terraform expression's result to valid JSON syntax.
#   policy = jsonencode({
#     Version = "2012-10-17"
#     Id      = "shape-media-library-bucket-policy"
#     Statement = [
#       {
#         Sid       = "Set Permission for objects and bucket"
#         Effect    = "Allow"
#         Principal = {"AWS": var.shape-replication-role-medialibrary}
#         Action    = ["s3:ReplicateObject", "s3:ReplicateDelete", "s3:ObjectOwnerOverrideToBucketOwner"]
#         Resource = [
#           "${aws_s3_bucket.shape-media-library.arn}/*",
#         ]
#       },
#       {
#         Sid       = "Set Permission for objects and bucket"
#         Effect    = "Allow"
#         Principal = {"AWS": var.shape-replication-role-medialibrary}
#         Action    = ["s3:GetBucketVersioning", "s3:PutBucketVersioning"]
#         Resource = [
#           aws_s3_bucket.shape-media-library.arn
#         ]
#       }
#     ]
#   })
# }

resource "aws_s3_bucket" "shape-file-source-sync-prod" {
  provider = aws.europe
  bucket   = "shape-file-source-sync-prod-eu"
  acl      = "private"
  logging {
    target_bucket = aws_s3_bucket.log_bucket.id
    target_prefix = "log/shape-file-source-sync-prod/"
  }
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.key.key_id
        sse_algorithm     = "aws:kms"
      }
    }
  }
  versioning {
    enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "shape-file-source-sync-prod" {
  provider                = aws.europe
  bucket                  = aws_s3_bucket.shape-file-source-sync-prod.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
# resource "aws_s3_bucket_policy" "shape-file-source-bucket-policy" {
#   bucket = aws_s3_bucket.shape-file-source.id

#   # Terraform's "jsonencode" function converts a
#   # Terraform expression's result to valid JSON syntax.
#   policy = jsonencode({
#     Version = "2012-10-17"
#     Id      = "shape-file-source-bucket-policy"
#     Statement = [
#       {
#         Sid       = "Set Permission for objects and bucket"
#         Effect    = "Allow"
#         Principal = {"AWS": var.shape-replication-role-filesource}
#         Action    = ["s3:ReplicateObject", "s3:ReplicateDelete", "s3:ObjectOwnerOverrideToBucketOwner"]
#         Resource = [
#           "${aws_s3_bucket.shape-file-source.arn}/*",
#         ]
#       },
#       {
#         Sid       = "Set Permission for objects and bucket"
#         Effect    = "Allow"
#         Principal = {"AWS": var.shape-replication-role-filesource}
#         Action    = ["s3:GetBucketVersioning", "s3:PutBucketVersioning"]
#         Resource = [
#           aws_s3_bucket.shape-file-source.arn
#         ]
#       }
#     ]
#   })
# }

resource "aws_s3_bucket" "shape-bucket-storage-sync-prod" {
  provider = aws.europe
  bucket   = "shape-bucket-storage-sync-prod-eu"
  acl      = "private"
  logging {
    target_bucket = aws_s3_bucket.log_bucket.id
    target_prefix = "log/shape-bucket-storage-sync-prod/"
  }
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.key.key_id
        sse_algorithm     = "aws:kms"
      }
    }
  }
  versioning {
    enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "shape-bucket-storage-sync-prod" {
  provider                = aws.europe
  bucket                  = aws_s3_bucket.shape-bucket-storage-sync-prod.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
# resource "aws_s3_bucket_policy" "shape-bucket-storage-policy" {
#   bucket = aws_s3_bucket.shape-bucket-storage-staging.id

#   # Terraform's "jsonencode" function converts a
#   # Terraform expression's result to valid JSON syntax.
#   policy = jsonencode({
#     Version = "2012-10-17"
#     Id      = "shape-bucket-storage-policy"
#     Statement = [
#       {
#         Sid       = "Set Permission for objects and bucket"
#         Effect    = "Allow"
#         Principal = {"AWS": var.shape-replication-role-bucket-storage}
#         Action    = ["s3:ReplicateObject", "s3:ReplicateDelete", "s3:ObjectOwnerOverrideToBucketOwner"]
#         Resource = [
#           "${aws_s3_bucket.shape-bucket-storage-staging.arn}/*",
#         ]
#       },
#       {
#         Sid       = "Set Permission for objects and bucket"
#         Effect    = "Allow"
#         Principal = {"AWS": var.shape-replication-role-bucket-storage}
#         Action    = ["s3:GetBucketVersioning", "s3:PutBucketVersioning"]
#         Resource = [
#           aws_s3_bucket.shape-bucket-storage-staging.arn
#         ]
#       }
#     ]
#   })
# }

#Create s3 bucket that should be sync with
resource "aws_s3_bucket" "ai-dvault-sync-prod" {
  provider = aws.europe
  bucket   = "ai-dvault-sync-prod-eu"
  acl      = "private"
  logging {
    target_bucket = aws_s3_bucket.log_bucket.id
    target_prefix = "log/ai-dvault-sync-prod/"
  }
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.key.key_id
        sse_algorithm     = "aws:kms"
      }
    }
  }
  versioning {
    enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "ai-dvault-sync-prod" {
  provider                = aws.europe
  bucket                  = aws_s3_bucket.shape-bucket-storage-sync-prod.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
