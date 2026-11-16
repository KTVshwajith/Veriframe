variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-2" # Sydney — closest region to New Zealand
}

variable "name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "veriframe"
}

variable "image_tag" {
  description = "Initial image tag. Later deploys are done by the GitHub Actions pipeline."
  type        = string
  default     = "latest"
}

variable "desired_count" {
  description = "Number of running API tasks"
  type        = number
  default     = 1
}

variable "github_repository" {
  description = "GitHub repo allowed to deploy, as owner/name"
  type        = string
  default     = "KTVshwajith/veriframe"
}

variable "create_github_oidc_provider" {
  description = "Set false if the AWS account already has the GitHub OIDC provider"
  type        = bool
  default     = true
}
