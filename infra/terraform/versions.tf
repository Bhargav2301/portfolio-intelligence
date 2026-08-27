terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    # Supply bucket, key, region, encrypt=true, and use_lockfile=true with -backend-config.
    # State buckets live in the security/log-archive account and are not created here.
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.tags
  }
}

provider "aws" {
  alias  = "backup"
  region = var.backup_region

  default_tags {
    tags = local.tags
  }
}

provider "aws" {
  alias  = "global"
  region = "us-east-1"

  default_tags {
    tags = local.tags
  }
}
