# Build progress

Last updated: 27 August 2026

This file is updated with the README as implementation changes.

## Current milestone: R0/R1 production foundation and immutable reconciliation

### Validation baseline

- 24 Core API tests cover goal math, file safety, certified reconciliation/publication, telemetry
  redaction, ledger invariants, deterministic holdings/analytics/monitors, and tenant isolation.
- 7 agent tests cover execution suppression, data-quality gating, hard rules, evidence links,
  bounded research/risk roles, and `Literal[False]` proposal output.
- Four PostgreSQL 16 tests apply the real Alembic baseline and prove forced RLS, transaction-local
  pool cleanup, non-bypass, and tenant-aware composite foreign keys.
- CI compiles both Python services, builds the optimized web application, and scans the tree for execution capabilities and committed secrets.
- The stack smoke gate builds every application container and exercises the browser proxy, PostgreSQL, MinIO quarantine, file upload, and bounded agent response.

### Implemented

- Clean monorepo layout.
- Next.js portfolio workspace.
- FastAPI Core API service.
- FastAPI/LangGraph agent service.
- PostgreSQL, Redis, MinIO, and optional ClamAV Docker stack.
- Tenant-scoped portfolio create/list/read API.
- Safe file intake for PDF, XLS, XLSX, and CSV.
- File-signature and spreadsheet-active-content checks.
- Native versus scanned PDF structural detection.
- Deterministic required-CAGR calculation.
- Empty-portfolio analytics contract.
- Bounded agent state, data gate, diagnostics, scenario, policy, and response nodes.
- Development safe mode when no AI key is present.
- Initial database schema and row-level-security policies.
- Human-confirmed append-only manual ledger events with duplicate and oversell protection.
- Deterministic cash, holdings, average cost, realized/unrealized P/L, and position weights.
- Protected-reserve and concentration monitoring with evidence identifiers.
- Tenant-scoped agent context assembled only from Core API ledger and monitor data.
- TradingAgents-derived analyst, bull/bear, and risk-panel architecture with one-round caps.
- Typed rebalance-review/no-action proposals with execution structurally disabled.
- Live dashboard holdings, monitoring alerts, proposal status, and evidence links.
- Secret generation, setup guide, CI, and repository-policy checks.
- Six requirements documents included without modification.
- Cognito authorization-code/PKCE BFF with opaque Redis sessions, origin/CSRF enforcement, token
  revocation, strict header rebuilding, membership authorization, and recent-MFA owner checks.
- Alembic forward-only baseline, separate migration/runtime/checkpoint roles, forced RLS, composite
  tenant keys, immutable-table triggers, durable jobs/idempotency/outbox/audit foundations.
- Certified `spi-ledger-csv/v1` parser, quarantine presign/checksum path, extracted-row lineage,
  reconciliation cases, optimistic edits, exact selection validation, and atomic publication.
- Reconciliation workbench with upload progress, row decisions, exceptions, acknowledgment, MFA
  refresh, and immutable publication receipts.
- AWS ECS/RDS/Redis/S3/SQS/Cognito/KMS/CloudFront/WAF Terraform with hard traffic and order gates.
- Signed-digest CI/CD with SBOM, image scan, migrations, 5%/15-minute canary, and alarm rollback.

### Partially implemented

- Asynchronous ingestion: durable job/outbox/SQS contracts and an isolated, gate-disabled ECS
  service are provisioned; the current completion endpoint still scans and parses in-process until
  the retry-safe worker cutover is qualified in staging.
- Storage interface: local and S3/MinIO quarantine adapters are active; approved/rendered publication lifecycle is pending.
- Malware scanning: ClamAV streaming and fail-closed production enforcement are implemented; the optional local scanner profile must be enabled explicitly.
- Agent persistence: PostgreSQL checkpoint initialization and IAM-token startup are implemented;
  staging failover/long-running reconnection qualification is pending.
- Agent evidence: ledger and monitor evidence is active; licensed market/news providers are pending.
- Dashboard: current ledger metrics, holdings, monitors, upload, and bounded chat are active;
  historical performance charts await valuation history.

### Not implemented yet

- Cloud-account deployment and Cognito/passkey staging qualification.
- Provider-specific parsing beyond the deliberately selected generic R1 CSV contract.
- Historical price, benchmark, contribution, risk, and market-state calculations.
- Evidence repository and point-in-time market/news tools.
- Licensed point-in-time research connectors for the adapted TradingAgents subgraph.
- Scenario persistence and comparison.
- User decisions, feedback, outcome evaluation, and offline self-correction.
- Read-only Upstox connector.
- Production deployment, penetration test, accessibility audit, and regulatory launch approval.

## Next implementation sequence

1. Provision the staging account with all service counts gated to zero.
2. Populate managed secrets and run the Cognito, RLS, telemetry, and restore exit gates.
3. Run certified CSV concurrency/fuzz/malware qualification and sign the R1 report.
4. Add historical valuation snapshots and deterministic return/risk analytics (R2).
5. Add licensed evidence tools and complete durable agent-run qualification (R3).
6. Implement and certify the isolated human order gateway only after R4 approvals.

## Release statement

The current milestone is suitable for local engineering and synthetic-data testing only. It is not approved for real portfolio advice or public production traffic.
