variable "region" {
  default = "us-east-1"
}

variable "profile" {
  default = "default"
}

variable "source-account-id" {
  default = "228718274899"
}
variable "cloudwatch-eventpermission-map" {
  default = {
    account_shape_dev = {
      principal = "767115741234"
    },
    account_vcoach_dev = {
      principal = "541436412055" #vcoach accocunt id for testing
    }, 

    account_informal_dev = {
      principal = "426132435523"
    }
  }
}

variable "shape-replication-role-medialibrary" {
  description = "The AWS role arn used by shape source account for s3 media library replication"
  type = string
}

variable "shape-replication-role-filesource" {
  description = "The AWS role arn used by shape source account for s3 source file replication"
  type = string
}

variable "shape-replication-role-bucket-storage" {
  description = "The AWS role arn used by shape source account for s3 bucket storage file replication"
  type = string
}