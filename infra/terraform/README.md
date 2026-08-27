# Production infrastructure

This root provisions one isolated workload account in `ap-south-1`. Run it independently in
development, staging, and production accounts. The security/log-archive account owns the
Terraform state bucket, organization CloudTrail, Config aggregator, GuardDuty administrator,
Security Hub administrator, and cross-account audit destination.

## Fail-closed gates

All ECS desired counts default to zero. `enable_services`, `identity_gate_passed`,
`rls_gate_passed`, and `telemetry_gate_passed` must all be true before any application task can
receive traffic. Live orders additionally require the explicit order switch, legal approval, and
Upstox production approval. Terraform variable changes must be made by reviewed pull request.

Never put secrets in tfvars. CI passes the Redis bootstrap credential as a masked environment
variable and writes application values to pre-created Secrets Manager containers. Per-user broker
grants are written only by Core as KMS envelope-encrypted ciphertext.

## First deployment

1. Copy the environment and backend examples outside the repository and replace identifiers.
2. Assume the environment deployment role through GitHub OIDC.
3. Run `terraform init -backend-config=<environment>.hcl` and `terraform plan`.
4. Apply with all gates false, populate secrets, and run the one-off migration task.
5. Run identity, forced-RLS pooled-connection, and telemetry canary tests.
6. Attach the signed evidence records, set the three gate variables, and apply again.

The primary database and S3 buckets have deletion protection or `prevent_destroy`. Destroy is not
a supported rollback mechanism; application and schema releases use expand/migrate/contract.
