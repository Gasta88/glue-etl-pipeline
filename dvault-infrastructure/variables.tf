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
    account1 = {
      principal = "228718274899"
    },
    account2 = {
      principal = "541436412055" #vcoach accocunt id for testing
    }
  }
}