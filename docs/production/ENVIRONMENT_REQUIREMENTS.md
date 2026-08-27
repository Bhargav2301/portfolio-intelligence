# Environment requirements

## Secrets and credentials

Populate the Terraform-created, environment-specific Secrets Manager entries through the approved
GitHub environment. Never place values in tfvars, task definitions, browser variables, or logs.

- `openai`: `api_key`; use separate OpenAI projects, approved model, budget, and rotation.
- `upstox-application`: client ID/secret and exact redirect URI; production remains unavailable
  until R4 approval. Per-user grants are Core-written KMS envelope ciphertext.
- `market-data` and `news-data`: licensed provider credentials; absent credentials require agent
  abstention.
- `cognito-bff`: client secret, created from the confidential user-pool client.
- `server-session`: at least 32 random bytes in `session_secret`.
- `redis`: TLS URL with the rotated authentication token.
- `malware-scanner`, `alerting`, and webhook-verification values where applicable.

RDS application tasks use IAM tokens through RDS Proxy. No static application database password is
permitted. Only the RDS-managed bootstrap administrator secret exists; the normal migration task
uses the `spi_migration` IAM database user.

## Security and identity

- Accounts: security/log archive, development, staging, production.
- Organization: Control Tower, organization CloudTrail, Config, GuardDuty, Security Hub, and SCPs.
- Cognito: Essentials/Plus, admin invitations only, verified email, required user verification for
  passkeys, or password plus TOTP, 15-minute access/ID tokens, revocation enabled.
- Edge: ACM in `ap-south-1` and `us-east-1`, Route53, CloudFront, managed WAF rule groups, regional
  origin-secret WAF, HSTS/CSP headers, and rate limits.
- GitHub: environment protection plus OIDC role. Repository access keys are forbidden.
- KMS: separate application, document, secret, observability, backup, and asymmetric capability
  keys with exact task-role grants.

## Data and storage

- PostgreSQL 16 Multi-AZ DB cluster: writer plus two readable standbys, 100 GiB encrypted storage,
  RDS Proxy, TLS/IAM auth, 35-day PITR, Performance Insights, deletion protection, and hourly AWS
  Backup copy to `ap-south-2`.
- Redis: TLS, authentication, encryption, Multi-AZ primary/replica; sessions/locks/rate limits only.
- S3: separate quarantine, approved documents, artifacts, and seven-year Object Lock audit buckets;
  Block Public Access, versioning, checksums, SSE-KMS, TLS-only policy, and lifecycle rules.
- SQS: jobs/audit queues, long polling, KMS, five-attempt DLQs, age/depth alarms. PostgreSQL remains
  authoritative for job, idempotency, checkpoint, and outbox state.

## Compute and delivery

- Private ECS Fargate services and roles for web, Core, agents, ingestion, scanner sidecar,
  migrations, scheduler, and the disabled order gateway.
- Only CloudFront/WAF and the web ALB are public. Agents have no order-port route and explicit IAM
  denies for broker material and service discovery.
- Immutable ECR SHA digests, BuildKit provenance/SBOM, Trivy gate, keyless Cosign signature, one-off
  migration task, and CodeDeploy 5% canary with 15-minute bake and alarm rollback.
- ADOT sidecars export metadata-only traces/metrics/logs. CloudWatch alarms cover application
  errors, queue age, and DLQs.
