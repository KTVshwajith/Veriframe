output "app_url" {
  description = "Public URL of the service"
  value       = "http://${aws_lb.api.dns_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "github_deploy_role_arn" {
  description = "Set this as the AWS_DEPLOY_ROLE_ARN repository variable in GitHub"
  value       = aws_iam_role.github_deploy.arn
}

output "dynamodb_table" {
  value = aws_dynamodb_table.ledger.name
}
