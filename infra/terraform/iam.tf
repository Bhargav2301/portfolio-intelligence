data "aws_iam_policy_document" "ecs_tasks" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "task-secret-bootstrap"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [for secret in aws_secretsmanager_secret.application : secret.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [aws_kms_key.secrets.arn]
      }
    ]
  })
}

resource "aws_iam_role" "task" {
  for_each = toset(["web", "api", "agents", "ingestion", "order_gateway", "scheduler", "migration"])

  name               = "${local.name}-${replace(each.key, "_", "-")}"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks.json
}

data "aws_iam_policy_document" "api" {
  statement {
    sid       = "RuntimeDatabaseLogin"
    actions   = ["rds-db:connect"]
    resources = ["arn:aws:rds-db:${var.aws_region}:${data.aws_caller_identity.current.account_id}:dbuser:*/spi_runtime"]
  }

  statement {
    sid     = "QuarantineAndDocuments"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:GetObjectAttributes"]
    resources = [
      "${aws_s3_bucket.private["quarantine"].arn}/*",
      "${aws_s3_bucket.private["documents"].arn}/*",
      "${aws_s3_bucket.private["artifacts"].arn}/*",
    ]
  }

  statement {
    sid       = "DispatchDurableOutbox"
    actions   = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.jobs.arn, aws_sqs_queue.audit.arn]
  }

  statement {
    sid       = "CapabilitySigning"
    actions   = ["kms:Sign", "kms:GetPublicKey"]
    resources = [aws_kms_key.capabilities.arn]
  }

  statement {
    sid       = "ApplicationDecrypt"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.application.arn, aws_kms_key.documents.arn]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "runtime"
  role   = aws_iam_role.task["api"].id
  policy = data.aws_iam_policy_document.api.json
}

resource "aws_iam_role_policy" "migration" {
  name = "database-migrations-only"
  role = aws_iam_role.task["migration"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["rds-db:connect"]
      Resource = ["arn:aws:rds-db:${var.aws_region}:${data.aws_caller_identity.current.account_id}:dbuser:*/spi_migration"]
    }]
  })
}

data "aws_iam_policy_document" "web" {
  statement {
    sid       = "SessionSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.application["cognito-bff"].arn, aws_secretsmanager_secret.application["server-session"].arn]
  }

  statement {
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.secrets.arn]
  }
}

resource "aws_iam_role_policy" "web" {
  name   = "session-only"
  role   = aws_iam_role.task["web"].id
  policy = data.aws_iam_policy_document.web.json
}

data "aws_iam_policy_document" "agents" {
  statement {
    sid       = "CheckpointDatabaseLogin"
    actions   = ["rds-db:connect"]
    resources = ["arn:aws:rds-db:${var.aws_region}:${data.aws_caller_identity.current.account_id}:dbuser:*/spi_checkpoint"]
  }

  statement {
    sid     = "ApprovedModelAndEvidenceSecrets"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.application["openai"].arn,
      aws_secretsmanager_secret.application["market-data"].arn,
      aws_secretsmanager_secret.application["news-data"].arn,
    ]
  }

  statement {
    sid       = "DecryptApprovedSecrets"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.secrets.arn]
  }

  statement {
    sid    = "DenyBrokerAndExecutionCapabilities"
    effect = "Deny"
    actions = [
      "secretsmanager:GetSecretValue",
      "kms:Sign",
      "execute-api:Invoke",
      "servicediscovery:DiscoverInstances",
    ]
    resources = [
      aws_secretsmanager_secret.application["upstox-application"].arn,
      aws_secretsmanager_secret.broker_grant_envelope.arn,
      aws_kms_key.capabilities.arn,
      "arn:aws:execute-api:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*/prod/*/orders*",
      "arn:aws:servicediscovery:${var.aws_region}:${data.aws_caller_identity.current.account_id}:service/*",
    ]
  }
}

resource "aws_iam_role_policy" "agents" {
  name   = "proposal-only"
  role   = aws_iam_role.task["agents"].id
  policy = data.aws_iam_policy_document.agents.json
}

data "aws_iam_policy_document" "order_gateway" {
  statement {
    actions   = ["rds-db:connect"]
    resources = ["arn:aws:rds-db:${var.aws_region}:${data.aws_caller_identity.current.account_id}:dbuser:*/spi_order_gateway"]
  }

  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.application["upstox-application"].arn, aws_secretsmanager_secret.broker_grant_envelope.arn]
  }

  statement {
    actions   = ["kms:Decrypt", "kms:Verify"]
    resources = [aws_kms_key.secrets.arn, aws_kms_key.application.arn, aws_kms_key.capabilities.arn]
  }
}

resource "aws_iam_role_policy" "order_gateway" {
  name   = "human-orders-only"
  role   = aws_iam_role.task["order_gateway"].id
  policy = data.aws_iam_policy_document.order_gateway.json
}

data "aws_iam_policy_document" "rds_proxy_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rds_proxy" {
  name               = "${local.name}-rds-proxy"
  assume_role_policy = data.aws_iam_policy_document.rds_proxy_assume.json
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:environment:${var.environment}"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = "${local.name}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_assume.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "terraform-and-signed-release"
  role = aws_iam_role.github_deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnvironmentInfrastructure"
        Effect = "Allow"
        Action = [
          "application-autoscaling:*", "backup:*", "cloudfront:*", "cloudwatch:*",
          "codedeploy:*", "cognito-idp:*", "config:*", "ec2:*", "ecr:*", "ecs:*",
          "elasticache:*", "elasticloadbalancing:*", "kms:*", "logs:*", "rds:*",
          "route53:*", "scheduler:*", "secretsmanager:*", "servicediscovery:*",
          "guardduty:*", "inspector2:*", "securityhub:*", "sns:*", "sqs:*", "wafv2:*"
        ]
        Resource = "*"
      },
      {
        Sid    = "EnvironmentRolesOnly"
        Effect = "Allow"
        Action = [
          "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateAssumeRolePolicy",
          "iam:TagRole", "iam:UntagRole", "iam:PutRolePolicy", "iam:GetRolePolicy",
          "iam:DeleteRolePolicy", "iam:AttachRolePolicy", "iam:DetachRolePolicy",
          "iam:ListAttachedRolePolicies", "iam:ListRolePolicies", "iam:PassRole"
        ]
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.name}-*"
      },
      {
        Sid      = "EncryptedRemoteState"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [var.terraform_state_bucket_arn, "${var.terraform_state_bucket_arn}/*"]
      }
    ]
  })
}
