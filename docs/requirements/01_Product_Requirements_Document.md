# Portfolio Intelligence — Product Requirements Document

Version: 1.0  
Date: 26 August 2026  
Status: Engineering baseline  
Primary market: India  
Product mode: Read-only portfolio intelligence; no order execution

## 1. Executive decision

[Certain] The phrase “target return of 0.5x to 2x” cannot be treated as a guaranteed product outcome. A 0.5x wealth multiple means a 50% capital loss, while 2x means doubling capital; neither is meaningful without a time horizon, benchmark, liquidity need, and drawdown tolerance.

Portfolio Intelligence will optimize for the probability of meeting a user-declared goal subject to explicit risk, liquidity, concentration, and regulatory constraints. It will present ranges and scenarios, never a promised return.

Wealth multiple M = ending wealth / net invested capital. The comparable annualized target is:

CAGR = M raised to the power of 1 / years, minus 1

| Goal | Horizon | Implied CAGR | Product treatment |
|---|---:|---:|---|
| 0.5x | 5 years | -12.94% | Downside scenario, never a target |
| 1.5x | 5 years | 8.45% | Goal scenario with risk assumptions |
| 2.0x | 5 years | 14.87% | Aggressive scenario; show probability and drawdown |
| 2.0x | 10 years | 7.18% | Long-horizon goal scenario |

[Certain] Portfolio Intelligence remains the portfolio system of record. LangGraph orchestrates analysis, but deterministic services calculate positions, returns, risk, cash, benchmark comparisons, and scenarios. PDF research is evidence only. Brokerage XLS/XLSX data is authoritative for tax lots after reconciliation and user approval.

## 2. Product problem

### 2.1 User problem

Investors commonly have fragmented records across brokers, spreadsheets, PDFs, research reports, and portfolio-management statements. They can see values but often cannot answer:

- What do I actually own after reconciling conflicting files?
- What drove performance versus deposits, withdrawals, and the benchmark?
- Which risks, concentrations, and thesis changes matter now?
- What action is worth considering, why, and what could invalidate it?
- If I am new, what sequence of decisions should precede any security selection?

### 2.2 Product opportunity

[Likely] The defensible product is not another generic stock chatbot. It is an evidence-linked portfolio decision workspace that combines a trustworthy ledger, deterministic analytics, bounded agent research, explainable scenarios, and a feedback loop tied to later outcomes.

### 2.3 Regulatory positioning

[Certain] SEBI describes an Investment Adviser as a registered professional providing personalized guidance based on goals and risk appetite. Personalized recommendations must therefore be enabled only under a documented registered-IA operating model or regulated partner arrangement. The current baseline is analytics, education, and user-directed scenarios with no trade execution. See the current [SEBI Investment Adviser master circular](https://www.sebi.gov.in/legal/master-circulars/feb-2026/master-circular-for-investment-advisers_99569.html), [SEBI IA regulations](https://www.sebi.gov.in/legal/regulations/nov-2025/securities-and-exchange-board-of-india-investment-advisers-regulations-2013-and-securities-last-amended-on-november-25-2025-_98246.html), and [SEBI explanation of Investment Advisers](https://investor.sebi.gov.in/investment_advisor.html).

This is a product requirement, not legal advice. Counsel and a compliance owner must approve launch mode, wording, records, disclosures, and workflows.

## 3. Product vision and principles

### 3.1 Vision

Give each investor a continuously reconciled, explainable view of their portfolio and a disciplined way to evaluate the next decision.

### 3.2 Principles

1. Numbers before narrative: every portfolio claim traces to a deterministic metric or cited evidence.
2. Authority is explicit: ledger records outrank research PDFs; approved user corrections outrank inferred mappings.
3. Recommendations are proposals: the user or licensed adviser owns the final decision.
4. Uncertainty is visible: ranges, confidence, data freshness, and missing evidence accompany outputs.
5. No silent mutation: agents cannot alter holdings, house rules, suitability, or execution state.
6. Past performance is evaluation data, not proof of future results.
7. Conflicts are surfaced: disagreeing XLS files pause publication until reconciled.
8. Every tenant is isolated: authorization applies to storage, queues, tools, prompts, logs, and exports.

## 4. Personas and jobs to be done

| Persona | Situation | Primary job | Product response | Key risk |
|---|---|---|---|---|
| New investor | Has goals and cash but no portfolio | Build a sensible starting roadmap | Goal, horizon, emergency reserve, risk capacity, education, staged model allocation | Treating a roadmap as a guarantee |
| Self-directed investor | Holds listed equities across brokers | Understand performance and next choices | Reconciled ledger, attribution, risk, thesis monitoring, scenarios | Overtrading on noisy signals |
| Experienced or HNI investor | Multiple equity, PMS, model, or watch portfolios | Compare managers and allocations | Multi-portfolio benchmark, exposure, cash, overlap, contribution, evidence | Incomplete PMS data and style drift |
| Adviser or analyst | Reviews portfolios for clients | Produce consistent, auditable analysis | Role-based workspace, approval queue, evidence bundle, audit trail | Crossing advice and disclosure rules |
| Operations/compliance user | Owns data quality and controls | Resolve imports and audit outputs | Reconciliation workbench, policy gates, immutable events | Tenant or data leakage |

## 5. Goals and non-goals

### 5.1 MVP goals

- Import native-text PDFs, scanned PDFs, XLS, XLSX, and CSV through a secure asynchronous workflow.
- Reconcile brokerage tax-lot ledgers, holdings snapshots, cash, and transactions before analytics.
- Support self-managed, PMS, model, and “Portfolio of Interest” portfolios.
- Provide allocation, concentration, performance, benchmark, contribution, volatility, drawdown, and scenario views.
- Create versioned market-state snapshots so weekly reviews can distinguish portfolio change from changing volatility, trend, breadth, liquidity, and benchmark conditions.
- Provide evidence-linked AI Portfolio Chat with bounded LangGraph workflows.
- Support separate existing-investor and new-investor onboarding.
- Capture user feedback, recommendation outcomes, and weekly review triggers.
- Support secure read-only Upstox account linking; never expose broker credentials to the browser.

### 5.2 V1 non-goals

- Automated or one-click trading, order routing, or broker write APIs.
- Return guarantees, “sure-shot” language, or an objective to maximize return without risk.
- Mutual-fund execution, derivatives, leverage, margin, short selling, crypto, detailed tax filing, or fee optimization.
- Full corporate-action accounting beyond explicitly supported split, bonus, dividend, merger, and demerger rules.
- General-purpose autonomous agents with unrestricted web, shell, email, or broker access.
- Training a foundation model on customer data.
- Social copy-trading, public leaderboards, performance fees, or payment custody.
- Replacing a registered adviser, auditor, accountant, or legal professional.

## 6. Core user journeys

### 6.1 Existing investor

~~~mermaid
flowchart TD
    A["Human: create portfolio"] --> B["Human: upload or link account"]
    B --> C["System: scan and parse"]
    C --> D{"Reconciled?"}
    D -- No --> E["Human: resolve conflicts"]
    E --> D
    D -- Yes --> F["System: publish ledger"]
    F --> G["Agents: research and scenarios"]
    G --> H["Policy gate"]
    H --> I["Human: review, ask, decide"]
~~~

Step-by-step:

1. User authenticates, accepts privacy and product disclosures, and creates a portfolio.
2. User selects an import type: brokerage XLS/XLSX/CSV, statement PDF, research PDF, manual entry, or Upstox read-only link.
3. The system scans, classifies, parses, normalizes, and validates the source.
4. The user reviews detected accounts, instruments, dates, quantities, prices, currency, duplicates, and conflicts.
5. Only approved rows publish to the ledger. Research PDFs publish to the evidence repository, never the ledger.
6. Deterministic analytics generate a timestamped portfolio snapshot.
7. LangGraph agents assemble context, analyze portfolio risks, research relevant holdings, test scenarios, and pass through risk/compliance gates.
8. The dashboard and chat expose metrics, evidence, assumptions, alternatives, and uncertainty.
9. The user saves, rejects, or annotates a proposal. No order is placed.
10. Weekly review mode evaluates triggers, changed evidence, outcomes, and stale assumptions.

### 6.2 New investor

1. User selects “I am starting from scratch.”
2. User records goals, horizon, income stability, emergency reserve, liquidity needs, experience, loss capacity, and risk tolerance.
3. The system blocks allocation proposals when suitability is incomplete or internally inconsistent.
4. Deterministic planning calculates required contributions and goal scenarios.
5. The education agent explains asset classes, diversification, costs, and risk in plain language.
6. The scenario agent provides allocation ranges and staged actions, not equal-weight defaults.
7. The user selects a plan for monitoring and can later import actual holdings.
8. Registered-adviser mode, if enabled, adds adviser approval and required records before personalized advice is displayed.

### 6.3 Weekly trigger and review

1. Scheduler freezes an as-of timestamp and evaluates deterministic triggers.
2. Trigger candidates include allocation drift, concentration breach, drawdown, cash-rule breach, thesis evidence change, stale data, and material benchmark divergence.
3. Agents analyze only triggered topics and retrieve point-in-time evidence.
4. Policy gate suppresses unsupported, stale, or unsuitable proposals.
5. User receives a concise review with “what changed,” “why it matters,” and “what to examine.”
6. User feedback and later portfolio outcomes become evaluation records; they do not silently change the strategy.

## 7. Human versus agent autonomy

| Activity | Human | Deterministic system | AI agent | Gate |
|---|---|---|---|---|
| Set goals, horizon, reserve, and constraints | Owns | Validates completeness | Explains trade-offs | Human confirmation |
| Parse files | Reviews exceptions | Scans, extracts, normalizes | Assists classification and ambiguous mapping | Confidence plus reconciliation |
| Create or change ledger | Approves | Writes append-only records | Prohibited | Explicit approval |
| Calculate return and risk | Consumes | Sole authority | May request tools and explain | Formula/version audit |
| Research securities | Chooses scope | Enforces cutoff and source policy | Retrieves, debates, synthesizes | Evidence and freshness gate |
| Propose portfolio change | Decides | Tests constraints and scenarios | Creates ranked options | Suitability/compliance gate |
| Place order | Outside V1 | No endpoint | Prohibited | Architectural absence |
| Learn from outcomes | Gives feedback | Measures realized outcome | Retrieves similar lessons | Offline evaluator approval |

## 8. Functional requirements

### 8.1 Identity, tenancy, and consent

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| PRD-FR-001 | OIDC authentication with MFA/passkey option and server-side sessions | P0 | Unauthorized requests return 401; cross-tenant access returns 404 or 403 without data disclosure |
| PRD-FR-002 | Tenant, workspace, role, consent, and disclosure records | P0 | Every protected record is owner-scoped and every material consent is versioned |
| PRD-FR-003 | Data export and deletion workflow | P0 | Export is machine-readable; deletion is policy-aware and auditable |

### 8.2 Portfolio onboarding

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| PRD-FR-010 | Create self-managed, PMS, model, or Portfolio of Interest portfolios | P0 | Each has base currency, benchmark, valuation timezone, and ownership |
| PRD-FR-011 | Existing-investor and new-investor onboarding branches | P0 | Progress can resume; unsuitable or incomplete profiles block proposals |
| PRD-FR-012 | Configurable policy rules | P0 | Supports non-equal-weighting, protected cash reserve, max weights, exclusions, and rebalance cadence |
| PRD-FR-013 | Preserve the initial house rule of an untouched ₹25 lakh reserve | P0 for initial workspace | Scenarios never allocate protected reserve unless the owner explicitly versions the rule |
| PRD-FR-014 | Read-only Upstox OAuth linking | P1 | Credentials remain server-side; scopes exclude order placement |

### 8.3 Secure ingestion and reconciliation

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| PRD-FR-020 | Upload PDF, XLS, XLSX, and CSV | P0 | Extension, magic bytes, MIME, size, malware, encryption, and tenant path validated |
| PRD-FR-021 | Parse native and scanned PDFs | P0 | Page-level coverage, OCR status, evidence coordinates, and confidence are visible |
| PRD-FR-022 | Parse spreadsheet holdings and tax lots | P0 | Dates, quantities, amounts, currency, identifiers, and signs are typed; formulas/macros are not executed |
| PRD-FR-023 | Classify each source as ledger authority, snapshot, or evidence | P0 | PDF research cannot create executable positions; brokerage tax-lot file has highest import authority |
| PRD-FR-024 | Detect duplicates and conflicting files | P0 | Conflicts produce a review task; no silent overwrite or double count |
| PRD-FR-025 | Human mapping and approval workbench | P0 | User sees source row beside normalized row and can approve, edit, reject, or map |
| PRD-FR-026 | Idempotent import | P0 | Re-uploading identical content creates no duplicate transaction |

### 8.4 Analytics and dashboard

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| PRD-FR-030 | Holdings, cash, value, invested capital, unrealized P/L, and weights | P0 | Reconciles to approved ledger within defined tolerances |
| PRD-FR-031 | Money-weighted and time-weighted return with benchmark comparison | P0 | Formula version, period, cash flows, and price timestamp are disclosed |
| PRD-FR-032 | Allocation, concentration, overlap, contribution, volatility, and drawdown | P0 | Calculations are deterministic and regression-tested |
| PRD-FR-033 | Scenario engine | P0 | Shows baseline, upside, downside, assumptions, costs, taxes excluded, and protected-cash constraints |
| PRD-FR-034 | Snapshot history and weekly review | P1 | User can reproduce a historical dashboard from immutable inputs |
| PRD-FR-035 | Data-quality banner | P0 | Dashboard never implies completeness when unresolved or stale data exists |
| PRD-FR-036 | Point-in-time market-state context | P1 | Versioned market features and regime label respect as-of/known-at cutoffs and appear as context, not prediction |

### 8.5 AI analysis and chat

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| PRD-FR-040 | Evidence-linked portfolio chat | P0 | Every material factual or numeric claim links to a metric snapshot or evidence item |
| PRD-FR-041 | LangGraph analysis workflow with durable checkpoints | P0 | Runs resume after interruption and are scoped by tenant, portfolio, thread, and as-of time |
| PRD-FR-042 | Asset-research subgraph based on pinned TradingAgents design | P1 | Research remains isolated from ledger and broker execution |
| PRD-FR-043 | Risk and compliance gate | P0 | Blocks unsupported, stale, unsuitable, prohibited, or constraint-breaking output |
| PRD-FR-044 | Agent telemetry and user-visible run summary | P0 | Shows agents used, tools called, timestamps, evidence, decisions, and suppression reasons without exposing hidden reasoning |
| PRD-FR-045 | Feedback and outcome evaluation | P1 | Captures accepted/rejected/save-for-later and evaluates later benchmark/risk outcomes |
| PRD-FR-046 | Self-correction workflow | P1 | Proposed prompt/policy changes are evaluated offline, approved, versioned, and reversible |

### 8.6 Notifications and operations

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| PRD-FR-050 | In-app job and weekly-review notifications | P1 | Deduplicated, preference-aware, and linked to evidence |
| PRD-FR-051 | Operations queues for failed parsing, reconciliation, and agent runs | P0 | Retry is idempotent; tenant context and audit history are preserved |
| PRD-FR-052 | Admin controls without unrestricted customer-data browsing | P0 | Time-bound support access requires purpose, approval, and audit |

## 9. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| PRD-NFR-001 | Availability | 99.9% monthly for core read paths after GA |
| PRD-NFR-002 | API latency | p95 under 400 ms for cached portfolio reads, excluding asynchronous jobs |
| PRD-NFR-003 | Dashboard experience | p75 LCP under 2.5 seconds on supported mobile networks |
| PRD-NFR-004 | File processing | 95% of supported 50-page native PDFs and 25 MB workbooks reach review within 120 seconds |
| PRD-NFR-005 | AI response | p95 time to first streamed token under 5 seconds; bounded full run under 5 minutes |
| PRD-NFR-006 | Security | Zero known critical vulnerabilities at release; annual independent penetration test |
| PRD-NFR-007 | Accessibility | WCAG 2.2 AA |
| PRD-NFR-008 | Recovery | RPO 15 minutes and RTO 4 hours for production data |
| PRD-NFR-009 | Observability | Trace ID across UI, API, job, agent, tool, and audit event |
| PRD-NFR-010 | Reproducibility | Every recommendation reconstructable from versioned inputs, tools, model, prompt, and policy |

## 10. Product success metrics

### 10.1 North-star metric

Weekly Evidence-Backed Decisions: count of weekly active portfolios for which a user completes a reviewed insight, scenario, or no-action decision with current reconciled data and linked evidence.

### 10.2 Leading indicators

| Metric | MVP target | Why |
|---|---:|---|
| First portfolio published | At least 65% of users who begin upload | Measures onboarding completion |
| Median time to first trusted dashboard | Under 10 minutes for supported files | Measures ingestion value |
| Auto-mapped rows | At least 90% on certified templates | Measures operational efficiency |
| Reconciliation completion | At least 85% within one session | Measures trust workflow |
| Numeric claim evidence coverage | 100% | Prevents uncited financial assertions |
| Weekly review completion | At least 35% of activated users | Measures habit value |
| Insight usefulness | At least 70% useful or very useful | Measures decision support |
| Thirty-day retained activated users | At least 35% in beta | Early retention |
| Support incidents caused by wrong holdings | Under 0.5% of published imports | Trust guardrail |

### 10.3 Outcome metrics

[Certain] Portfolio return is not the sole product success metric. It is evaluated after controlling for cash flows, horizon, benchmark, and risk.

- Goal progress versus the user’s required return.
- Time-weighted excess return and tracking error versus selected benchmark.
- Maximum drawdown, volatility, and concentration change.
- Percentage of proposals that stayed within user constraints.
- Calibration: whether stated confidence aligns with observed outcomes.
- Decision quality: evidence coverage, user understanding, and avoided constraint breaches.

## 11. Release plan

| Phase | Duration | Exit outcome |
|---|---:|---|
| 0. Compliance and foundations | 3 weeks | Launch mode, data classification, threat model, schemas, metric definitions approved |
| 1. Ingestion and ledger | 7 weeks | Certified PDF/XLS templates, reconciliation, manual correction, portfolio publication |
| 2. Analytics and dashboard | 6 weeks | Trusted metrics, scenarios, snapshots, numeric-first dashboard |
| 3. LangGraph chat and research | 7 weeks | Evidence chat, bounded agents, risk gate, telemetry, feedback |
| 4. Beta and hardening | 5 weeks | Security, performance, accessibility, DR, UAT, operational playbooks |

[Likely] A focused MVP is achievable in 28 weeks with a stable cross-functional team of 9–11: product lead, design lead, two frontend, two backend/data, two AI/ML, one QA automation, and shared security/compliance/SRE.

## 12. Launch gates

1. Legal counsel documents whether the launch is analytics-only, Research Analyst, Investment Adviser, or partner-delivered.
2. No critical tenant-isolation, file-upload, authorization, or prompt-injection findings.
3. Golden-ledger calculations pass at 100%.
4. Certified-template extraction and reconciliation thresholds in the QA plan pass.
5. All numeric AI claims have evidence; prohibited outputs are blocked in red-team tests.
6. Upstox integration is read-only and verified by scope and absence of order endpoints.
7. WCAG 2.2 AA audit has no critical blocker.
8. Incident response, backup restore, model rollback, and kill-switch exercises pass.

## 13. Dependencies, assumptions, and open decisions

### Confirmed constraints

- India-first; INR is the default base currency.
- Listed equities are the V1 investable scope.
- Portfolio Intelligence owns ledger and analytics.
- LangGraph is required for agent workflows.
- Upstox is read-only.
- No equal-weighting rule is configurable and enabled for the initial workspace.
- ₹25 lakh protected reserve remains untouched in the initial workspace.
- Weekly trigger/review mode is required.

### Decisions required by Phase 0

| Decision | Owner | Deadline | Default if unresolved |
|---|---|---|---|
| Regulatory operating model | Founder, counsel, compliance | End of week 2 | Analytics and education only |
| Advice review authority | Compliance and product | End of week 2 | Human user only; no personalized imperative |
| Market-data vendor and licenses | Product and finance | End of week 3 | Delayed data with explicit timestamps |
| Model provider and data-retention terms | AI and security | End of week 3 | Enterprise no-training endpoint |
| Supported broker templates | Product and data | End of week 3 | Upstox plus two highest-volume beta templates |
| Corporate-action coverage | Finance-data lead | End of week 3 | Splits, bonus, cash dividends only |

## 14. Traceability

This PRD is implemented by:

- Architecture decisions and data flow: [Technical Design and System Architecture](03_Technical_Design_and_System_Architecture.md)
- Screens, interaction states, and accessibility: [UX/UI Design Specification](04_UX_UI_Design_Specification.md)
- Entities and API contracts: [Data Model and API Specification](05_Data_Model_and_API_Specification.md)
- Verification and release gates: [QA and Test Plan](06_QA_and_Test_Plan.md)
- Market, positioning, pricing, and business case: [Market and Business Requirements](02_Market_and_Business_Requirements_Document.md)
