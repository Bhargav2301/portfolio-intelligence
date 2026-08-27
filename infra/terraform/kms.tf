resource "aws_kms_key" "application" {
  description             = "${local.name} application envelope encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "documents" {
  description             = "${local.name} document and derived-object encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "secrets" {
  description             = "${local.name} Secrets Manager encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "observability" {
  description             = "${local.name} audit and observability encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "capabilities" {
  description              = "${local.name} asymmetric capability-token signing"
  customer_master_key_spec = "RSA_3072"
  key_usage                = "SIGN_VERIFY"
  deletion_window_in_days  = 30
}

resource "aws_kms_alias" "keys" {
  for_each = {
    application   = aws_kms_key.application.key_id
    documents     = aws_kms_key.documents.key_id
    secrets       = aws_kms_key.secrets.key_id
    observability = aws_kms_key.observability.key_id
    capabilities  = aws_kms_key.capabilities.key_id
  }

  name          = "alias/${local.name}-${each.key}"
  target_key_id = each.value
}
