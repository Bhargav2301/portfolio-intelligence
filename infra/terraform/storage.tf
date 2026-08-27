locals {
  bucket_purposes = toset(["quarantine", "documents", "artifacts"])
}

resource "aws_s3_bucket" "private" {
  for_each = local.bucket_purposes

  bucket        = "${local.name}-${each.key}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "private" {
  for_each = aws_s3_bucket.private

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "private" {
  for_each = aws_s3_bucket.private

  bucket = each.value.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "private" {
  for_each = aws_s3_bucket.private

  bucket = each.value.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.documents.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "private" {
  for_each = aws_s3_bucket.private

  bucket = each.value.id

  rule {
    id     = "retention"
    status = "Enabled"

    filter {}

    dynamic "expiration" {
      for_each = each.key == "quarantine" ? [1] : []
      content { days = 7 }
    }

    noncurrent_version_expiration {
      noncurrent_days = each.key == "quarantine" ? 7 : 90
    }

    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}

resource "aws_s3_bucket_policy" "private" {
  for_each = aws_s3_bucket.private

  bucket = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [each.value.arn, "${each.value.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        Sid       = "DenyUnencryptedObjects"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${each.value.arn}/*"
        Condition = {
          StringNotEquals = { "s3:x-amz-server-side-encryption" = "aws:kms" }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_cors_configuration" "quarantine" {
  bucket = aws_s3_bucket.private["quarantine"].id

  cors_rule {
    allowed_headers = ["content-type", "x-amz-*", "x-amz-meta-*"]
    allowed_methods = ["POST", "PUT"]
    allowed_origins = ["https://${var.public_app_domain}"]
    expose_headers  = ["ETag"]
    max_age_seconds = 600
  }
}

resource "aws_s3_bucket" "audit" {
  bucket              = "${local.name}-immutable-audit-${data.aws_caller_identity.current.account_id}"
  object_lock_enabled = true
  force_destroy       = false
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.observability.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    default_retention {
      mode  = "COMPLIANCE"
      years = 7
    }
  }
}

resource "aws_s3_bucket_policy" "audit" {
  bucket = aws_s3_bucket.audit.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.audit.arn, "${aws_s3_bucket.audit.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}
