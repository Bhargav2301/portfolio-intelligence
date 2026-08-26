# Portfolio Intelligence — Market and Business Requirements Document

Version: 1.0  
Date: 26 August 2026  
Status: Business baseline  
Related product scope: [Product Requirements Document](01_Product_Requirements_Document.md)

## 1. Executive business case

[Certain] The market need is real, but “AI that beats the market” is not a credible or compliant position. The business should sell trusted consolidation, decision discipline, evidence, risk visibility, and time saved. Investment outcomes remain variable.

[Certain] India has a large and expanding base of retail market participants. NSE reported 12.7 crore unique registered investors as of 31 January 2026, and later reported crossing 13 crore in April 2026. The mutual-fund industry reported ₹85.76 lakh crore of assets under management at 31 July 2026. These are market-scale indicators, not the product’s addressable-user count. Sources: [NSE January 2026 release](https://nsearchives.nseindia.com/web/pressrelease/2026-02/PR_cc_12022026_20260212155410.pdf), [NSE 13-crore update](https://www.nseindia.com/mediacoverage/nse-registered-investor-base-crosses-13-crore-130-million-unique-investors-unique-pans_1), and [AMFI July 2026 AUM](https://www.amfiindia.com/articles/indian-mutual).

[Likely] Portfolio Intelligence can occupy a narrower, higher-trust category between free portfolio trackers and full-service wealth management: multi-source portfolio intelligence with an auditable AI research and review layer.

## 2. Market definition

### 2.1 Category

Primary category: consumer and adviser-facing portfolio intelligence SaaS.

Adjacent categories:

- Portfolio aggregation and net-worth tracking.
- Securities research and screening.
- Digital investment advice and goal planning.
- Model portfolios and execution platforms.
- Adviser workflow, reporting, and client portals.

### 2.2 Initial geographic and asset scope

- Geography: India.
- Currency: INR primary, with schema support for multi-currency.
- Assets in V1: listed equities, cash, and benchmark indices.
- Portfolio types: self-managed, PMS, model, and Portfolio of Interest.
- Data channels: PDF, XLS, XLSX, CSV, manual input, and read-only Upstox.

### 2.3 Customer segments

| Segment | Need intensity | Ability to pay | Acquisition route | Initial priority |
|---|---|---|---|---|
| Self-directed investors with multiple accounts | High | Medium | Content, broker communities, referrals | 1 |
| Experienced investors and HNIs | High | High | Adviser/PMS networks, referrals, private beta | 1 |
| New investors seeking a roadmap | Medium | Low to medium | Education, SEO, employer programs | 2 |
| SEBI-registered advisers and research teams | High | High | Direct sales and partnerships | 2 after compliance |
| General net-worth trackers | Low differentiation | Low | High-cost consumer channels | Not a first target |

## 3. Customer problem and willingness to pay

### 3.1 Pain points

1. Fragmented holdings and inconsistent broker exports.
2. Confusion between investment return and cash-flow effects.
3. Generic AI answers with no portfolio evidence.
4. Research overload without a disciplined decision record.
5. Poor visibility into concentration, drawdown, overlap, and thesis drift.
6. No repeatable way to learn from accepted and rejected decisions.

### 3.2 Paid value

Users should pay for:

- Reconciliation of files and tax lots.
- Trusted, reproducible analytics across portfolios.
- Evidence-linked answers grounded in their own approved data.
- Weekly exception-based review instead of daily noise.
- Scenario comparison under explicit portfolio constraints.
- Historical decision and outcome records.
- Faster adviser/client review and audit preparation.

Users should not be charged on the premise that the system guarantees a return.

## 4. Competitive landscape

### 4.1 Current alternatives

| Alternative | Verified current positioning | Strength | Gap Portfolio Intelligence targets |
|---|---|---|---|
| INDmoney | Tracks investments, family accounts, and net worth; offers free stock portfolio tracking | Broad aggregation and execution ecosystem | Evidence-level reconciliation and auditable agent workflow are not its primary public positioning |
| ET Money Genius | Investment-intelligence service for where, when, and how much to invest | Recognizable consumer advice proposition | Multi-source tax-lot reconciliation and user-owned evidence workspace |
| Tickertape Pro | Smart multi-asset portfolio analysis, linked demat accounts, diversification, red flags, and alerts | Strong research and portfolio analytics | Deep document ingestion, decision provenance, and workflow-level agent telemetry |
| Value Research | Free multi-asset portfolio tracker plus paid research/advisory products | Long research history, portfolio depth, corporate-action handling | Conversational, evidence-linked multi-agent decision workspace |
| smallcase | Expert-managed model portfolios connected to brokers | Discovery, model portfolios, and execution | Independent system of record and cross-portfolio diagnostic layer |
| Spreadsheets and advisers | Flexible and trusted when maintained well | Human judgment and custom rules | Time, consistency, provenance, and repeatable monitoring |

Sources: [INDmoney portfolio tracker](https://www.indmoney.com/features/stocks-shares-portfolio-tracker), [ET Money Genius description](https://www.etmoney.com/help/genius/about-genius/what-is-genius), [Tickertape pricing/features](https://www.tickertape.in/pricing), [Value Research Portfolio Manager](https://www.valueresearchonline.com/stories/224343/track-analyse-investments-value-research-portfolio-manager-tool/), and [smallcase](https://www.smallcase.com/).

[Certain] These sources verify positioning and visible features, not internal capability. Competitive claims must be rechecked quarterly and before sales use.

### 4.2 Differentiation thesis

Portfolio Intelligence is differentiated when all five layers operate together:

1. Authority-aware ingestion: brokerage ledger, statement snapshot, and research evidence are kept distinct.
2. Deterministic portfolio truth: the LLM never invents financial calculations.
3. Bounded agent research: multiple viewpoints, point-in-time evidence, policy gates, and no execution.
4. Decision memory: user feedback and later outcomes are evaluated without silently rewriting strategy.
5. Explainable constraint engine: reserve, concentration, exclusion, suitability, and no-equal-weight rules are enforced in scenarios.

### 4.3 Defensibility

[Likely] Defensibility will come from data quality and workflow, not the underlying LLM:

- Growing library of certified broker and PMS parsing templates.
- Normalized, user-corrected transaction histories and mapping rules.
- Portfolio-specific evaluation datasets and decision outcomes.
- Reproducible evidence graph and policy history.
- Trust earned through accurate reconciliation and conservative failure modes.
- Adviser integrations and operational workflows.

## 5. Market sizing

### 5.1 Sizing method

The following is a planning model, not an external market forecast.

| Layer | Assumption | Calculation | Indicative annual value |
|---|---|---:|---:|
| TAM | 13 crore registered equity investors and ₹3,000 annual software spend | 130,000,000 × ₹3,000 | ₹39,000 crore |
| SAM | 5% are digitally active, self-directed, multi-account or advice-seeking users | 6,500,000 × ₹3,000 | ₹1,950 crore |
| Beachhead SOM | 30,000 paid users in year 3 at ₹4,200 blended ARR | 30,000 × ₹4,200 | ₹12.6 crore ARR |

[Guessing] The 5% serviceable-user assumption and ₹3,000 willingness to pay require validation. The model intentionally excludes institutional clients and does not treat total AUM as revenue.

### 5.2 Validation plan

Before general availability:

- Interview 30 self-directed investors, 15 HNIs/PMS users, and 10 registered advisers.
- Test reconciliation prototypes on at least 200 de-identified documents from 10 source formats.
- Run pricing tests with ₹0, ₹3,999/year, ₹9,999/year, and adviser-seat variants.
- Measure willingness to pay after users see a reconciled dashboard, not from concept descriptions.
- Require at least 20% paid-intent conversion in the high-intent beta cohort before scaling acquisition.

## 6. Business objectives and requirements

| ID | Business requirement | Measure | Target |
|---|---|---|---|
| BRD-BR-001 | Establish a trusted India-first portfolio intelligence category | Activated portfolios | 10,000 by end of year 2 |
| BRD-BR-002 | Reach repeatable paid conversion | Activated-to-paid | At least 8% consumer beta; 15% high-intent cohort |
| BRD-BR-003 | Maintain sustainable unit economics | Gross margin | At least 75% after model, data, storage, support, and payment variable costs |
| BRD-BR-004 | Retain users through weekly review value | Paid annual retention | At least 70% |
| BRD-BR-005 | Avoid performance-promise dependence | Revenue mix | 100% subscription/usage/seat fees in V1 |
| BRD-BR-006 | Protect trust | Material wrong-ledger incidents | Fewer than 0.5% of published imports |
| BRD-BR-007 | Operate inside approved regulatory mode | Compliance exceptions | Zero unapproved personalized-advice releases |
| BRD-BR-008 | Control AI economics | AI and research variable cost | Under 20% of subscription revenue |

## 7. Pricing and packaging

### 7.1 Recommended launch packaging

| Plan | Proposed price | Included value | Guardrails |
|---|---:|---|---|
| Explore | ₹0 | One portfolio, manual/CSV import, basic dashboard, five chat questions monthly | No deep research runs; delayed data |
| Plus | ₹399/month or ₹3,999/year | Three portfolios, PDF/XLS imports, weekly review, core analytics, 40 chat questions | Fair-use limits and queued research |
| Pro | ₹999/month or ₹9,999/year | Ten portfolios, advanced risk/scenarios, more research, exports, priority processing | No execution; market-data license limits |
| Adviser Workspace | ₹2,499/user/month plus client tier | Approval queues, client workspaces, audit bundles, policy templates | Available only after regulatory and contractual readiness |

[Guessing] These are test prices, not validated prices. They should be changed by experiment, contribution margin, and compliance scope.

### 7.2 Pricing rules

- Never charge a percentage of investment return in V1.
- Never advertise “2x” as expected performance.
- Include GST treatment and billing disclosures in final commercial terms.
- Separate licensed market-data costs when redistribution rules require it.
- Do not degrade ledger accuracy, security, or regulatory controls by tier.
- Use rate limits for expensive deep research, not hidden response-quality degradation.

## 8. Unit economics and break-even

### 8.1 Illustrative Plus plan

| Item | Annual amount per paid user |
|---|---:|
| Subscription revenue | ₹3,999 |
| Model, search, and market-data variable cost | ₹720 |
| Storage, processing, and notifications | ₹120 |
| Payment fees and refunds | ₹120 |
| Variable customer support | ₹180 |
| Contribution | ₹2,859 |
| Contribution margin | 71.5% |

[Guessing] The launch target is at least 75% blended gross margin; the table deliberately uses conservative early-stage costs. Caching deterministic analytics, trigger-based rather than daily agent runs, and model routing are essential.

### 8.2 Break-even planning

[Guessing] With ₹3.5 crore annual fixed operating cost and ₹3,750 blended annual contribution per paid account, operating break-even requires about 9,334 paid-account equivalents:

Break-even accounts = annual fixed cost / annual contribution per account

The operating plan should use a range:

- Lean case: ₹2.8 crore fixed cost, 7,467 account equivalents.
- Base case: ₹3.5 crore fixed cost, 9,334 account equivalents.
- Expansion case: ₹5.0 crore fixed cost, 13,334 account equivalents.

These calculations exclude fundraising costs, taxes, and exceptional legal or data-license expenses.

## 9. ROI target: product and business interpretation

### 9.1 Investor outcome

The system will accept a desired terminal multiple only after the user specifies:

- Net invested capital and recurring contributions.
- Horizon and withdrawal schedule.
- Minimum protected reserve.
- Maximum tolerable drawdown.
- Liquidity needs and loss capacity.
- Benchmark and investable universe.

It will return:

- Required CAGR.
- Historical and simulated range with explicit assumptions.
- Probability bands, not certainty.
- Downside and drawdown scenarios.
- Feasibility classification: plausible, stretched, or internally inconsistent.
- Alternatives such as higher contribution, longer horizon, or lower goal.

### 9.2 Product claim policy

Prohibited:

- “We will double your money.”
- “Guaranteed 0.5x–2x return.”
- “AI-selected winning stocks.”
- Cherry-picked backtests without fees, survivorship controls, and benchmark.

Permitted after compliance review:

- “See what return your goal requires.”
- “Understand portfolio risk, concentration, and benchmark performance.”
- “Explore evidence-linked scenarios before you decide.”
- “Track whether a past thesis held up.”

### 9.3 Why the business case does not depend on excess return

[Certain] A subscription business can create value even when the recommended decision is “do nothing.” The monetizable benefit is reduced analysis time, fewer data errors, better discipline, transparent risk, and auditability. This avoids incentives to manufacture activity or take excessive risk.

## 10. Go-to-market plan

### 10.1 Beachhead

Target investors who already maintain spreadsheets, use more than one broker/PMS, and conduct weekly or monthly reviews. They feel the reconciliation and evidence problem most acutely and can evaluate quality.

### 10.2 Channels

1. Founder-led private beta with experienced investors and advisers.
2. Educational content around return attribution, drawdown, and file reconciliation.
3. Broker/PMS statement-template landing pages with secure sample reports.
4. Partnerships with SEBI-registered advisers for supervised-advice mode.
5. Referral program based on subscription credits, not investment outcomes.
6. Employer financial-wellness pilot for new-investor roadmap mode.

### 10.3 Funnel

| Stage | User event | Target conversion |
|---|---|---:|
| Visitor to signup | Selects portfolio diagnosis or starting roadmap | 12% |
| Signup to activated | Publishes a reconciled portfolio or completes suitability roadmap | 65% |
| Activated to value | Reviews first evidence-linked insight | 70% |
| Value to paid | Starts Plus or Pro trial/plan | 8–15% by cohort |
| Paid to annual retained | Renews | 70% |

## 11. Regulatory, privacy, and business controls

### 11.1 Advice and research

[Certain] SEBI maintains separate regimes for personalized Investment Advisers and non-personalized Research Analysts. The latest regulations available on the official site were last amended 25 November 2025, with master circulars dated 6 February 2026. Sources: [Investment Adviser regulations](https://www.sebi.gov.in/legal/regulations/nov-2025/securities-and-exchange-board-of-india-investment-advisers-regulations-2013-and-securities-last-amended-on-november-25-2025-_98246.html), [Research Analyst regulations](https://www.sebi.gov.in/legal/regulations/nov-2025/securities-and-exchange-board-of-india-research-analysts-regulations-2014-last-amended-on-november-25-2025-_98248.html), [IA master circular](https://www.sebi.gov.in/legal/master-circulars/feb-2026/master-circular-for-investment-advisers_99569.html), and [RA master circular](https://www.sebi.gov.in/legal/master-circulars/feb-2026/master-circular-for-research-analysts_99571.html).

Business requirements:

- Legal classification and compliance matrix before beta.
- Registration or regulated-partner arrangement before personalized-advice mode.
- Versioned suitability, disclosures, conflicts, fees, rationale, approvals, and communications.
- Clear separation of general research, portfolio analytics, scenario output, and personalized advice.
- Record retention, grievance handling, and audit export defined by compliance.
- Marketing review for every return, performance, model, or AI claim.

### 11.2 Privacy

[Certain] India’s Digital Personal Data Protection Rules, 2025 have staggered commencement dates, so the implementation plan must track which provisions are in force at launch rather than assuming the entire regime begins on one date. Sources: [DPDP Act, 2023](https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf) and [DPDP Rules, 2025 Gazette](https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf).

Required controls:

- Purpose-specific, versioned consent.
- Data minimization and configurable retention.
- User access, correction, export, and erasure workflows.
- Processor inventory and contractual restrictions on model training.
- Breach and grievance workflows.
- Age gating; no child-account onboarding in V1.

## 12. Operating model

### 12.1 Core roles

| Role | Accountability |
|---|---|
| Product owner | Outcomes, scope, metrics, pricing experiments |
| Compliance owner | Launch mode, policies, disclosures, audit readiness |
| Data operations lead | Parser certification, reconciliation SLAs, source authority |
| Investment methodology owner | Metric definitions, scenario assumptions, research policy |
| AI safety owner | Evaluation, prompt/model versions, red-team gates, kill switch |
| Security/DPO function | Privacy, access, incident response, vendor review |
| Customer operations | Import exceptions, user support, escalation |

### 12.2 Service levels

- Critical security or tenant-isolation incident: immediate containment; executive notification.
- Published-ledger correctness incident: triage within one hour; affected analytics suspended.
- File-processing failure: visible immediately; retry or human review within one business day.
- Material market-data delay: freshness banner and recommendation suppression.
- Agent-policy failure: disable affected graph/prompt version through feature flag.

## 13. Business risks and mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Product crosses into regulated personalized advice | Medium | Critical | Counsel-approved modes, policy engine, licensed partner, audit records |
| Users interpret scenarios as guarantees | High | High | Goal feasibility UX, uncertainty, prohibited-claim tests, comprehension checks |
| Wrong holdings undermine trust | Medium | Critical | Authority hierarchy, reconciliation, user approval, immutable source links |
| LLM and market-data costs erase margin | Medium | High | Triggered runs, caching, small-model routing, plan limits, cost telemetry |
| Competitors copy chat features | High | Medium | Data-quality workflow, decision memory, certified parsers, adviser operations |
| User acquisition is too expensive | Medium | High | High-intent beachhead, content, adviser partnerships, referral |
| Historical evaluation leaks future data | Medium | High | Point-in-time stores, cutoff enforcement, leakage tests |
| Model output causes harmful action | Medium | Critical | Read-only product, no orders, suitability/risk gate, human decision |

## 14. Stage gates and investment decisions

| Gate | Evidence required | Decision |
|---|---|---|
| Discovery | 55 interviews and 200 representative files | Proceed to build certified templates |
| Alpha | 95% of supported imports reconcile; 100% numeric evidence coverage | Invite external beta |
| Paid beta | At least 20% paid intent in high-intent cohort; support load under model | Confirm packaging |
| GA | Compliance, security, accessibility, DR, model evaluation, and SLAs pass | Public launch |
| Adviser mode | Registration/partner, contracts, suitability, records, supervision tested | Enable personalized workflow |

## 15. Cross-document implications

- PRD-FR-023 and PRD-FR-024 protect the business promise of trusted consolidation.
- TDD architecture must enforce read-only integrations and source authority.
- UX must make uncertainty, data freshness, and human approval unmistakable.
- The data model must retain consent, suitability, rationale, evidence, and outcomes.
- QA must treat tenant isolation, ledger correctness, and prohibited claims as release blockers.
