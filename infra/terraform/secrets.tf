locals {
  secret_names = toset([
    "openai",
    "upstox-application",
    "market-data",
    "news-data",
    "cognito-bff",
    "server-session",
    "redis",
    "malware-scanner",
    "alerting",
    "agent-internal",
  ])
}

resource "aws_secretsmanager_secret_version" "cognito_bff" {
  secret_id = aws_secretsmanager_secret.application["cognito-bff"].id
  secret_string = jsonencode({
    client_secret = aws_cognito_user_pool_client.bff.client_secret
  })

  lifecycle { ignore_changes = [secret_string] }
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.application["redis"].id
  secret_string = jsonencode({
    url = "rediss://:${urlencode(var.redis_auth_token)}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379"
  })

  lifecycle { ignore_changes = [secret_string] }
}

resource "aws_secretsmanager_secret" "application" {
  for_each = local.secret_names

  name                    = "${local.name}/${each.key}"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 30
}

# Per-user Upstox grants use tenant/user-scoped names and envelope-encrypted values created
# only by the Core API. Terraform creates the key and IAM boundary, never token values.
resource "aws_secretsmanager_secret" "broker_grant_envelope" {
  name                    = "${local.name}/broker-grant-envelope-metadata"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 30
}
