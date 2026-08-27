resource "aws_ecr_repository" "service" {
  for_each = toset(keys(local.services))

  name                 = "${local.name}/${replace(each.key, "_", "-")}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.application.arn
  }

  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_repository" "migration" {
  name                 = "${local.name}/migration"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.application.arn
  }

  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "service" {
  for_each = aws_ecr_repository.service

  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain the most recent 100 immutable images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 100
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enhanced"
  }
}

resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${local.name}.internal"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "service" {
  for_each = local.services

  name = replace(each.key, "_", "-")

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {}
}

resource "aws_cloudwatch_log_group" "service" {
  for_each = local.services

  name              = "/spi/${var.environment}/${replace(each.key, "_", "-")}"
  retention_in_days = var.environment == "production" ? 90 : 30
  kms_key_id        = aws_kms_key.observability.arn
}

resource "aws_cloudwatch_log_group" "migration" {
  name              = "/spi/${var.environment}/migration"
  retention_in_days = var.environment == "production" ? 90 : 30
  kms_key_id        = aws_kms_key.observability.arn
}

locals {
  image_uri = {
    for name, repository in aws_ecr_repository.service :
    name => "${repository.repository_url}@${lookup(var.image_digests, name, local.bootstrap_digest)}"
  }

  common_environment = [
    { name = "APP_ENV", value = var.environment },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://localhost:4318" },
    { name = "OTEL_RESOURCE_ATTRIBUTES", value = "deployment.environment=${var.environment}" },
  ]
}

resource "aws_ecs_task_definition" "service" {
  for_each = local.services

  family                   = "${local.name}-${replace(each.key, "_", "-")}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.key == "api" || each.key == "agents" ? 1024 : 512
  memory                   = each.key == "api" ? 3072 : each.key == "agents" ? 2048 : 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task[each.key].arn

  container_definitions = jsonencode(concat([
    {
      name                   = replace(each.key, "_", "-")
      image                  = local.image_uri[each.key]
      essential              = true
      readonlyRootFilesystem = true
      portMappings = [{
        containerPort = each.value.port
        hostPort      = each.value.port
        protocol      = "tcp"
      }]
      environment = concat(local.common_environment, each.key == "web" ? [
        { name = "INTERNAL_API_URL", value = "http://api.${local.name}.internal:8000" },
        { name = "INTERNAL_AGENT_URL", value = "http://agents.${local.name}.internal:8001" },
        { name = "OIDC_ISSUER_URL", value = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}" },
        { name = "OIDC_CLIENT_ID", value = aws_cognito_user_pool_client.bff.id },
        { name = "OIDC_OAUTH_BASE_URL", value = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com" },
        { name = "OIDC_REDIRECT_URI", value = "https://${var.public_app_domain}/api/auth/callback" },
        { name = "PUBLIC_APP_ORIGIN", value = "https://${var.public_app_domain}" },
        ] : each.key == "api" ? [
        { name = "DATABASE_URL", value = "postgresql+asyncpg://spi_runtime@${aws_db_proxy.main.endpoint}:5432/portfolio_intelligence" },
        { name = "RDS_IAM_AUTH", value = "true" },
        { name = "STORAGE_BACKEND", value = "s3" },
        { name = "OBJECT_STORAGE_BUCKET", value = aws_s3_bucket.private["quarantine"].id },
        { name = "OBJECT_STORAGE_REGION", value = var.aws_region },
        { name = "OBJECT_STORAGE_KMS_KEY_ID", value = aws_kms_key.documents.arn },
        { name = "OBJECT_STORAGE_SECURE", value = "true" },
        { name = "DIRECT_UPLOAD_ENABLED", value = "false" },
        { name = "MALWARE_SCAN_REQUIRED", value = "true" },
        { name = "CLAMAV_HOST", value = "127.0.0.1" },
        { name = "CLAMAV_PORT", value = "3310" },
        { name = "IDENTITY_PROPAGATION_ENABLED", value = tostring(var.identity_gate_passed) },
        { name = "RLS_VERIFICATION_COMPLETE", value = tostring(var.rls_gate_passed) },
        { name = "TELEMETRY_REDACTION_VERIFIED", value = tostring(var.telemetry_gate_passed) },
        { name = "ALLOWED_ORIGINS", value = "https://${var.public_app_domain}" },
        { name = "OIDC_ISSUER_URL", value = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}" },
        { name = "OIDC_CLIENT_ID", value = aws_cognito_user_pool_client.bff.id },
        { name = "JOB_QUEUE_URL", value = aws_sqs_queue.jobs.url },
        { name = "AUDIT_QUEUE_URL", value = aws_sqs_queue.audit.url },
        { name = "KMS_DATA_KEY_ID", value = aws_kms_key.application.arn },
        { name = "KMS_CAPABILITY_SIGNING_KEY_ID", value = aws_kms_key.capabilities.arn },
        ] : each.key == "agents" ? [
        { name = "CORE_API_URL", value = "http://api.${local.name}.internal:8000" },
        { name = "POSTGRES_CHECKPOINT_DSN", value = "postgresql://spi_checkpoint@${aws_db_proxy.main.endpoint}:5432/portfolio_intelligence?sslmode=require" },
        { name = "RDS_IAM_AUTH", value = "true" },
        { name = "DURABLE_CHECKPOINTS_ENABLED", value = "true" },
        { name = "OIDC_ISSUER_URL", value = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}" },
        { name = "OIDC_CLIENT_ID", value = aws_cognito_user_pool_client.bff.id },
        { name = "IDENTITY_PROPAGATION_ENABLED", value = tostring(var.identity_gate_passed) },
        { name = "AGENT_EVALUATION_VERIFIED", value = tostring(var.agent_evaluation_gate_passed) },
        { name = "OPENAI_MODEL", value = var.approved_openai_model },
        ] : each.key == "order_gateway" ? [
        { name = "LIVE_ORDERS_ENABLED", value = tostring(local.live_order_gate_open) },
        { name = "CAPABILITY_PUBLIC_KEY_ID", value = aws_kms_key.capabilities.arn },
      ] : [])
      secrets = each.key == "web" ? [
        { name = "OIDC_CLIENT_SECRET", valueFrom = "${aws_secretsmanager_secret.application["cognito-bff"].arn}:client_secret::" },
        { name = "SESSION_SECRET", valueFrom = "${aws_secretsmanager_secret.application["server-session"].arn}:session_secret::" },
        { name = "REDIS_URL", valueFrom = "${aws_secretsmanager_secret.application["redis"].arn}:url::" },
        ] : each.key == "agents" ? [
        { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.application["openai"].arn}:api_key::" },
      ] : []
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "app"
        }
      }
      dependsOn   = [{ containerName = "adot", condition = "START" }]
      mountPoints = [{ sourceVolume = "tmp", containerPath = "/tmp", readOnly = false }]
      healthCheck = {
        command = each.key == "web" ? [
          "CMD-SHELL", "wget -q -O - http://localhost:${each.value.port}/health/ready >/dev/null || exit 1"
          ] : [
          "CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${each.value.port}/health/ready')\""
        ]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
    },
    {
      name                   = "adot"
      image                  = "public.ecr.aws/aws-observability/aws-otel-collector:v0.43.3"
      essential              = true
      readonlyRootFilesystem = true
      command                = ["--config=/etc/ecs/ecs-default-config.yaml"]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "adot"
        }
      }
    }
    ], each.key == "api" ? [
    {
      name                   = "clamav"
      image                  = "clamav/clamav:1.4"
      essential              = true
      readonlyRootFilesystem = false
      mountPoints = [
        { sourceVolume = "clamav-data", containerPath = "/var/lib/clamav", readOnly = false },
        { sourceVolume = "tmp", containerPath = "/tmp", readOnly = false },
      ]
      healthCheck = {
        command     = ["CMD-SHELL", "clamdscan --ping 1"]
        interval    = 30
        timeout     = 10
        retries     = 5
        startPeriod = 120
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "clamav"
        }
      }
    }
  ] : []))

  volume { name = "tmp" }
  volume { name = "clamav-data" }

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${local.name}-migration"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task["migration"].arn

  container_definitions = jsonencode([{
    name                   = "migration"
    image                  = "${aws_ecr_repository.migration.repository_url}@${lookup(var.image_digests, "migration", local.bootstrap_digest)}"
    essential              = true
    readonlyRootFilesystem = true
    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "MIGRATION_DB_HOST", value = aws_db_proxy.main.endpoint },
      { name = "MIGRATION_DB_PORT", value = "5432" },
      { name = "MIGRATION_DB_NAME", value = "portfolio_intelligence" },
      { name = "MIGRATION_DB_USER", value = "spi_migration" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.migration.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "migration"
      }
    }
  }])
}

resource "aws_ecs_service" "service" {
  for_each = local.services

  name                               = replace(each.key, "_", "-")
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.service[each.key].arn
  desired_count                      = each.value.desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "LATEST"
  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100
  enable_execute_command             = false
  health_check_grace_period_seconds  = each.key == "web" ? 60 : null

  network_configuration {
    subnets          = aws_subnet.private[*].id
    assign_public_ip = false
    security_groups = [
      each.key == "web" ? aws_security_group.web.id :
      each.key == "api" ? aws_security_group.api.id :
      each.key == "agents" ? aws_security_group.agents.id :
      each.key == "order_gateway" ? aws_security_group.order_gateway.id :
      aws_security_group.ingestion.id
    ]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.service[each.key].arn
  }

  dynamic "load_balancer" {
    for_each = each.key == "web" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.web.arn
      container_name   = "web"
      container_port   = 3000
    }
  }

  deployment_controller {
    type = each.key == "web" ? "CODE_DEPLOY" : "ECS"
  }

  lifecycle {
    ignore_changes = [task_definition, desired_count]

    precondition {
      condition = each.value.desired_count == 0 || (
        var.identity_gate_passed && var.rls_gate_passed && var.telemetry_gate_passed
      )
      error_message = "Services cannot receive traffic before identity, forced-RLS, and telemetry gates pass."
    }
  }
}

data "aws_iam_policy_document" "codedeploy_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codedeploy.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codedeploy" {
  name               = "${local.name}-codedeploy"
  assume_role_policy = data.aws_iam_policy_document.codedeploy_assume.json
}

resource "aws_iam_role_policy_attachment" "codedeploy" {
  role       = aws_iam_role.codedeploy.name
  policy_arn = "arn:aws:iam::aws:policy/AWSCodeDeployRoleForECS"
}

resource "aws_codedeploy_app" "web" {
  name             = "${local.name}-web"
  compute_platform = "ECS"
}

resource "aws_codedeploy_deployment_config" "canary" {
  deployment_config_name = "${local.name}-ecs-canary-5-15"
  compute_platform       = "ECS"

  traffic_routing_config {
    type = "TimeBasedCanary"
    time_based_canary {
      interval   = 15
      percentage = 5
    }
  }
}

resource "aws_codedeploy_deployment_group" "web" {
  app_name               = aws_codedeploy_app.web.name
  deployment_group_name  = "${local.name}-web"
  service_role_arn       = aws_iam_role.codedeploy.arn
  deployment_config_name = aws_codedeploy_deployment_config.canary.id

  ecs_service {
    cluster_name = aws_ecs_cluster.main.name
    service_name = aws_ecs_service.service["web"].name
  }

  deployment_style {
    deployment_option = "WITH_TRAFFIC_CONTROL"
    deployment_type   = "BLUE_GREEN"
  }

  blue_green_deployment_config {
    deployment_ready_option {
      action_on_timeout = "CONTINUE_DEPLOYMENT"
    }
    terminate_blue_instances_on_deployment_success {
      action                           = "TERMINATE"
      termination_wait_time_in_minutes = 15
    }
  }

  load_balancer_info {
    target_group_pair_info {
      prod_traffic_route {
        listener_arns = [aws_lb_listener.https.arn]
      }
      target_group { name = aws_lb_target_group.web.name }
      target_group { name = aws_lb_target_group.web_green.name }
    }
  }

  alarm_configuration {
    alarms  = [aws_cloudwatch_metric_alarm.service_errors["web"].alarm_name]
    enabled = true
  }

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM", "DEPLOYMENT_STOP_ON_REQUEST"]
  }
}

resource "aws_appautoscaling_target" "service" {
  for_each = local.services

  max_capacity       = each.key == "web" || each.key == "api" ? 10 : 20
  min_capacity       = each.value.desired_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.service[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  for_each = local.services

  name               = "${local.name}-${each.key}-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.service[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.service[each.key].scalable_dimension
  service_namespace  = aws_appautoscaling_target.service[each.key].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 60
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
