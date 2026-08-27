resource "aws_lb" "web" {
  name                       = substr("${local.name}-web", 0, 32)
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.edge_alb.id]
  subnets                    = aws_subnet.public[*].id
  enable_deletion_protection = true
  drop_invalid_header_fields = true
  preserve_host_header       = true
}

resource "aws_lb_target_group" "web" {
  name        = substr("${local.name}-web", 0, 32)
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = "/"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 60
}

resource "aws_lb_target_group" "web_green" {
  name        = substr("${local.name}-web-green", 0, 32)
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = "/"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 60
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.web.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type = "forward"
    forward {
      target_group { arn = aws_lb_target_group.web.arn }
    }
  }
}

resource "aws_wafv2_ip_set" "operators" {
  provider = aws.global

  name               = "${local.name}-operators"
  scope              = "CLOUDFRONT"
  ip_address_version = "IPV4"
  addresses          = var.allowed_operator_cidrs
}

resource "aws_wafv2_web_acl" "edge" {
  provider = aws.global

  name  = "${local.name}-edge"
  scope = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 10
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "common"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 20
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "known-bad-inputs"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 30
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "ip-reputation"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 40
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "sqli"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "AuthenticationRateLimit"
    priority = 50
    action {
      block {}
    }
    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = 300
        scope_down_statement {
          byte_match_statement {
            positional_constraint = "STARTS_WITH"
            search_string         = "/api/auth/"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "auth-rate"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "ChatAndUploadRateLimit"
    priority = 60
    action {
      block {}
    }
    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = 600
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "application-rate"
      sampled_requests_enabled   = false
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = local.name
    sampled_requests_enabled   = false
  }
}

resource "aws_wafv2_web_acl" "origin" {
  name  = "${local.name}-origin"
  scope = "REGIONAL"

  default_action {
    block {}
  }

  rule {
    name     = "CloudFrontOriginSecret"
    priority = 1
    action {
      allow {}
    }
    statement {
      byte_match_statement {
        positional_constraint = "EXACTLY"
        search_string         = sha256("${data.aws_caller_identity.current.account_id}:${var.environment}:${aws_kms_key.application.key_id}")
        field_to_match {
          single_header { name = "x-origin-verify" }
        }
        text_transformation {
          priority = 0
          type     = "NONE"
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "cloudfront-origin"
      sampled_requests_enabled   = false
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name}-origin"
    sampled_requests_enabled   = false
  }
}

resource "aws_wafv2_web_acl_association" "origin" {
  resource_arn = aws_lb.web.arn
  web_acl_arn  = aws_wafv2_web_acl.origin.arn
}

resource "aws_cloudfront_distribution" "web" {
  enabled         = true
  is_ipv6_enabled = true
  aliases         = [var.public_app_domain]
  web_acl_id      = aws_wafv2_web_acl.edge.arn
  price_class     = "PriceClass_200"
  http_version    = "http2and3"

  origin {
    domain_name = aws_lb.web.dns_name
    origin_id   = "web-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-Origin-Verify"
      value = sha256("${data.aws_caller_identity.current.account_id}:${var.environment}:${aws_kms_key.application.key_id}")
    }
  }

  default_cache_behavior {
    target_origin_id         = "web-alb"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods           = ["GET", "HEAD"]
    compress                 = true
    cache_policy_id          = "413f1608-5154-4e1e-9c6e-1d7d6925f8fc"
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3"
  }

  restrictions {
    geo_restriction {
      restriction_type = "whitelist"
      locations        = ["IN"]
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.cloudfront_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  logging_config {
    bucket          = "${replace(var.log_archive_bucket_arn, "arn:aws:s3:::", "")}.s3.amazonaws.com"
    prefix          = "cloudfront/${var.environment}/"
    include_cookies = false
  }

  depends_on = [aws_lb_listener.https]
}

resource "aws_route53_record" "web" {
  zone_id = var.route53_zone_id
  name    = var.public_app_domain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.web.domain_name
    zone_id                = aws_cloudfront_distribution.web.hosted_zone_id
    evaluate_target_health = false
  }
}
