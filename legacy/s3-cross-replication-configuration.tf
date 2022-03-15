resource "aws_s3_bucket_replication_configuration" "shape-media-library-sync-prod-replication" {
  provider = aws.europe
  role     = aws_iam_role.replication.arn
  bucket   = aws_s3_bucket.shape-media-library-sync-prod.id
  rule {
    status = "Enabled"
    destination {
      bucket        = aws_s3_bucket.shape-media-library-sync-prod-central.arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = aws_kms_key.key-central.arn
      }
    }
    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }
  }
}

resource "aws_s3_bucket_replication_configuration" "shape-file-source-sync-prod-replication" {
  provider = aws.europe
  role     = aws_iam_role.replication.arn
  bucket   = aws_s3_bucket.shape-file-source-sync-prod.id
  rule {
    status = "Enabled"
    destination {
      bucket        = aws_s3_bucket.shape-file-source-sync-prod-central.arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = aws_kms_key.key-central.arn
      }
    }
    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }
  }
}

resource "aws_s3_bucket_replication_configuration" "shape-bucket-storage-sync-prod-replication" {
  provider = aws.europe
  role     = aws_iam_role.replication.arn
  bucket   = aws_s3_bucket.shape-bucket-storage-sync-prod.id
  rule {
    status = "Enabled"
    destination {
      bucket        = aws_s3_bucket.shape-bucket-storage-sync-prod-central.arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = aws_kms_key.key-central.arn
      }
    }
    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }
  }
}

resource "aws_s3_bucket_replication_configuration" "ai-dvault-sync-prod-replication" {
  provider = aws.europe
  role     = aws_iam_role.replication.arn
  bucket   = aws_s3_bucket.ai-dvault-sync-prod.id
  rule {
    status = "Enabled"
    destination {
      bucket        = aws_s3_bucket.ai-dvault-sync-prod-central.arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = aws_kms_key.key-central.arn
      }
    }
    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }
  }
}
