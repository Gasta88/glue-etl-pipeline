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
                "s3:ListBucket",
                "s3:GetReplicationConfiguration",
                "s3:GetObjectVersionForReplication",
                "s3:GetObjectVersionAcl",
                "s3:GetObjectVersionTagging",
                "s3:GetObjectRetention",
                "s3:GetObjectLegalHold"
            ],
            "Effect": "Allow",
            "Resource": [
                "${aws_s3_bucket.shape-media-library-sync-prod.arn}",
                "${aws_s3_bucket.shape-file-source-sync-prod.arn}",
                "${aws_s3_bucket.shape-bucket-storage-sync-prod.arn}",
                "${aws_s3_bucket.ai-dvault-sync-prod.arn}",
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
                "s3:ReplicateTags",
                "s3:GetObjectVersionTagging",
                "s3:ObjectOwnerOverrideToBucketOwner"
            ],
            "Effect": "Allow",
            "Condition": {
                "StringLikeIfExists": {
                    "s3:x-amz-server-side-encryption": [
                        "aws:kms",
                        "AES256"
                    ]
                }
            },
            "Resource": [
                "${aws_s3_bucket.shape-media-library-sync-prod-central.arn}/*",
                "${aws_s3_bucket.shape-file-source-sync-prod-central.arn}/*",
                "${aws_s3_bucket.shape-bucket-storage-sync-prod-central.arn}/*",
                "${aws_s3_bucket.ai-dvault-sync-prod-central.arn}/*"
            ]
        },
        {
            "Action": [
                "kms:Decrypt"
            ],
            "Effect": "Allow",
            "Condition": {
                "StringLike": {
                    "kms:ViaService": "s3.eu-west-1.amazonaws.com",
                    "kms:EncryptionContext:aws:s3:arn": [
                        "${aws_s3_bucket.shape-media-library-sync-prod.arn}/*",
                        "${aws_s3_bucket.shape-file-source-sync-prod.arn}/*",
                        "${aws_s3_bucket.shape-bucket-storage-sync-prod.arn}/*",
                        "${aws_s3_bucket.ai-dvault-sync-prod.arn}/*"
                    ]
                }
            },
            "Resource": [
                "${aws_kms_key.key.arn}"
            ]
        },
        {
            "Action": [
                "kms:Encrypt"
            ],
            "Effect": "Allow",
            "Condition": {
                "StringLike": {
                    "kms:ViaService": [
                        "s3.eu-central-1.amazonaws.com"
                    ],
                    "kms:EncryptionContext:aws:s3:arn": [
                        "${aws_s3_bucket.shape-media-library-sync-prod-central.arn}/*",
                        "${aws_s3_bucket.shape-file-source-sync-prod-central.arn}/*",
                        "${aws_s3_bucket.shape-bucket-storage-sync-prod-central.arn}/*",
                        "${aws_s3_bucket.ai-dvault-sync-prod-central.arn}/*"
                    ]
                }
            },
            "Resource": [
                "${aws_kms_key.key-central.arn}"
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