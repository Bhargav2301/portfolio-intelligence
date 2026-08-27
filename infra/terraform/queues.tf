resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${local.name}-jobs-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = aws_kms_key.application.arn
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${local.name}-jobs"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 1209600
  receive_wait_time_seconds  = 20
  kms_master_key_id          = aws_kms_key.application.arn
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue" "audit_dlq" {
  name                      = "${local.name}-audit-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = aws_kms_key.observability.arn
}

resource "aws_sqs_queue" "audit" {
  name                       = "${local.name}-audit"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600
  kms_master_key_id          = aws_kms_key.observability.arn
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.audit_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_sns_topic" "alerts" {
  name              = "${local.name}-security-operations"
  kms_master_key_id = aws_kms_key.observability.id
}
