locals {
  name             = "spi-${var.environment}"
  azs              = slice(data.aws_availability_zones.available.names, 0, 3)
  bootstrap_digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

  production_gate_open = (
    var.enable_services &&
    var.identity_gate_passed &&
    var.rls_gate_passed &&
    var.telemetry_gate_passed
  )

  live_order_gate_open = (
    local.production_gate_open &&
    var.enable_live_orders &&
    var.legal_approval_recorded &&
    var.upstox_live_approval_recorded
  )

  tags = {
    Application = "super-portfolio-intelligence"
    Environment = var.environment
    ManagedBy   = "terraform"
    DataClass   = "confidential-financial"
  }

  services = {
    web = {
      port          = 3000
      desired_count = local.production_gate_open ? 2 : 0
      public        = true
    }
    api = {
      port          = 8000
      desired_count = local.production_gate_open ? 2 : 0
      public        = false
    }
    agents = {
      port          = 8001
      desired_count = local.production_gate_open && var.agent_evaluation_gate_passed && var.research_provider_approved ? 1 : 0
      public        = false
    }
    ingestion = {
      port          = 8080
      desired_count = local.production_gate_open && var.ingestion_gate_passed ? 1 : 0
      public        = false
    }
    order_gateway = {
      port          = 8010
      desired_count = local.live_order_gate_open ? 2 : 0
      public        = false
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}
