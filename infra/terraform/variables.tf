variable "environment" {
  description = "One of development, staging, or production."
  type        = string

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

variable "aws_region" {
  type    = string
  default = "ap-south-1"

  validation {
    condition     = var.aws_region == "ap-south-1"
    error_message = "The approved primary region is ap-south-1."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "public_app_domain" {
  type        = string
  description = "Public application hostname, for example staging.portfolio.example.com."
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN in ap-south-1 for the public ALB."
}

variable "cloudfront_certificate_arn" {
  type        = string
  description = "ACM certificate ARN in us-east-1 for CloudFront."
}

variable "route53_zone_id" {
  type        = string
  description = "Public Route53 hosted-zone ID."
}

variable "github_repository" {
  type        = string
  description = "GitHub owner/repository permitted to assume the deployment role."
}

variable "github_oidc_provider_arn" {
  type        = string
  description = "GitHub Actions OIDC provider provisioned in the workload account."
}

variable "image_digests" {
  description = "Promoted image digests keyed by web, api, agents, ingestion, scanner, scheduler, and order_gateway."
  type        = map(string)
  default     = {}
}

variable "redis_auth_token" {
  description = "Rotated Redis ACL/auth token supplied from the environment secret pipeline."
  type        = string
  sensitive   = true
}

variable "allowed_operator_cidrs" {
  description = "Corporate/break-glass egress CIDRs allowed by WAF in addition to normal application traffic."
  type        = list(string)
  default     = []
}

variable "backup_region" {
  type    = string
  default = "ap-south-2"
}

variable "enable_services" {
  description = "Services remain disabled until identity/RLS/telemetry staging gates are signed."
  type        = bool
  default     = false
}

variable "identity_gate_passed" {
  type    = bool
  default = false
}

variable "rls_gate_passed" {
  type    = bool
  default = false
}

variable "telemetry_gate_passed" {
  type    = bool
  default = false
}

variable "agent_evaluation_gate_passed" {
  type    = bool
  default = false
}

variable "ingestion_gate_passed" {
  type    = bool
  default = false
}

variable "research_provider_approved" {
  type    = bool
  default = false
}

variable "approved_openai_model" {
  type        = string
  description = "Procurement-approved OpenAI model identifier for this environment."
  default     = ""
}

variable "enable_live_orders" {
  description = "Global live-order kill switch. Must remain false through R4 sandbox qualification."
  type        = bool
  default     = false
}

variable "legal_approval_recorded" {
  type    = bool
  default = false
}

variable "upstox_live_approval_recorded" {
  type    = bool
  default = false
}

variable "log_archive_bucket_arn" {
  type        = string
  description = "Organization log-archive bucket ARN in the security account."
}

variable "terraform_state_bucket_arn" {
  type        = string
  description = "Cross-account encrypted Terraform state bucket ARN."
}
