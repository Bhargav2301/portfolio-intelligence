data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "edge_alb" {
  name        = "${local.name}-edge-alb"
  description = "CloudFront origin ingress only"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "web" {
  name        = "${local.name}-web"
  description = "Next.js BFF"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "api" {
  name        = "${local.name}-api"
  description = "Core API"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "agents" {
  name        = "${local.name}-agents"
  description = "Proposal-only agents with no order-gateway route"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "ingestion" {
  name        = "${local.name}-ingestion"
  description = "Asynchronous ingestion workers"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "order_gateway" {
  name        = "${local.name}-order-gateway"
  description = "Human-authorized order gateway"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "rds_proxy" {
  name        = "${local.name}-rds-proxy"
  description = "RDS Proxy"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "database" {
  name        = "${local.name}-database"
  description = "PostgreSQL cluster"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "redis" {
  name        = "${local.name}-redis"
  description = "TLS Redis sessions and coordination"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "endpoints" {
  name        = "${local.name}-endpoints"
  description = "Private AWS API endpoints"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "edge_https" {
  security_group_id = aws_security_group.edge_alb.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "edge_to_web" {
  security_group_id            = aws_security_group.edge_alb.id
  referenced_security_group_id = aws_security_group.web.id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 3000
}

resource "aws_vpc_security_group_ingress_rule" "web_from_edge" {
  security_group_id            = aws_security_group.web.id
  referenced_security_group_id = aws_security_group.edge_alb.id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 3000
}

resource "aws_vpc_security_group_egress_rule" "web_to_api" {
  security_group_id            = aws_security_group.web.id
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_egress_rule" "web_to_agents" {
  security_group_id            = aws_security_group.web.id
  referenced_security_group_id = aws_security_group.agents.id
  ip_protocol                  = "tcp"
  from_port                    = 8001
  to_port                      = 8001
}

resource "aws_vpc_security_group_egress_rule" "web_to_redis" {
  security_group_id            = aws_security_group.web.id
  referenced_security_group_id = aws_security_group.redis.id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_egress_rule" "web_https" {
  security_group_id = aws_security_group.web.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_ingress_rule" "api_from_web" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.web.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_ingress_rule" "api_from_agents" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.agents.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_egress_rule" "api_to_database" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.rds_proxy.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "api_to_redis" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.redis.id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_egress_rule" "api_to_order_gateway" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.order_gateway.id
  ip_protocol                  = "tcp"
  from_port                    = 8010
  to_port                      = 8010
}

resource "aws_vpc_security_group_egress_rule" "api_https" {
  security_group_id = aws_security_group.api.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_ingress_rule" "agents_from_web" {
  security_group_id            = aws_security_group.agents.id
  referenced_security_group_id = aws_security_group.web.id
  ip_protocol                  = "tcp"
  from_port                    = 8001
  to_port                      = 8001
}

resource "aws_vpc_security_group_egress_rule" "agents_to_api" {
  security_group_id            = aws_security_group.agents.id
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_egress_rule" "agents_to_database" {
  security_group_id            = aws_security_group.agents.id
  referenced_security_group_id = aws_security_group.rds_proxy.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "agents_https" {
  security_group_id = aws_security_group.agents.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "ingestion_to_database" {
  security_group_id            = aws_security_group.ingestion.id
  referenced_security_group_id = aws_security_group.rds_proxy.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "ingestion_https" {
  security_group_id = aws_security_group.ingestion.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_ingress_rule" "order_from_api" {
  security_group_id            = aws_security_group.order_gateway.id
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = 8010
  to_port                      = 8010
}

resource "aws_vpc_security_group_egress_rule" "order_to_database" {
  security_group_id            = aws_security_group.order_gateway.id
  referenced_security_group_id = aws_security_group.rds_proxy.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "order_https" {
  security_group_id = aws_security_group.order_gateway.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

locals {
  database_clients = {
    api           = aws_security_group.api.id
    agents        = aws_security_group.agents.id
    ingestion     = aws_security_group.ingestion.id
    order_gateway = aws_security_group.order_gateway.id
  }

  redis_clients = {
    web = aws_security_group.web.id
    api = aws_security_group.api.id
  }
}

resource "aws_vpc_security_group_ingress_rule" "proxy_from_clients" {
  for_each = local.database_clients

  security_group_id            = aws_security_group.rds_proxy.id
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "proxy_to_database" {
  security_group_id            = aws_security_group.rds_proxy.id
  referenced_security_group_id = aws_security_group.database.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_ingress_rule" "database_from_proxy" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.rds_proxy.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_clients" {
  for_each = local.redis_clients

  security_group_id            = aws_security_group.redis.id
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_https" {
  security_group_id = aws_security_group.endpoints.id
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
