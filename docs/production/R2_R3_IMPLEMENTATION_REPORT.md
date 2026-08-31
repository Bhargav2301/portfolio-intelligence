# R2/R3 implementation checkpoint

R1 code completion does not imply that R2/R3 are production-approved; this checkpoint adds the
technical vertical slice while preserving every external exit gate.

Date: 27 August 2026
Branch: `codex/r2-r3-evidence-analytics`
TradingAgents reference: `TauricResearch/TradingAgents@a33fd4c0f134485a43553a2c23a63cb14adbd88f`

## Outcome

[Certain] The repository now contains an additive R2/R3 implementation for:

- immutable, versioned, tenant-scoped price and corporate-action datasets;
- point-in-time valuation snapshots tied to ledger, dataset, and methodology versions;
- deterministic TWR, MWR/XIRR, volatility, downside-deviation, and drawdown calculations;
- non-executable market-stress and hypothetical-cash-allocation scenarios;
- tenant-scoped evidence records with rights, publication/retrieval/known-at times, hashes,
  typed claims, and cutoff eligibility;
- durable Core agent-run metadata plus PostgreSQL LangGraph checkpoints in staging/production;
- structured numeric citations and independent Agent/Core gates that suppress or reject answers
  below full coverage;
- agent-service authentication for run lifecycle writes; and
- web display of versioned risk metrics, run identity, evidence, and numeric citations.

[Certain] No ledger-write or broker capability was added to the agent service. Scenario and agent
records have database and type-level `can_execute = false` invariants.

## Architecture

~~~mermaid
flowchart TD
    H["Human review"] --> C["Core API"]
    C --> L["Append-only ledger"]
    C --> A["Versioned analytics"]
    C --> E["Evidence store"]
    G["Bounded agent graph"] --> C
    G --> P["LangGraph checkpoints"]
    A --> G
    E --> G
~~~

Portfolio Intelligence remains the system of record. The adapted TradingAgents graph is a
read-only consumer of Core context and a writer only of proposal/run records through authenticated
Core endpoints. The checkpoint role can access only the `langgraph` schema.

## Reason–Act–Observation record

### Phase 1 — Reconcile the R1 checkpoint

**Thought.** The live repository already had stronger R0/R1 controls than the earlier planning
snapshot, including forced RLS, composite foreign keys, durable production checkpoints, and atomic
publication. Replacing those controls would create regression risk.

**Action.** Extended the existing schema, tenant session, idempotency, audit, and policy patterns.
Kept the ledger unchanged as the sole authority for positions and cash.

**Observation.** Existing API and agent suites continue to pass. R1 behavior and routes remain
backward compatible.

### Phase 2 — Deterministic valuation and risk

**Thought.** Transaction prices are not a reproducible historical market-price source. R2 requires
economic time (`as_of`) and information time (`known_at`) to be separate.

**Action.** Added sealed market-data manifests, prices, corporate actions, valuation positions,
analytics snapshots, metric values, and scenario records. Every result stores canonical input hash,
ledger version, dataset version, methodology version, quality, and limitations.

**Observation.** A future-known price is excluded from a historical valuation. Missing, stale,
currency-mismatched, or unsupported inputs lower quality instead of being guessed.

### Phase 3 — Evidence-linked durable agents

**Thought.** Durable LangGraph checkpoints alone do not provide application-level provenance.
Runs also need tenant/portfolio/thread identity, public stages, tool allowlist, policy, evidence, and
output hashes.

**Action.** Added durable Core run/step/evidence records, an authenticated start/complete lifecycle,
tenant/portfolio-scoped checkpoint keys, typed citations, and numeric coverage validation. Core
rebuilds the cutoff-safe claim set, validates each claim/value/unit/date/locator, recomputes coverage
from the public answer, verifies its hash, then stores only the hash and canonical citations. The
TradingAgents analyst, bull/bear, and risk-panel shape remains bounded to one round each.

**Observation.** Uncited numeric output is replaced by an abstention. Completion is rejected if a
registered citation value differs from its evidence claim or if the evidence was unknown at the
run cutoff.

## Data and integrity model

| Record | Authority | Mutation rule | Reproducibility key |
|---|---|---|---|
| Ledger transaction | Portfolio truth | Append-only; correction event | tenant, portfolio, ledger version |
| Market-data set | Valuation input | Sealed and append-only | provider version, cutoff, hash |
| Price/action row | Market input | Append-only | dataset, instrument, time, source hash |
| Analytics snapshot | Derived truth | Append-only | ledger + dataset + method + cutoff hash |
| Metric/position | Derived detail | Append-only | analytics snapshot |
| Scenario | Hypothesis | Append-only, never executable | base snapshot + assumptions + engine |
| Evidence item | Research/metric support | Human-approved and append-only | content hash + known-at + rights |
| Agent run | Explainable workflow | Controlled running → terminal transition | graph, prompt, model, policy, cutoff |
| Agent step/link | Public provenance | Append-only | run + stage/evidence claim |

Every new domain table has forced RLS and a `tenant_id`. Composite tenant-aware foreign keys reject
cross-workspace parent identifiers even when an application query is wrong.

## Deterministic finance methods

### Valuation

1. Select ledger events where both `trade_date <= as_of` and `recorded_at <= known_at`.
2. Interleave supported split and cash-dividend actions by effective time.
3. Select the latest price per instrument where `observed_at <= as_of` and the price's
   `known_at <= information_cutoff`.
4. Reject currency mismatches and non-positive values; flag missing/stale data.
5. Persist positions, cash, total value, coverage, lineage, and limitations.

Supported corporate actions in this checkpoint are splits and cash dividends. Rights issues,
spin-offs, mergers, and tax-lot adjustments remain blocked, not approximated.

### Returns and risk

Subperiod return uses the documented end-of-period external-flow convention:

$$r_t = \frac{V_t - F_t}{V_{t-1}} - 1$$

TWR is chain-linked as $\prod_t(1+r_t)-1$. MWR uses actual/365.25 XIRR over external flows plus
terminal value. Volatility and downside deviation use trusted periodic returns and 252-period
annualization. Drawdown uses the chain-linked wealth index. Insufficient history returns an
`insufficient_data` metric rather than zero.

Detailed tax calculations, benchmark/active return, beta, tracking error, attribution, and market
regime features are not claimed complete in this checkpoint.

## End-to-end workflows

### Valuation workflow

1. A human publishes reconciled ledger data.
2. An authorized owner seals a licensed/internal/user-provided market-data version.
3. The deterministic engine freezes `as_of` and `known_at`.
4. The engine values the immutable ledger and persists a snapshot.
5. The engine creates a verified analytics evidence item for available metrics.
6. The UI reads the latest stored snapshot; it never asks an LLM to calculate a number.

### Scenario workflow

1. A human chooses a trusted base snapshot and typed shocks/allocations.
2. The engine checks protected cash, equal-weight policy, price availability, and concentration.
3. Baseline and stressed values are persisted with tax-excluded disclosure.
4. A blocked scenario remains visible for explanation but has no execution path.

### Agent workflow

~~~mermaid
sequenceDiagram
    participant U as Human
    participant G as Agent API
    participant C as Core API
    participant P as Checkpoint DB
    U->>G: Question, portfolio, cutoff
    G->>C: Start durable run
    G->>C: Fetch cutoff-safe context
    G->>P: Run bounded graph
    G->>G: Validate policy and citations
    G->>C: Persist terminal run and proposal
    G-->>U: Answer, evidence, citations
~~~

If Core cannot persist the terminal record, the Agent API withholds the answer. If a numeric claim
cannot resolve to evidence, the graph suppresses the proposal and abstains.

## Human intervention versus autonomy

| Decision | Human responsibility | Autonomous software limit |
|---|---|---|
| Publish ledger | Reviews and explicitly approves | Parses/reconciles; cannot self-publish |
| Accept evidence/data rights | Owner approval or approved provider process | Validates schema, cutoff, hash, rights |
| Calculate valuations | Reviews methodology/quality | Deterministic code only; no LLM arithmetic |
| Run a scenario | Supplies typed assumptions | Enforces hard constraints; cannot change rules |
| Ask for research | Selects portfolio/security and cutoff | Bounded analysts synthesize allowlisted evidence |
| Act on proposal | Decides outside the product | `can_execute` is always false |
| Improve AI | Governance approves a release | No online self-training or silent prompt changes |

## API surface added

| Method and path | Purpose |
|---|---|
| `POST /v1/portfolios/{id}/market-data/datasets` | Seal tenant-scoped versioned prices/actions |
| `POST /v1/portfolios/{id}/analytics/recompute` | Persist reproducible valuation/risk snapshot |
| `GET /v1/analytics/{id}/metrics` | Read snapshot, positions, metrics, and lineage |
| `POST /v1/portfolios/{id}/scenarios` | Persist constrained non-executable stress scenario |
| `GET /v1/scenarios/{id}` | Read scenario assumptions/results |
| `POST /v1/portfolios/{id}/evidence` | Human-accept typed point-in-time evidence |
| `GET /v1/evidence/{id}` | Read authorized evidence metadata and claims |
| `POST /v1/portfolios/{id}/agent-runs` | Agent-service-only durable run start |
| `POST /v1/agent-runs/{id}/complete` | Validate and persist terminal run/proposal |
| `GET /v1/agent-runs/{id}` | Read tenant-authorized public run provenance |

All mutating user routes use the existing identity, membership, RLS, audit, and idempotency
controls. Agent lifecycle writes additionally require `AGENT_CORE_SHARED_SECRET` in staging and
production.

## Verification checkpoint

| Gate | Current evidence | Status |
|---|---|---|
| Existing R1 regression | 29 locally runnable Core tests and 9 Agent tests | Pass |
| Finance golden cases | Split, dividend, cutoff, transfer flow, TWR/drawdown, XIRR, reserve | Pass locally |
| Numeric citation gate | Match/mismatch, fabricated dynamic claim, Core recomputation, suppression | Pass locally |
| API vertical slice | Dataset → snapshot → scenario → evidence → durable run | Pass locally |
| RLS/composite FK | 6 PostgreSQL tests plus forward Alembic migration | Pass in CI run 33068700407 |
| Terraform topology | Format, provider initialization, and validation | Pass in CI run 33068700407 |
| Web type/build | Next.js 16 optimized build and TypeScript | Pass locally and in CI |
| Container vertical slice | MinIO upload and browser-to-Agent flow | Pass in CI run 33069158486 |
| Licensed provider | Contract, credentials, rights tests | Blocked externally |
| R2 complete exit | Full benchmark/attribution/property suite | Not approved |
| R3 complete exit | ≥99% bounded runs, provider and abstention evaluation | Not approved |

## Remaining blockers

- Select and contract a licensed point-in-time price/fundamental/news provider.
- Add benchmark total-return series, contribution/attribution, beta/tracking error, and market-state
  features.
- Add property/fuzz coverage beyond the included golden cases.
- Qualify PostgreSQL migration/RLS, checkpoint reconnect/failover, load, and restore in AWS staging.
- Run the frozen agent evaluation set and demonstrate bounded completion of at least 99%.
- Complete accessibility, security, compliance, and operating-mode approvals.

The Terraform service gates remain closed until those artifacts are signed.
