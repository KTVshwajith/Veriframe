terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
  }

  # For team use, store state remotely, e.g.:
  # backend "s3" {
  #   bucket       = "my-tf-state-bucket"
  #   key          = "veriframe/terraform.tfstate"
  #   region       = "ap-southeast-2"
  #   use_lockfile = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "veriframe"
      ManagedBy = "terraform"
    }
  }
}
