# Portfolio Intelligence — Technical Design and System Architecture

Version: 1.0  
Date: 26 August 2026  
Status: Target architecture  
Related requirements: [PRD](01_Product_Requirements_Document.md), PRD-FR-001 through PRD-FR-052 and PRD-NFR-001 through PRD-NFR-010

## 1. Architecture decision

[Certain] Portfolio Intelligence, not the LLM or TradingAgents, is the system of record.

The target design has four authority layers:

1. Source and ledger layer: uploaded files, broker data, normalized transactions, positions, cash, and snapshots.
2. Deterministic intelligence layer: valuations, returns, risk, attribution, benchmark, constraint, and scenario engines.
3. Evidence layer: research documents, market observations, citations, freshness, and point-in-time metadata.
4. Agent experience layer: LangGraph workflows that select tools, debate bounded questions, explain results, and propose user-reviewable options.

No agent writes a transaction, changes a holding, weakens a constraint, or places an order.

## 2. Current baseline and target state

### 2.1 Existing baseline to preserve

- Next.js 16.2.6 and React 19.2.6 user experience compiled through Vinext.
- OpenAI Sites/Cloudflare Worker deployment for the web layer.
- Cloudflare D1 owner-scoped application data.
- Separate Python FastAPI/LangGraph service.
- TradingAgents pinned to commit a33fd4c0f134485a43553a2c23a63cb14adbd88f.
- Read-only Upstox OAuth bridge with server-held credentials.
- Bounded TradingAgents debates: one research round and one risk round by default.

### 2.2 Production target

[Likely] Retain the edge web/BFF deployment, but move the authoritative financial ledger, agent checkpoints, audit records, and evidence metadata to managed PostgreSQL. Use D1 only for edge-local preferences or cache if it remains useful. PostgreSQL row-level security supports policies by command and role, but application authorization must still be enforced and tested. See [PostgreSQL row security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

Target components:

- Web: Next.js, React, TypeScript, server-rendered dashboard, accessible design system.
- Edge BFF: authenticated API façade, request validation, rate limiting, signed-upload coordination.
- Core API: Python FastAPI with Pydantic contracts and domain services.
- Workflow: LangGraph in a dedicated agent service; durable PostgreSQL checkpointer and owner-scoped store.
- Jobs: Redis-compatible queue plus durable jobs/outbox tables; worker pools separated by trust level.
- Data: PostgreSQL, object storage, Redis cache, time-series market-data adapter, optional pgvector for evidence retrieval.
- Observability: OpenTelemetry traces, structured logs, metrics, model/tool cost ledger, immutable audit events.
- Secrets: managed KMS and secret manager; short-lived service credentials.

## 3. System context

~~~mermaid
flowchart TD
    U["Human user or adviser"] --> W["Web UI and edge BFF"]
    W --> C["Core portfolio API"]
    C --> D["Ledger, analytics, evidence"]
    C --> A["LangGraph agent service"]
    D --> A
    A --> X["Approved data and research tools"]
    C --> B["Read-only broker connectors"]
~~~

Trust boundary rules:

- The browser receives neither broker tokens nor model-provider credentials.
- The BFF derives tenant and user identity from the authenticated server session; it never accepts a client-supplied tenant as authority.
- The Core API owns domain authorization and validates every resource relation.
- Agent tools receive a capability-scoped run context, not raw infrastructure credentials.
- Uploaded objects remain quarantined until scanning and type validation pass.
- External web content is untrusted evidence, never executable instruction.

## 4. Component architecture

| Component | Responsibility | Owns | Does not own |
|---|---|---|---|
| Web UI | Onboarding, upload, review, dashboard, chat, feedback | View state and accessible interaction | Financial calculations or credentials |
| Edge BFF | Session, CSRF, request shaping, rate limits, upload handshakes | Short-lived user session | Ledger or agent truth |
| Identity service | OIDC/OAuth 2.1, MFA/passkeys, roles, session revocation | Identity and authentication | Portfolio authorization |
| Core Portfolio API | Tenancy, portfolios, imports, ledger, jobs, analytics orchestration | Domain policy and write authority | Free-form agent reasoning |
| Ingestion service | Scan, classify, parse, normalize, reconcile | Extraction candidates and provenance | Published ledger without approval |
| Portfolio ledger | Transactions, lots, cash, snapshots, corrections | Authoritative approved financial records | Research opinion |
| Analytics service | Return, risk, benchmark, attribution, scenarios | Versioned deterministic metric snapshots | Natural-language advice |
| Evidence service | Documents, chunks, citations, market facts, known-at time | Evidence provenance and retrieval | Holdings authority |
| LangGraph agent service | Plans bounded workflows and synthesizes output | Agent run state and proposals | Ledger writes or broker execution |
| Policy service | Suitability, reserve, concentration, freshness, regulatory modes | Versioned constraints and gates | User goals |
| Broker connector | Read-only account/holding synchronization | Encrypted broker grants and sync cursors | Order placement |
| Notification service | In-app/email events after user preference checks | Delivery state | Investment decisions |
| Operations console | Exception queues and audited support | Resolution workflow | Unlogged data browsing |

## 5. End-to-end data flow

### 5.1 File upload to trusted portfolio

~~~mermaid
sequenceDiagram
    participant H as Human
    participant UI as Web and BFF
    participant IN as Ingestion
    participant DB as Ledger
    participant AG as Agents
    H->>UI: Select file and source role
    UI->>IN: Create signed quarantined upload
    IN->>IN: Scan, identify, parse, validate
    IN-->>H: Preview, confidence, conflicts
    H->>IN: Correct and approve
    IN->>DB: Publish idempotent ledger batch
    DB->>DB: Compute analytics snapshot
    DB->>AG: Emit portfolio-ready event
    AG-->>H: Evidence-linked review
~~~

Detailed flow:

1. Client requests POST /v1/uploads with filename, declared type, size, checksum, portfolio, and source role.
2. BFF authenticates the session and Core API authorizes portfolio write access.
3. API returns a short-lived single-object signed URL under a tenant-isolated quarantine prefix.
4. Client uploads directly to object storage and calls upload completion with checksum.
5. Ingestion worker verifies size, checksum, extension, MIME, magic bytes, encryption metadata, and object path.
6. Malware and active-content scanning runs in a network-restricted worker.
7. Classifier identifies native PDF, scanned PDF, legacy XLS, XLSX, or CSV and determines ledger/evidence role.
8. Parser creates page/sheet/row provenance plus normalized candidates. Raw source is immutable.
9. Validation applies schema, numeric, date, identifier, duplicate, balance, and cross-file reconciliation rules.
10. User sees source and normalized values side by side. Low-confidence or conflicting rows require action.
11. Approval creates an immutable import batch and append-only ledger events inside one transaction.
12. Outbox event triggers materialized positions, cash, valuations, and analytics snapshot.
13. Only the published snapshot is available to agents. Unresolved candidates are excluded and disclosed.

### 5.2 Chat and analysis flow

1. User submits a question with portfolio and optional as-of date.
2. Core API persists the message and creates a tenant-scoped agent run.
3. Context assembler retrieves suitability, policy version, portfolio snapshot, data-quality state, past decisions, and relevant evidence.
4. Router classifies the request: explanation, deterministic analysis, research, scenario, or prohibited execution.
5. Deterministic requests call typed analytics tools directly.
6. Research requests call the isolated asset-research subgraph only for confirmed instrument identifiers.
7. Scenario requests create candidate actions, then call deterministic scenario and constraint tools.
8. Risk/compliance gate checks suitability, evidence, freshness, conflicts, claim language, and product mode.
9. Response composer emits answer, metrics, evidence IDs, assumptions, uncertainty, alternatives, and next human action.
10. Output evaluator records structural checks and quality signals.
11. UI streams status and response. No hidden chain-of-thought is shown; user-visible telemetry lists stages, tools, evidence, and gates.

## 6. Secure file-ingestion design

The upload control follows the principles in the [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html): allowlisted types, generated storage names, size limits, signature checks, scanning, authorization, and storage outside the web root.

### 6.1 Supported formats

| Format | MVP support | Processing | Restrictions |
|---|---|---|---|
| PDF, native text | Yes | pypdf/pdfplumber extraction and table adapters | Reject embedded executables; sanitize rendering |
| PDF, scanned | Yes | Rasterize in sandbox, OCR, page confidence | User review required below threshold |
| PDF, password protected | Conditional | Password used only in isolated job memory | Never persist or log password |
| XLS, legacy BIFF | Yes | Isolated legacy parser or conversion with macros disabled | No formula or external-link execution |
| XLSX | Yes | openpyxl read-only/data-only and streaming parser | Reject macros; ignore external links |
| CSV | Yes | Encoding detection, dialect preview, typed streaming parser | Formula-injection neutralization on export |
| XLSM/XLSB/ODS | No in MVP | Quarantine and explain unsupported type | Never silently convert |

### 6.2 Threat controls

- Maximum object size 50 MB in MVP; lower per-plan limits allowed.
- Maximum 200 PDF pages, 50 workbook sheets, 500,000 rows, and bounded decompressed size.
- File name is metadata only; server generates storage key.
- MIME plus magic bytes plus parser confirmation; extension alone is insufficient.
- ClamAV or managed malware scanner before parsing.
- Containers run non-root, read-only filesystem, no outbound network, low CPU/memory/time limits.
- PDF JavaScript, launch actions, attachments, and embedded files are stripped or rejected.
- Spreadsheet formulas are treated as strings or cached values; no macros, DDE, external references, or plugins execute.
- Prompt-like text inside documents is content, never agent instruction.
- Extracted HTML/Markdown is escaped before UI rendering.
- Duplicate detection uses cryptographic object hash plus source identity and period.
- Raw, rendered, and derived objects use separate prefixes and access policies.

### 6.3 PDF extraction workflow

1. Inspect encryption, page count, text coverage, and embedded object types.
2. Classify each page as native text, image, table-heavy, or mixed.
3. Extract native text with bounding boxes; OCR only where necessary.
4. Run document-family classifier: broker statement, PMS report, company research, annual report, or unknown.
5. Apply versioned template adapter when available.
6. Extract tables with page, region, row, and cell coordinates.
7. Normalize dates, Indian number formats, currency, identifiers, and negative signs.
8. Cross-check totals, opening/closing balances, page continuation, and row counts.
9. Assign field-level confidence and issue codes.
10. Route unknown or low-confidence fields to review.

### 6.4 XLS/XLSX extraction workflow

1. Enumerate sheets, used ranges, merged cells, hidden sheets, formulas, and external links without execution.
2. Identify header row and statement family.
3. Present detected column mapping to the user.
4. Parse numeric values with decimal arithmetic; preserve raw cell text.
5. Resolve trade date, settlement date, symbol, exchange, ISIN, side, quantity, price, fees-as-unallocated, and source lot reference.
6. Detect duplicate rows and overlapping reporting periods.
7. Reconcile holdings implied by transactions with closing holdings snapshots.
8. Publish only approved mappings and rows.

### 6.5 Source authority

| Source | Authority | Allowed effect |
|---|---|---|
| Approved brokerage tax-lot XLS/XLSX/CSV | Ledger authority | Create imported transaction/lot events |
| Read-only broker API | Ledger or snapshot authority by endpoint | Create synchronized events after reconciliation |
| Broker/PMS statement PDF | Snapshot or ledger candidate | Requires certified template and approval |
| User manual entry | Ledger authority with explicit user confirmation | Creates correction/manual event |
| Research PDF or web article | Evidence only | May support analysis; never changes holdings |
| LLM inference | None | May propose mapping or action; cannot publish |

## 7. Portfolio ledger and deterministic analytics

### 7.1 Ledger invariants

- Append-only transactions and correction events; no destructive edits.
- Money and quantity use fixed-precision decimals, never binary floats.
- Each record carries tenant, owner, portfolio, account, source, import batch, effective date, recorded-at time, and version.
- Duplicate source reference within a portfolio/import authority is rejected.
- Published batches are immutable; corrections reverse and replace.
- Instrument identity is resolved before valuation; NSE/BSE aliases require confirmed .NS or .BO mapping for the TradingAgents adapter.
- Cash is explicit and never inferred from missing rows.
- The initial workspace’s protected ₹25 lakh reserve is a versioned constraint, not an ordinary cash allocation.

### 7.2 Analytics

Versioned deterministic functions calculate:

- Position quantity and lot roll-forward.
- Market value and invested capital.
- Unrealized and realized economic P/L, excluding detailed tax treatment in V1.
- Time-weighted return and money-weighted return.
- Benchmark return and active return.
- Contribution by instrument, sector, and portfolio.
- Allocation, concentration, overlap, and cash.
- Volatility, downside deviation, drawdown, recovery time, beta where data suffices, and tracking error.
- Data quality, price freshness, and coverage.
- Market-state features including benchmark trend, realized volatility, breadth, dispersion, correlation, liquidity proxy, and drawdown regime.

Each analytics snapshot stores:

- As-of market timestamp.
- Known-at processing timestamp.
- Input ledger version and price-source version.
- Formula/methodology version.
- Currency and benchmark.
- Missing-data flags.
- Hash of canonical inputs for reproducibility.

### 7.3 Market-state engine

[Likely] Changing market state should be a deterministic, point-in-time context service rather than an LLM opinion. A versioned market-state snapshot contains observed features, data coverage, methodology, and a descriptive regime label such as low-volatility trend, high-volatility drawdown, or mixed breadth.

The engine:

1. Freezes as_of and known_at cutoffs.
2. Computes benchmark trend, realized volatility, market breadth, dispersion, cross-asset or cross-sector correlation, liquidity proxy, and drawdown features from licensed data.
3. Applies a versioned rule-based or statistically validated classifier.
4. Emits feature values, label, stability, and confidence/coverage.
5. Supplies context to weekly triggers, scenario stresses, and asset research.
6. Never converts a regime label directly into a trade.

### 7.4 Scenario engine

Inputs are typed candidate actions, not natural-language instructions. The engine:

1. Validates available cash and protected reserve.
2. Applies user exclusions, maximum weights, and no-equal-weight rule.
3. Simulates quantities, allocation, concentration, expected transaction costs, and tax exclusion.
4. Recalculates risk and goal metrics.
5. Produces baseline, upside, downside, and stress views.
6. Returns constraint violations and sensitivity, not a prediction.

## 8. LangGraph agent architecture

LangGraph is appropriate because it supports durable execution, streaming, persistence, and human-in-the-loop interrupts. See the official [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence), and [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts).

### 8.1 Portfolio analysis graph

~~~mermaid
flowchart TD
    C["Context assembler"] --> V["Data-validity gate"]
    V --> R["Request router"]
    R --> P["Portfolio diagnostics"]
    R --> E["Asset research subgraph"]
    P --> S["Scenario planner"]
    E --> S
    S --> G["Risk and compliance gate"]
    G --> O["Response and evaluation"]
~~~

### 8.2 Agent responsibilities

| Node/agent | Inputs | Tools | Output | Autonomous limit |
|---|---|---|---|---|
| Context assembler | User, thread, portfolio, as-of | Profile, policy, snapshot, evidence retrieval | Typed run context | Cannot infer missing suitability |
| Data-validity gate | Run context | Quality and freshness rules | Proceed, narrow, or interrupt | Must pause on critical conflicts |
| Request router | User question | Intent schema and policy | Allowed workflow | Cannot route to execution |
| Portfolio diagnostician | Snapshot and question | Deterministic analytics | Findings and ranked issues | No financial arithmetic in model text |
| Asset research subgraph | Confirmed instruments and cutoff | Market, fundamentals, news, sentiment tools | Bull/bear/risk evidence packet | One debate round by default |
| Scenario planner | Findings and constraints | Scenario engine | Ranked candidate scenarios | Cannot bypass reserve or suitability |
| Risk/compliance gate | Proposal, mode, evidence | Policy and claim checks | Allow, revise, suppress, or human review | Final machine authority over release |
| Response composer | Approved packet | Citation renderer | User-facing answer | Cannot add uncited factual claims |
| Output evaluator | Full trace | Structural and semantic tests | Scores and incidents | Cannot alter displayed answer post hoc |

### 8.3 TradingAgents adaptation

[Certain] TauricResearch/TradingAgents is used only as an asset-research subgraph. Its analyst, debate, trader, and risk-manager structure does not become the portfolio ledger or execution engine.

Required changes:

- Replace single-ticker CLI entry with a typed FastAPI request.
- Invoke every run through the lifecycle wrapper so checkpoint, memory, and final-state logging cannot be bypassed.
- Create one immutable graph configuration per worker process; do not mutate process-global dataflow configuration between tenants.
- Replace local Markdown memory with tenant/portfolio-scoped PostgreSQL records.
- Replace fixed five-day raw-return reflection with configurable, benchmark- and risk-adjusted outcome evaluation.
- Persist checkpoints and artifacts; remove in-memory production run storage.
- Remove or disable order-like trader semantics. Output is a thesis and scenario candidate.
- Enforce point-in-time cutoffs on every research tool.
- Disable live StockTwits, Reddit, Polymarket, and other non-point-in-time sources in historical runs.
- Record provider, query, retrieval time, source publication time, cutoff, and content hash.
- Cap research and risk debate rounds; default remains one each.
- Validate tool output against schemas before adding it to graph state.

### 8.4 State model

Every run state includes:

- run_id, tenant_id, owner_id, portfolio_id, thread_id.
- request_id, initiated_by, product_mode, as_of, known_at.
- portfolio_snapshot_id, policy_version_id, suitability_version_id.
- market_state_snapshot_id and its as_of/known_at cutoff.
- user_question, classified_intent, allowed_tools.
- evidence_ids, analytics_ids, scenario_ids.
- node statuses, retries, interrupts, token/cost use.
- proposal, policy decision, citations, evaluator scores.

Thread and checkpoint keys must be non-guessable and owner-scoped. A thread identifier alone never authorizes access.

### 8.5 Self-improvement without unsafe online learning

~~~mermaid
flowchart TD
    F["User feedback and outcomes"] --> E["Offline evaluation"]
    E --> C["Candidate prompt or policy"]
    C --> T["Golden and red-team tests"]
    T --> A{"Human approval"}
    A -- Pass --> R["Canary and rollback"]
    A -- Reject --> X["Archive evidence"]
~~~

Rules:

- No customer conversation automatically trains or changes production behavior.
- Feedback is separated from factual outcome measurement.
- Recommendations are evaluated at predefined horizons against benchmark, drawdown, and constraints.
- Candidate prompt, model, policy, and tool changes are versioned.
- Promotion requires offline tests, compliance approval for material behavior, canary traffic, and rollback.
- Memory retrieval filters by tenant, portfolio type, time horizon, and policy compatibility.
- Delete requests propagate to raw content, embeddings, derived memories, and future training datasets.

## 9. Human-in-the-loop controls

Mandatory interrupts:

- Low-confidence instrument identity or file mapping.
- Conflicting authoritative files.
- Missing suitability for a personalized scenario.
- Proposal that approaches or breaches reserve, liquidity, concentration, or exclusion rules.
- Material source freshness failure.
- Compliance-mode uncertainty.
- Support override or data correction.

Human actions are explicit commands: approve import, edit mapping, reject row, accept evidence, save scenario, request adviser review, change policy, or dismiss insight. Merely viewing a response is not consent.

## 10. Multi-tenancy

### 10.1 Isolation model

- Shared application with tenant_id on every domain record.
- PostgreSQL row-level security enabled and forced on tenant tables.
- API sets tenant context from verified membership, never request body.
- Background jobs carry signed tenant context and re-authorize before work.
- Object keys use random identifiers under tenant prefixes; access uses one-time signed URLs.
- Cache keys include tenant, portfolio, authorization scope, and data version.
- Vector retrieval requires tenant filter before similarity search.
- Logs redact financial values and personal identifiers by default.
- Support access is just-in-time, purpose-bound, approved, and audited.

### 10.2 Roles

| Role | Portfolio access | Mutation | AI output approval |
|---|---|---|---|
| Owner | All owned workspace resources | Full within product scope | May approve own scenarios |
| Editor | Assigned portfolios | Import and correct | Cannot change billing or tenant policy |
| Viewer | Assigned portfolios | None | None |
| Adviser | Assigned client portfolios | Notes and proposals | May approve only in enabled regulated mode |
| Compliance reviewer | Metadata and queued outputs | Policy decisions | Approves/suppresses regulated output |
| Support operator | Time-bound scoped case | Defined repair actions | None |

### 10.3 Isolation verification

- Automated cross-tenant negative tests on every endpoint.
- RLS test suite executed against real migrations.
- Storage and queue isolation tests.
- Fuzzing of object, portfolio, run, thread, and export identifiers.
- Quarterly access review and tenant-escape penetration test.

## 11. Security architecture

### 11.1 Authentication and sessions

- OIDC/OAuth 2.1 authorization code with PKCE.
- HttpOnly, Secure, SameSite session cookie at BFF.
- Short-lived access tokens and rotating refresh sessions.
- MFA/passkeys for privileged roles and strongly encouraged for investors.
- Reauthentication for exports, deletion, broker relink, and role changes.
- CSRF protection on state-changing browser requests.

### 11.2 Authorization

- Deny by default.
- Tenant membership plus resource-level authorization plus policy scope.
- Service identities have least-privilege roles.
- Agent tools use per-run capabilities with expiry and exact portfolio/resource allowlists.
- No generic SQL, filesystem, shell, email, or broker-order tools available to agents.

### 11.3 Data protection

- TLS 1.2 minimum, TLS 1.3 preferred.
- AES-256 or cloud-provider equivalent at rest.
- Envelope encryption with KMS; separate production keys and regular rotation.
- Sensitive fields such as PAN, account number, broker token, and document password are separately classified.
- Broker tokens encrypted and never logged; document passwords are ephemeral.
- Backups encrypted, access-controlled, restore-tested, and lifecycle-managed.
- Model providers contractually barred from training on customer data; minimum retention configuration.

### 11.4 AI-specific threats

| Threat | Control |
|---|---|
| Prompt injection in PDF/web content | Content/instruction separation, tool allowlist, quoted evidence, no dynamic tool grants |
| Data exfiltration through tools | Tenant-scoped capabilities, egress allowlist, DLP, output scanning |
| Hallucinated numbers | Typed analytics tools and 100% numeric citation requirement |
| Historical leakage | as_of and known_at enforcement; point-in-time provider tests |
| Model drift | Version pinning, evaluation gates, canary, rollback |
| Excessive autonomy | Bounded graph, max iterations/cost/time, mandatory gates, no execution endpoint |
| Sensitive reasoning exposure | User-visible summaries only; no hidden chain-of-thought storage or display |

## 12. API and event integration

Core API uses versioned REST/JSON for resources and server-sent events for job/agent progress.

Key properties:

- OpenAPI-generated client and server contract tests.
- Idempotency-Key required for uploads, import publication, scenario creation, and feedback.
- Optimistic concurrency using version or ETag for user edits.
- 202 Accepted plus job resource for asynchronous work.
- Cursor pagination; no unbounded list endpoints.
- Error envelope includes code, human message, trace ID, field issues, and retryability.

Primary events:

- upload.completed
- document.scanned
- extraction.review_required
- import.published
- portfolio.snapshot_ready
- market_data.refreshed
- review.triggered
- agent.run_completed
- recommendation.reviewed
- recommendation.outcome_due
- policy.version_changed

Transactional outbox guarantees that database commit and event publication do not diverge.

## 13. Deployment topology

~~~mermaid
flowchart TD
    E["Cloudflare edge: web and BFF"] --> K["Private API ingress"]
    K --> C["Core API pool"]
    K --> A["Agent API pool"]
    C --> P["PostgreSQL and object storage"]
    A --> P
    C --> Q["Redis and worker pools"]
    A --> Q
    Q --> X["Allowlisted external providers"]
~~~

Deployment requirements:

- Separate development, test, staging, and production accounts/projects.
- Infrastructure as code and policy-as-code.
- Immutable container images with SBOM, signatures, and vulnerability scans.
- Blue/green or canary deploys for API, agent graph, prompts, and model routes.
- Worker pools separated for file parsing, OCR, portfolio analytics, and agents.
- Agent service concurrency bounded by tenant and model budget.
- Schema migrations are backward compatible and independently reversible.
- Production admin access uses SSO, MFA, device controls, and audited short-lived elevation.

## 14. Observability and audit

### 14.1 Telemetry

One trace ID spans:

browser event → BFF → Core API → job/outbox → worker → agent node → tool → model call → policy gate.

Metrics:

- Request latency, errors, saturation, and availability.
- Queue age, retry rate, dead letters, extraction throughput.
- Parser accuracy by template/version and source.
- Reconciliation exceptions by code.
- Analytics freshness and recompute latency.
- Agent run time, node retries, interrupts, tool failures, model tokens, and cost.
- Evidence coverage, citation validity, policy suppressions, and safety incidents.
- Tenant-level budgets without exposing cross-tenant data.

### 14.2 Audit events

Immutable events record actor, action, resource, purpose, before/after hash, time, IP/device metadata where permitted, trace ID, and policy decision. Audit records are separately access-controlled and integrity-protected.

Do not log:

- Raw access/broker tokens.
- Document passwords.
- Full PAN or account numbers.
- Entire documents or chat content in operational logs.
- Hidden model reasoning.

## 15. Reliability and recovery

### 15.1 Failure behavior

| Failure | User behavior | System behavior |
|---|---|---|
| Upload interrupted | Resume or retry | Multipart checksum and idempotent completion |
| Parser crashes | Job shows retrying | Retry bounded; dead-letter and preserve quarantine |
| Reconciliation conflict | Dashboard marked incomplete | Block publication; preserve both sources |
| Market data stale | Show timestamp and limited mode | Suppress price-sensitive recommendations |
| Model unavailable | Show deterministic dashboard and retry option | Circuit breaker and approved fallback model |
| Agent node fails | Show partial status without advice | Resume from checkpoint or fail closed |
| Policy service unavailable | No recommendation release | Fail closed |
| Broker API unavailable | Show last successful sync | No credential reset or write attempt |

### 15.2 Recovery objectives

- PostgreSQL point-in-time recovery with RPO 15 minutes.
- Core service RTO 4 hours.
- Object-store versioning and cross-zone durability.
- Quarterly restore test and annual regional failover exercise.
- Checkpoint migration tests before LangGraph upgrades.
- Feature flags to disable broker sync, external web tools, a parser, a model, or the whole agent layer independently.

## 16. Performance and capacity model

Initial design capacity:

- 100,000 registered users.
- 20,000 monthly active portfolios.
- 2,000 simultaneous web sessions.
- 250 concurrent file-processing jobs across isolated pools.
- 100 concurrent agent runs with per-tenant quota.
- 10 million ledger events and 100 million market-price points without redesign.

Scaling strategy:

- Partition high-volume ledger/audit tables by time and tenant hash only when measured.
- Precompute portfolio snapshots and cache versioned reads.
- Stream workbook rows and PDF pages; never load unbounded files into memory.
- Use queue backpressure and fair scheduling across tenants.
- Research only holdings/questions in scope; do not run the full graph on every page load.
- Use smaller models for routing, schema repair, and summarization; reserve larger models for bounded synthesis.

## 17. Architecture decision records

| ADR | Decision | Rationale | Trade-off |
|---|---|---|---|
| TDD-ADR-001 | Portfolio Intelligence owns financial truth | Prevents LLM-created state | More deterministic engineering |
| TDD-ADR-002 | PostgreSQL is production system of record | Transactions, precision, RLS, audit, checkpoints | Migration from D1 |
| TDD-ADR-003 | LangGraph is isolated behind FastAPI | Durable workflows and controlled scaling | Additional service boundary |
| TDD-ADR-004 | TradingAgents is an asset-research subgraph | Reuses debate mechanics without false portfolio semantics | Adapter work and reduced autonomy |
| TDD-ADR-005 | Files publish only after reconciliation | Trust and reproducibility | Adds onboarding friction |
| TDD-ADR-006 | Research PDFs are evidence only | Prevents untrusted text changing holdings | Some manual mapping remains |
| TDD-ADR-007 | No execution endpoint in V1 | Regulatory and safety boundary | User acts elsewhere |
| TDD-ADR-008 | Human-reviewed offline self-correction | Improves safely without silent drift | Slower iteration |
| TDD-ADR-009 | Point-in-time evidence is mandatory | Prevents backtest leakage | Fewer historical sources |
| TDD-ADR-010 | One graph configuration per worker process | Avoids mutable global cross-run contamination | More worker variants |

## 18. Implementation sequence

1. Define domain schemas, tenancy model, source authority, analytics formulas, and API contracts.
2. Build identity, portfolio, object quarantine, and audit foundations.
3. Implement certified spreadsheet and PDF ingestion with reconciliation.
4. Implement ledger, snapshots, market-data adapter, and deterministic analytics.
5. Build dashboard and data-quality states.
6. Implement agent service, persistence, typed tools, and policy gate.
7. Adapt pinned TradingAgents code into the asset-research subgraph.
8. Add chat, citations, telemetry, feedback, and offline evaluator.
9. Add read-only Upstox sync behind feature flag.
10. Complete security, load, accessibility, DR, and compliance gates.

## 19. Technical exit criteria

- All P0 API and event contracts versioned and contract-tested.
- Every tenant table and object path passes isolation tests.
- Raw-to-ledger lineage is reproducible for every imported value.
- Deterministic analytics match golden models exactly within documented decimal tolerances.
- Agent runs resume from durable checkpoints and never cross tenant or as-of boundaries.
- No agent-accessible order, generic network, shell, or unrestricted data tool exists.
- Model/provider, prompt, graph, tool, evidence, policy, and calculation versions reconstruct each output.
- Security, performance, accessibility, and recovery thresholds in the QA plan pass.
