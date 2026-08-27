resource "aws_cloudwatch_log_group" "audit" {
  name              = "/spi/${var.environment}/audit"
  retention_in_days = 2557
  kms_key_id        = aws_kms_key.observability.arn
}

resource "aws_cloudwatch_metric_alarm" "service_errors" {
  for_each = local.services

  alarm_name          = "${local.name}-${each.key}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ErrorCount"
  namespace           = "SPI/Application"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { Service = each.key, Environment = var.environment }
}

resource "aws_cloudwatch_metric_alarm" "dlq" {
  for_each = {
    jobs  = aws_sqs_queue.jobs_dlq.name
    audit = aws_sqs_queue.audit_dlq.name
  }

  alarm_name          = "${local.name}-${each.key}-dlq-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { QueueName = each.value }
}

resource "aws_cloudwatch_metric_alarm" "oldest_job" {
  alarm_name          = "${local.name}-job-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 120
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { QueueName = aws_sqs_queue.jobs.name }
}

resource "aws_cloudwatch_dashboard" "operations" {
  dashboard_name = "${local.name}-operations"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        x    = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "ECS CPU"
          region = var.aws_region
          metrics = [for name in keys(local.services) : [
            "AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name,
            "ServiceName", aws_ecs_service.service[name].name,
          ]]
          period = 300
          stat   = "Average"
        }
      },
      {
        type = "metric"
        x    = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "Durable queue health"
          region = var.aws_region
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.jobs.name],
            ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", aws_sqs_queue.jobs.name],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.jobs_dlq.name],
          ]
        }
      }
    ]
  })
}

resource "aws_scheduler_schedule_group" "main" {
  name = local.name
}

resource "aws_scheduler_schedule" "checkpoint_cleanup" {
  name       = "checkpoint-cleanup"
  group_name = aws_scheduler_schedule_group.main.name

  flexible_time_window { mode = "OFF" }
  schedule_expression = "cron(15 2 * * ? *)"
  state               = local.production_gate_open ? "ENABLED" : "DISABLED"

  target {
    arn      = aws_sqs_queue.jobs.arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      job_type       = "checkpoint_cleanup"
      retention_days = 30
    })
  }
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name}-eventbridge-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler" {
  name = "enqueue"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = [aws_sqs_queue.jobs.arn]
    }]
  })
}
