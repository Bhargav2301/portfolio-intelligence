resource "aws_backup_vault" "primary" {
  name        = "${local.name}-primary"
  kms_key_arn = aws_kms_key.application.arn
}

resource "aws_kms_key" "backup" {
  provider = aws.backup

  description             = "${local.name} cross-region backups"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_backup_vault" "secondary" {
  provider = aws.backup

  name        = "${local.name}-secondary"
  kms_key_arn = aws_kms_key.backup.arn
}

resource "aws_backup_plan" "database" {
  name = "${local.name}-database"

  rule {
    rule_name         = "continuous-and-cross-region"
    target_vault_name = aws_backup_vault.primary.name
    schedule          = "cron(0 * * * ? *)"
    start_window      = 60
    completion_window = 180

    lifecycle {
      delete_after = 35
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.secondary.arn
      lifecycle {
        delete_after = 35
      }
    }
  }
}

data "aws_iam_policy_document" "backup_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["backup.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backup" {
  name               = "${local.name}-backup"
  assume_role_policy = data.aws_iam_policy_document.backup_assume.json
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_backup_selection" "database" {
  name         = "${local.name}-database"
  plan_id      = aws_backup_plan.database.id
  iam_role_arn = aws_iam_role.backup.arn
  resources    = [aws_rds_cluster.postgres.arn]
}
