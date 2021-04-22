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