# Super Portfolio Intelligence — Unified Architecture and Delivery Roadmap

Last updated: 27 August 2026

## Executive outcome

The Portfolio Intelligence repository remains the application shell and authoritative system of
record. TradingAgents commit `a33fd4c0f134485a43553a2c23a63cb14adbd88f` has been adapted as an
isolated research pattern inside the agent service. Its analyst, bull/bear, and risk-panel structure
is retained; its trader semantics are replaced by typed, non-executable proposals.

This implementation is a tested production-oriented vertical slice, not approval for public use or
real-money advice. OIDC/MFA, durable checkpoints, certified file reconciliation, licensed
point-in-time research, and the formal security/compliance gates remain launch blockers.

## Non-negotiable boundary

~~~mermaid
flowchart LR
    U[Next.js workspace] --> B[Server-side BFF]
    B --> C[Core FastAPI]
    C --> L[(Tenant-scoped append-only ledger)]
    C --> D[Deterministic analytics and monitors]
    B --> A[Agent FastAPI and LangGraph]
    A --> C
    A --> R[Bounded research panel]
    R --> P[Proposal only]
    P --> H[Human review]
    H -. action outside product .-> X[External broker]
~~~

There is no order endpoint, broker trading client, or execution tool. An agent cannot publish a
ledger event. A ledger event requires an authenticated Core API request and explicit
`confirm_publication: true`; uploaded files remain candidates until a reconciliation workflow
publishes them.

## Repository integration map

| Source | Role in the unified system | Integration decision |
|---|---|---|
| `portfolio-intelligence` at `1a431c7` | Next.js UI, Core API, storage, data model, deployment shell | Primary repository |
| `TradingAgents` at `a33fd4c` | Reference architecture for multi-role security research | Adapted, not imported as ledger/execution code |
| `services/api` | Tenant-scoped portfolio truth and deterministic calculations | Sole numeric authority |
| `services/agents` | Explanation, research perspectives, risk review, proposal composition | Read-only Core API consumer |
| `apps/web` | Human review workspace | Displays source quality, evidence, controls, and proposal-only status |

The exact adaptation boundary is recorded in
[`services/agents/UPSTREAM_INTEGRATION.md`](../services/agents/UPSTREAM_INTEGRATION.md).

## ReAct implementation record

### Phase 1 — Baseline and gap analysis

**Thought.** The shell already provided secure upload intake, tenant-scoped portfolio CRUD, an empty
analytics contract, and a basic bounded graph. The material gaps were an authoritative published
ledger path, real holdings/monitor calculations, evidence-bearing agent context, and the
TradingAgents research/risk structure.

**Action.** Pinned and inspected both repositories and reconciled them with the six approved
requirements documents. Defined the ledger/API boundary before changing agent behavior.

**Observation.** Directly importing the upstream trader and portfolio-manager flow would conflict
with PRD-FR-043 and TDD section 8.3. An adapter is safer and easier to audit than process-global
upstream configuration.

### Phase 2 — Ledger, analytics, and monitoring

**Thought.** AI answers cannot be trustworthy until holdings, cash, and rules come from deterministic
code. Decimal arithmetic, tenant filters, idempotent source references, and append-only publication
are required before agent integration.

**Action.** Added human-confirmed ledger publication/listing, deterministic roll-forward, holdings,
cash, average cost, realized/unrealized P/L, weights, protected cash, analytics, concentration
monitoring, and a compact agent-context endpoint.

**Observation.** API tests reproduce a ₹40 lakh portfolio with ₹25 lakh protected cash and a 37.5%
position. The monitor reports a concentration alert while reserve coverage remains intact. An
oversell, unconfirmed publication, duplicate source reference, and cross-tenant read fail closed.

### Phase 3 — TradingAgents adaptation

**Thought.** The useful upstream pattern is multi-perspective research, not its final trade decision.
Portfolio numbers must enter through the Core API, evidence gaps must stay visible, and output must
be structurally incapable of execution.

**Action.** Implemented request routing, four analyst slots, a one-round bull/bear comparison, an
aggressive/neutral/conservative risk panel, a deterministic scenario planner, a policy gate, and an
evidence-linked response composer. The proposal contract always includes `can_execute: false`.

**Observation.** Safe mode completes without an API key, keeps unavailable fundamentals/news/
sentiment unavailable, cites the ledger/monitor snapshots, suggests review rather than action, and
suppresses execution requests.

### Phase 4 — Unified workspace

**Thought.** Users need one view of authoritative numbers, active triggers, AI limitations, evidence,
and the human-control boundary.

**Action.** Connected the dashboard to analytics, holdings, and monitor endpoints; added security
focus selection; and rendered proposal status and evidence links in the chat result.

**Observation.** TypeScript validation and the optimized Next.js production build pass. Empty,
partial, trusted, alert, and proposal-only states remain explicit.

### Phase 5 — Verification

**Thought.** Financial integrity and excessive agency are higher-risk than cosmetic completeness.

**Action.** Added API and graph tests and ran Python compilation, unit/contract suites, repository
policy checks, TypeScript validation, and the production web build.

**Observation.** The implemented slice passes its automated checks. Historical returns, licensed
research, production identity, durable checkpoints, and full reconciliation are deliberately not
represented as complete.

## Implemented API surface

| Method and path | Purpose | Safety property |
|---|---|---|
| `POST /v1/portfolios/{id}/ledger/events` | Publish a confirmed manual ledger event | Explicit confirmation, tenant scope, unique source reference, invariant validation |
| `GET /v1/portfolios/{id}/ledger/events` | Read append-only event history | Tenant scope; no update/delete route |
| `GET /v1/portfolios/{id}/holdings` | Read deterministic holdings/cash snapshot | Decimal roll-forward; ledger version and limitations returned |
| `GET /v1/portfolios/{id}/analytics/latest` | Read current deterministic metrics | AI is not involved in calculation |
| `GET /v1/portfolios/{id}/monitors/latest` | Check reserve and concentration rules | Deterministic thresholds with evidence IDs |
| `GET /v1/portfolios/{id}/agent-context` | Supply minimum typed agent context | Tenant-scoped Core API boundary |
| `POST /v1/agent-runs` | Run portfolio/research review | Read-only, bounded rounds, evidence, proposal-only output |

## Target production topology

1. Serve Next.js behind a CDN/WAF. The BFF validates OIDC sessions and never accepts a browser-
   supplied tenant as authority.
2. Run Core API, ingestion workers, agent workers, and scheduler as private services with separate
   workload identities and egress policies.
3. Use multi-AZ PostgreSQL with a non-owner runtime role, forced RLS, point-in-time recovery, and
   separate schemas/roles for LangGraph checkpoints.
4. Use private object storage with quarantine, approved, rendered, and deleted prefixes; enable
   malware scanning and object lifecycle policies.
5. Use Redis only for ephemeral coordination. Durable jobs, outbox events, agent runs, evidence, and
   checkpoints remain in PostgreSQL.
6. Put model and research providers behind an allowlisted tool gateway that enforces tenant, as-of,
   known-at, timeout, row, token, cost, and retention policies.
7. Send OpenTelemetry traces and structured audit events to a restricted observability account. Do
   not log uploaded content, credentials, full portfolio payloads, or hidden model reasoning.
8. Deploy with signed images, SBOM/provenance, migration jobs, canary traffic, automatic rollback,
   tested backups, and agent/tool kill switches.

## Delivery roadmap and exit gates

### R1 — Reconciliation and immutable publication

- Persist extraction candidates, source-row lineage, mappings, confidence, and reconciliation cases.
- Add certified Upstox and two beta brokerage templates.
- Build approve/edit/reject UI and atomic batch publication with compensating reversals.
- Gate: golden ledgers pass 100%; no duplicate or cross-tenant publication.

### R2 — Historical analytics and scenarios

- Add instrument master, corporate actions, licensed prices, benchmark series, valuation snapshots,
  TWR/MWR, contribution, volatility, drawdown, overlap, and methodology versions.
- Add typed scenario API with costs, tax-excluded disclosure, and hard-constraint validation.
- Gate: deterministic finance golden/property suite and point-in-time reproducibility pass.

### R3 — Evidence-grade research and durable agents

- Add evidence records with provider, query, publication/retrieval time, cutoff, hash, and rights.
- Connect licensed point-in-time market/fundamental/news tools through immutable worker config.
- Move checkpoints and run/artifact records to PostgreSQL; add interrupts, cancellation, SSE, and
  user-visible tool/stage telemetry.
- Gate: 100% numeric-claim citation, zero historical cutoff violations, bounded completion at least
  99%.

### R4 — Production identity, privacy, and operations

- Add OIDC/MFA, server-side sessions, membership/role checks, consent, export/deletion, KMS-backed
  secrets, read-only broker OAuth, support-access workflow, and complete audit/outbox coverage.
- Gate: tenant-isolation fuzz/RLS suite, no order scopes/endpoints, restore drill, and privacy review.

### R5 — Beta hardening and release

- Run accessibility, browser, load/noisy-neighbor, chaos, penetration, AI red-team, compliance, and
  UAT programs from the approved QA plan.
- Deploy 1–5% canary with error, latency, cost, evidence, suppression, and feedback comparisons.
- Gate: every PRD launch gate passes; legal/compliance selects and approves the operating mode.

## Current known limitations

- Manual ledger publication is available; file-derived publication still needs the reconciliation
  workbench and certified templates.
- Latest transaction/price-mark values support the current snapshot; historical performance and
  licensed live prices are not implemented.
- Monitor coverage currently includes data presence, protected cash, and max position weight. Drift
  needs versioned target allocations.
- The research panel has provider slots but deliberately abstains when approved point-in-time
  evidence is absent.
- Development uses in-memory LangGraph checkpoints. Production mode remains fail-closed until
  durable checkpoints and verified identity propagation are enabled.
- The current local workspace header is development-only and must never be exposed as a production
  tenancy mechanism.
