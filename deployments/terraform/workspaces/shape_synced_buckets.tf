/* Not in active use since these are synced by Architecture

#Create s3 bucket that should be synced with
resource "aws_s3_bucket" "shape-media-library" {
  bucket = "shape-media-library"
  acl    = "private"
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
  versioning {
    enabled = true
  }
}

resource "aws_s3_bucket_policy" "shape-media-library-bucket-policy" {
  bucket = aws_s3_bucket.shape-media-library.id

  # Terraform's "jsonencode" function converts a
  # Terraform expression's result to valid JSON syntax.
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "shape-media-library-bucket-policy"
    Statement = [
      {
        Sid       = "Set Permission for objects and bucket"
        Effect    = "Allow"
        Principal = { "AWS" : var.shape-replication-role-medialibrary }
        Action    = ["s3:ReplicateObject", "s3:ReplicateDelete", "s3:ObjectOwnerOverrideToBucketOwner"]
        Resource = [
          "${aws_s3_bucket.shape-media-library.arn}/*",
        ]
      },
      {
        Sid       = "Set Permission for objects and bucket"
        Effect    = "Allow"
        Principal = { "AWS" : var.shape-replication-role-medialibrary }
        Action    = ["s3:GetBucketVersioning", "s3:PutBucketVersioning"]
        Resource = [
          aws_s3_bucket.shape-media-library.arn
        ]
      }
    ]
  })
}

resource "aws_s3_bucket" "shape-file-source" {
  bucket = "shape-file-source"
  acl    = "private"
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
  versioning {
    enabled = true
  }
}

resource "aws_s3_bucket_policy" "shape-file-source-bucket-policy" {
  bucket = aws_s3_bucket.shape-file-source.id

  # Terraform's "jsonencode" function converts a
  # Terraform expression's result to valid JSON syntax.
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "shape-file-source-bucket-policy"
    Statement = [
      {
        Sid       = "Set Permission for objects and bucket"
        Effect    = "Allow"
        Principal = { "AWS" : var.shape-replication-role-filesource }
        Action    = ["s3:ReplicateObject", "s3:ReplicateDelete", "s3:ObjectOwnerOverrideToBucketOwner"]
        Resource = [
          "${aws_s3_bucket.shape-file-source.arn}/*",
        ]
      },
      {
        Sid       = "Set Permission for objects and bucket"
        Effect    = "Allow"
        Principal = { "AWS" : var.shape-replication-role-filesource }
        Action    = ["s3:GetBucketVersioning", "s3:PutBucketVersioning"]
        Resource = [
          aws_s3_bucket.shape-file-source.arn
        ]
      }
    ]
  })
}

resource "aws_s3_bucket" "shape-bucket-storage" {
  bucket = "shape-bucket-storage"
  acl    = "private"
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
  versioning {
    enabled = true
  }
}

resource "aws_s3_bucket_policy" "shape-bucket-storage-policy" {
  bucket = aws_s3_bucket.shape-bucket-storage.id

  # Terraform's "jsonencode" function converts a
  # Terraform expression's result to valid JSON syntax.
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "shape-bucket-storage-policy"
    Statement = [
      {
        Sid       = "Set Permission for objects and bucket"
        Effect    = "Allow"
        Principal = { "AWS" : var.shape-replication-role-bucket-storage }
        Action    = ["s3:ReplicateObject", "s3:ReplicateDelete", "s3:ObjectOwnerOverrideToBucketOwner"]
        Resource = [
          "${aws_s3_bucket.shape-bucket-storage.arn}/*",
        ]
      },
      {
        Sid       = "Set Permission for objects and bucket"
        Effect    = "Allow"
        Principal = { "AWS" : var.shape-replication-role-bucket-storage }
        Action    = ["s3:GetBucketVersioning", "s3:PutBucketVersioning"]
        Resource = [
          aws_s3_bucket.shape-bucket-storage.arn
        ]
      }
    ]
  })
}
*/
