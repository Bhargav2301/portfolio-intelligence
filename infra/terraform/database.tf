resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_rds_cluster" "postgres" {
  cluster_identifier                    = "${local.name}-postgres"
  engine                                = "postgres"
  engine_version                        = "16.4"
  db_cluster_instance_class             = "db.m6gd.large"
  database_name                         = "portfolio_intelligence"
  master_username                       = "spi_admin"
  manage_master_user_password           = true
  master_user_secret_kms_key_id         = aws_kms_key.secrets.arn
  allocated_storage                     = 100
  storage_type                          = "gp3"
  iops                                  = 3000
  availability_zones                    = local.azs
  db_subnet_group_name                  = aws_db_subnet_group.main.name
  vpc_security_group_ids                = [aws_security_group.database.id]
  storage_encrypted                     = true
  kms_key_id                            = aws_kms_key.application.arn
  backup_retention_period               = 35
  preferred_backup_window               = "18:30-19:30"
  preferred_maintenance_window          = "sun:19:30-sun:20:30"
  copy_tags_to_snapshot                 = true
  deletion_protection                   = true
  skip_final_snapshot                   = false
  final_snapshot_identifier             = "${local.name}-final"
  iam_database_authentication_enabled   = true
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]
  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.observability.arn
  performance_insights_retention_period = 731

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_db_proxy" "main" {
  name                   = "${local.name}-postgres"
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 1800
  require_tls            = true
  default_auth_scheme    = "IAM_AUTH"
  role_arn               = aws_iam_role.rds_proxy.arn
  vpc_subnet_ids         = aws_subnet.private[*].id
  vpc_security_group_ids = [aws_security_group.rds_proxy.id]

}

resource "aws_db_proxy_default_target_group" "main" {
  db_proxy_name = aws_db_proxy.main.name

  connection_pool_config {
    connection_borrow_timeout    = 120
    max_connections_percent      = 80
    max_idle_connections_percent = 40
    session_pinning_filters      = ["EXCLUDE_VARIABLE_SETS"]
  }
}

resource "aws_db_proxy_target" "main" {
  db_cluster_identifier = aws_rds_cluster.postgres.id
  db_proxy_name         = aws_db_proxy.main.name
  target_group_name     = aws_db_proxy_default_target_group.main.name
}

resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name}-redis"
  description                = "Sessions, locks, and short-lived coordination only"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.t4g.small"
  port                       = 6379
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token
  kms_key_id                 = aws_kms_key.application.arn
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]
  snapshot_retention_limit   = 7
  apply_immediately          = false
}
