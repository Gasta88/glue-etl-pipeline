resource "aws_iam_role" "replication" {
  name = "s3-cross-region-replication-role"

  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "s3.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
POLICY
}

resource "aws_iam_policy" "replication" {
  name = "s3-cross-region-replication-policy"

  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "s3:GetReplicationConfiguration",
        "s3:ListBucket"
      ],
      "Effect": "Allow",
      "Resource": [
        "${aws_s3_bucket.shape-media-library-sync-prod.arn}",
        "${aws_s3_bucket.shape-file-source-sync-prod.arn}",
        "${aws_s3_bucket.shape-bucket-storage-sync-prod.arn}",
        "${aws_s3_bucket.ai-dvault-sync-prod.arn}"
      ]
    },
    {
      "Action": [
        "s3:GetObjectVersionForReplication",
        "s3:GetObjectVersionAcl",
         "s3:GetObjectVersionTagging"
      ],
      "Effect": "Allow",
      "Resource": [
        "${aws_s3_bucket.shape-media-library-sync-prod.arn}/*",
        "${aws_s3_bucket.shape-file-source-sync-prod.arn}/*",
        "${aws_s3_bucket.shape-bucket-storage-sync-prod.arn}/*",
        "${aws_s3_bucket.ai-dvault-sync-prod.arn}/*"
      ]
    },
    {
      "Action": [
        "s3:ReplicateObject",
        "s3:ReplicateDelete",
        "s3:ReplicateTags"
      ],
      "Effect": "Allow",
      "Resource": [
        "${aws_s3_bucket.shape-media-library-sync-prod-central.arn}/*",
        "${aws_s3_bucket.shape-file-source-sync-prod-central.arn}/*",
        "${aws_s3_bucket.shape-bucket-storage-sync-prod-central.arn}/*",
        "${aws_s3_bucket.ai-dvault-sync-prod-central.arn}/*"
      ]
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "replication" {
  role       = aws_iam_role.replication.name
  policy_arn = aws_iam_policy.replication.arn
}