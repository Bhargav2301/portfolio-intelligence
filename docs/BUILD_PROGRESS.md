# Build progress

Last updated: 2 September 2026

This file is updated with the README as implementation changes.

## Current milestone: R2/R3 implementation checkpoint after the R0/R1 foundation

### Hosted Sites demo checkpoint

- Hosted Sites version 18 is active with owner-only access; the public repository contains a sanitized source snapshot at `apps/sites-demo/`.
- The responsive Sites UI includes collapsible navigation, portfolio setup, native CSV/TSV/XLS/XLSX/JSON selection, consolidated workbook flattening, PDF metadata plus SHA-256 registration, deterministic analytics, scenarios, evidence views, account-data deletion, and an in-session conversational copilot.
- The public normalizer uses runtime mappings or review-only derived symbols; customer-specific ticker aliases and private portfolio statistics are not compiled into the repository.
- Local validation passes the optimized Sites build, 9 JavaScript tests, ESLint, and 6 Python ingestion/policy/LangGraph tests.
- Durable server-side chat memory, raw private document storage, and Upstox OAuth remain activation or production-hardening work.
- No model, broker, or runtime secret is committed. Owner-only Sites version 18 was privately redeployed with protected environment revision 5, the approved billed `google/gemma-4-26b-a4b-it` chat route, and the authenticated external TradingAgents/LangGraph runtime. Render health and shared-token authentication probes passed.

### Validation baseline

- 29 locally runnable Core API tests cover goal math, file safety, certified
  reconciliation/publication, telemetry redaction, ledger invariants, point-in-time valuation,
  deterministic returns/risk, constrained scenarios, evidence, durable run records, and tenant
  isolation.
- 9 agent tests cover execution suppression, data-quality gating, hard rules, numeric citations,
  abstention, bounded research/risk roles, and `Literal[False]` proposal output.
- Six PostgreSQL 16 tests apply the real Alembic chain and prove forced RLS, transaction-local pool
  cleanup, non-bypass, tenant-aware composite foreign keys, and R2/R3 table isolation. They require
  a PostgreSQL test service and are skipped by the SQLite-only local command.
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
- Sealed market-data versions with price observations, supported splits/cash dividends, rights,
  checksums, economic dates, and information cutoffs.
- Immutable valuation snapshots and position rows linked to ledger, market-data, and methodology
  versions.
- Decimal TWR, XIRR/MWR, annualized volatility, downside deviation, drawdown, price coverage, and
  explicit unavailable/quality states.
- Persisted market-stress scenarios that enforce the protected reserve, reject equal-weight
  suggestions, exclude tax calculations, and always return `can_execute: false`.
- Point-in-time evidence records with typed numeric claims, source rights, hashes, structured
  locators, and snapshot/run lineage.
- Durable Core agent-run/stage/proposal records plus PostgreSQL LangGraph checkpoint configuration,
  tenant/portfolio/thread scope, output hashes, and terminal-persistence fail-closed behavior.
- Numeric-citation validation that withholds unsupported answers and completed runs below 100%
  numeric coverage.

### Partially implemented

- Asynchronous ingestion: durable job/outbox/SQS contracts and an isolated, gate-disabled ECS
  service are provisioned; the current completion endpoint still scans and parses in-process until
  the retry-safe worker cutover is qualified in staging.
- Storage interface: local and S3/MinIO quarantine adapters are active; approved/rendered publication lifecycle is pending.
- Malware scanning: ClamAV streaming and fail-closed production enforcement are implemented; the optional local scanner profile must be enabled explicitly.
- Agent persistence: PostgreSQL checkpoint initialization, durable Core run/stage records, and
  IAM-token startup are implemented; staging failover/long-running reconnection qualification is
  pending.
- Agent evidence: immutable evidence storage, cutoff validation, internal ledger/monitor/rule
  evidence, and numeric citations are active; licensed market/news provider workers are pending.
- Dashboard: current ledger metrics, holdings, monitors, upload, and bounded chat are active;
  citation display is active, while historical chart and scenario-comparison screens are pending.

### Not implemented yet

- Cloud-account deployment and Cognito/passkey staging qualification.
- Provider-specific parsing beyond the deliberately selected generic R1 CSV contract.
- Licensed historical price/news ingestion workers, benchmark/active return, contribution and
  attribution, advanced corporate actions, and market-state classification.
- Licensed point-in-time research connectors for the adapted TradingAgents subgraph.
- Scenario comparison UI and cost-model qualification.
- User decisions, feedback, outcome evaluation, and offline self-correction.
- Read-only Upstox connector.
- Production deployment, penetration test, accessibility audit, and regulatory launch approval.

## Next implementation sequence

1. Provision the staging account with all service counts gated to zero.
2. Populate managed secrets and run the Cognito, RLS, telemetry, and restore exit gates.
3. Run certified CSV concurrency/fuzz/malware qualification and sign the R1 report.
4. Run the R2 golden/property/reproducibility suite against PostgreSQL and licensed historical data;
   add benchmark/active return, attribution, and the approved corporate-action subset.
5. Connect licensed evidence workers and complete R3 cutoff, citation, failover, bounded-completion,
   abstention, canary, and kill-switch qualification.
6. Complete privacy/suitability controls and implement the isolated human order gateway only after
   R4 approvals.

## Release statement

The R2/R3 checkpoint is suitable for local engineering and synthetic-data testing only. It is not
an exit-gate pass and is not approved for real portfolio advice or public production traffic.
