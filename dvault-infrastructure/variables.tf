variable "region" {
  default = "us-east-1"
}

variable "profile" {
  default = "default"
}

variable "source-account-id" {
  default = "228718274899"
}

variable "tf-state-filekey" {
  default = "ai-terraform-state-files/dvault-shape-staging.tfstate"
}

variable "tf-state-bucket-name" {
  default = "terraform-ai-dev-states"
}