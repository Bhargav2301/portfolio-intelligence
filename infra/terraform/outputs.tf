output "application_url" {
  value = "https://${var.public_app_domain}"
}

output "deployment_role_arn" {
  value = aws_iam_role.github_deploy.arn
}

output "ecr_repository_urls" {
  value = merge(
    { for name, repository in aws_ecr_repository.service : name => repository.repository_url },
    { migration = aws_ecr_repository.migration.repository_url },
  )
}

output "rds_proxy_endpoint" {
  value     = aws_db_proxy.main.endpoint
  sensitive = true
}

output "cognito" {
  value = {
    issuer    = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
    client_id = aws_cognito_user_pool_client.bff.id
    domain    = aws_cognito_user_pool_domain.main.domain
  }
}

output "production_gate_open" {
  value = local.production_gate_open
}

output "live_order_gate_open" {
  value = local.live_order_gate_open
}

output "migration_runtime" {
  value = {
    cluster         = aws_ecs_cluster.main.name
    task_definition = aws_ecs_task_definition.migration.family
    subnet_ids      = aws_subnet.private[*].id
    security_group  = aws_security_group.ingestion.id
  }
}
