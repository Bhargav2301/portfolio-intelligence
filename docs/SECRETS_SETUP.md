# Secrets and API-key setup

This guide explains every credential represented by the current codebase. The application must never contain a real key in Git.

## 1. Create the local secrets file

From the repository root:

    python scripts/bootstrap_env.py

This reads .env.example, generates strong local database, object-storage, encryption, and session secrets, and writes a new .env file with restricted permissions where the operating system supports them.

If .env already exists, the script stops instead of overwriting it. To start again, rename the old file first so it remains recoverable.

## 2. Required now

### OpenAI API key

Purpose: live language-model responses in the LangGraph agent service.

Steps:

1. Sign in to the OpenAI API platform using the account that will own development billing.
2. Create a separate project named Portfolio Intelligence Development.
3. Add a low initial monthly budget and usage alerts.
4. Create a project-scoped secret API key.
5. Copy it once and paste it after OPENAI_API_KEY= in .env.
6. Do not use a personal all-project key.
7. Do not prefix it with quotes unless the value itself requires them.
8. Restart the agents container after changing it:

       docker compose restart agents

9. Open http://localhost:8001/health/ready. The response will state whether live AI is configured.

OPENAI_MODEL is intentionally blank in the repository. Set it to an approved model available to the project. Model selection must pass the QA evaluation before production use.

If no API key is set, the graph still runs in deterministic safe mode and explains that live model synthesis is disabled.

## 3. Generated local infrastructure secrets

The bootstrap script generates:

| Variable | Purpose |
|---|---|
| POSTGRES_PASSWORD | Local database administrator password |
| OBJECT_STORAGE_SECRET_KEY | Local MinIO password |
| SESSION_SECRET | Signs local browser/session state |
| FIELD_ENCRYPTION_KEY | Encrypts sensitive fields; base64-encoded 32-byte key |
| AGENT_CORE_SHARED_SECRET | Authenticates Agent service run-provenance writes to Core |

These values are suitable for one local developer. Production values must come from a managed secret store and use separate credentials per environment.

Do not reuse any generated value as a personal password.

### Core-to-Agent internal authentication

Variable:

- AGENT_CORE_SHARED_SECRET

The bootstrap script creates this value for local development. It must be identical in the Core API
and Agent API process environments. It is server-only and must never use a `NEXT_PUBLIC_` name.

For AWS staging or production:

1. Generate at least 48 random bytes with an approved password generator or secret-management
   workflow.
2. Open the Terraform-created Secrets Manager entry ending in `/agent-internal`.
3. Store one JSON value with this exact shape, substituting the generated value:

       {"shared_secret":"replace-with-generated-value"}

4. Do not place the value in Terraform variables, task-definition source, CI output, or logs.
5. Deploy Core and Agents together; Terraform injects the same `shared_secret` JSON field into both
   services.
6. Verify an Agent start/complete request succeeds and a missing or altered secret receives 401.
7. Rotate by creating a new secret version and rolling both services in the same maintenance window.

Staging and production services fail closed when this secret is absent. If final run persistence to
Core fails, the Agent service withholds the answer instead of returning unrecorded advice.

## 4. Required before a public production deployment

### OIDC authentication

Variables:

- OIDC_ISSUER_URL
- OIDC_OAUTH_BASE_URL
- OIDC_CLIENT_ID
- OIDC_CLIENT_SECRET
- OIDC_REDIRECT_URI

Purpose: real user sign-in, MFA/passkeys, and verified identity.

Steps:

1. Choose the organization’s identity provider.
2. Create separate applications for staging and production.
3. Enable authorization-code flow with PKCE.
4. Register the exact HTTPS callback URL.
5. Disable wildcard callbacks.
6. Enable MFA for privileged roles.
7. Store the client secret in the deployment secret manager.
8. Configure short sessions and server-side revocation.
9. Test login, logout, expiry, revocation, and cross-tenant access before public launch.

Production mode refuses to start if OIDC or the signed traffic gates are missing. The BFF now uses
opaque Redis sessions and Core revalidates membership on every request; production traffic remains
disabled until the staging identity report is signed.

### Production PostgreSQL

Variables:

- DATABASE_URL
- POSTGRES_CHECKPOINT_DSN
- RDS_IAM_AUTH=true

Use separate IAM-authenticated application, checkpoint, reporting, order, and migration users
through RDS Proxy. Runtime users are non-superuser, non-owner, and `NOBYPASSRLS`; every tenant table
forces RLS. Require TLS, backups, point-in-time recovery, and a measured restore.

DATABASE_URL belongs to the Core API. POSTGRES_CHECKPOINT_DSN belongs to the isolated LangGraph service. They may target the same cluster but should use separate schemas and least-privilege users.

### Production object storage

Variables:

- OBJECT_STORAGE_ENDPOINT
- OBJECT_STORAGE_REGION
- OBJECT_STORAGE_BUCKET
- OBJECT_STORAGE_ACCESS_KEY
- OBJECT_STORAGE_SECRET_KEY
- OBJECT_STORAGE_SECURE

Create a private bucket with:

- Public access disabled.
- Server-side encryption.
- Object versioning.
- Short-lived signed URLs.
- Separate quarantine, approved, rendered, and derived prefixes.
- Lifecycle deletion rules.
- An application identity limited to this bucket.

The local MinIO container has no KMS and therefore receives no server-side-encryption header; its
Docker volume is development-only. AWS development without a custom endpoint uses SSE-S3.
Staging/production configuration requires `OBJECT_STORAGE_KMS_KEY_ID` and fails closed without it.

### Malware scanning

Variables:

- MALWARE_SCAN_REQUIRED
- CLAMAV_HOST
- CLAMAV_PORT

Local development defaults to false so the base stack starts quickly. Production must set MALWARE_SCAN_REQUIRED=true and run:

    docker compose --profile security up --build

The API must fail closed when scanning is required but unavailable.

### Field encryption

Variable:

- FIELD_ENCRYPTION_KEY

Production must use envelope encryption backed by a managed key service. Do not place the root encryption key directly in a container environment for long-term production. Rotate using a versioned re-encryption process.

## 5. Optional integrations

### LangSmith

Variables:

- LANGSMITH_TRACING
- LANGSMITH_API_KEY
- LANGSMITH_PROJECT

Purpose: agent tracing and evaluation.

Before enabling:

1. Create a dedicated project.
2. Configure retention and access.
3. Ensure raw statements, account identifiers, secrets, and unnecessary chat content are not exported.
4. Use a restricted project key.
5. Set LANGSMITH_TRACING=true only after privacy review.

### Upstox read-only connection

Variables:

- UPSTOX_CLIENT_ID
- UPSTOX_CLIENT_SECRET
- UPSTOX_REDIRECT_URI

Purpose: optional read-only portfolio synchronization.

Steps:

1. Create an application in the Upstox developer console.
2. Register the exact server callback URL.
3. Request only the scopes needed to read profile, holdings, positions, and transactions.
4. Do not request order placement, order modification, or withdrawal scopes.
5. Store the secret only on the server.
6. Verify that no browser network response contains an access or refresh token.
7. Keep the connection feature disabled until the connector implementation and QA-BRK tests pass.

The current milestone prepares configuration only; the connector is not yet enabled.

### Market and news data

Variables:

- MARKET_DATA_BASE_URL
- MARKET_DATA_API_KEY
- NEWS_DATA_BASE_URL
- NEWS_DATA_API_KEY

No provider is hard-coded. Select a licensed provider during Phase 0 and confirm:

- Indian equity and benchmark coverage.
- NSE/BSE identifier mapping.
- Point-in-time historical availability.
- Publication and known-at timestamps.
- Redistribution rights.
- Rate limits and service levels.
- Corporate-action handling.

Do not enable historical agent evaluation with a source that cannot honor a historical cutoff.

## 6. Secret placement by environment

| Environment | Storage |
|---|---|
| Local | Untracked .env with restricted file permissions |
| CI | GitHub Actions environment/repository secrets |
| Staging | Managed cloud secret store, staging-only identities |
| Production | Managed secret store/KMS, short-lived workload identity |

Never copy production secrets to staging or local machines.

## 7. GitHub Actions secrets

The initial CI does not require runtime credentials. When deployment is added:

1. Open repository Settings.
2. Open Secrets and variables, then Actions.
3. Prefer environment-scoped secrets for staging and production.
4. Require approval for production environments.
5. Add only the deployment credentials used by that workflow.
6. Never echo secrets or enable shell tracing around them.

## 8. Rotation and incident response

Rotate immediately if a key appears in:

- Git history.
- An issue, pull request, screenshot, log, or chat.
- Browser developer tools when it should be server-only.
- A third-party system outside the approved processor list.

Response:

1. Revoke the exposed key at its provider.
2. Create a replacement.
3. Update the secret store.
4. Restart affected services.
5. verify the old key fails.
6. Review access and audit logs.
7. Remove the secret from current files and, where justified, rewrite Git history.
8. Record the incident without repeating the secret.

Deleting a leaked string from the latest commit does not make the old key safe.

## 9. Pre-flight checklist

- .env exists locally and git status does not show it.
- No placeholder beginning with REPLACE remains in required variables.
- OPENAI_API_KEY is project-scoped and budget-limited.
- No NEXT_PUBLIC variable contains a secret.
- Database URLs use the correct environment and TLS in production.
- Object storage is private.
- Production malware scanning is required.
- OIDC is configured before public access.
- AGENT_CORE_SHARED_SECRET is server-only, identical in Core and Agents, and stored in
  `agent-internal`.
- Upstox scopes are read-only.
- Agent and provider logs do not contain raw financial documents.
