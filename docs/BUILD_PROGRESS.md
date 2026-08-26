# Build progress

Last updated: 26 August 2026

This file is updated with the README as implementation changes.

## Current milestone: clean foundation and first vertical slice

### Validation baseline

- 13 Core API tests cover goal math, file safety, duplicate quarantine, and tenant isolation.
- 5 agent tests cover execution suppression, data-quality gating, hard rules, and the complete safe-mode graph.
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
- Secret generation, setup guide, CI, and repository-policy checks.
- Six requirements documents included without modification.

### Partially implemented

- Storage interface: local and S3/MinIO quarantine adapters are active; approved/rendered publication lifecycle is pending.
- Malware scanning: ClamAV streaming and fail-closed production enforcement are implemented; the optional local scanner profile must be enabled explicitly.
- Agent persistence: configuration prepared; production PostgreSQL checkpoint initialization is pending.
- Agent evidence: response contract supports evidence; provider tools are pending.
- Dashboard: live portfolio/upload/chat actions are included; full charts depend on ledger analytics.

### Not implemented yet

- Production OIDC/MFA.
- Provider-specific parsing templates.
- Human reconciliation workbench and publication.
- Append-only transactions and cash-event APIs.
- Holdings, price, benchmark, contribution, risk, and market-state calculations.
- Evidence repository and point-in-time market/news tools.
- Full TradingAgents-derived asset-research debate.
- Scenario persistence and comparison.
- User decisions, feedback, outcome evaluation, and offline self-correction.
- Read-only Upstox connector.
- Production deployment, penetration test, accessibility audit, and regulatory launch approval.

## Next implementation sequence

1. Finish PostgreSQL migration runner and non-superuser runtime role.
2. Build extraction candidate and reconciliation-case persistence.
3. Add certified brokerage XLS/XLSX templates.
4. Publish approved transactions into an append-only ledger.
5. Implement holdings/cash snapshot and invariant tests.
6. Connect the web reconciliation workbench.
7. Add deterministic return/risk analytics.
8. Add evidence tools and the bounded asset-research subgraph.

## Release statement

The current milestone is suitable for local engineering and synthetic-data testing only. It is not approved for real portfolio advice or public production traffic.
