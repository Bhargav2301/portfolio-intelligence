# Portfolio Intelligence — UX/UI Design Specification

Version: 1.0  
Date: 26 August 2026  
Status: Product-design baseline  
Related requirements: [PRD](01_Product_Requirements_Document.md), PRD-FR-001 through PRD-FR-052

## 1. Experience objective

[Certain] The interface must make “trusted data, bounded analysis, human decision” obvious. A polished chat window over unreconciled holdings would create false confidence.

The experience is numeric-first and declarative:

- Show portfolio state before AI interpretation.
- Show data freshness and quality before return.
- Show “what changed” before “what to do.”
- Show evidence and assumptions beside each material claim.
- Use plain language first, with technical detail on demand.
- Require explicit user actions for data publication, policy changes, and scenario decisions.
- Avoid equal-weight suggestions; scenarios must honor configured allocation rules.
- Preserve the initial workspace’s protected ₹25 lakh reserve in every relevant view.

## 2. UX principles

1. Trust is a visible state, not a disclaimer.
2. One primary decision per screen.
3. Progressive disclosure for advanced metrics.
4. No red/green-only meaning.
5. No hidden automation.
6. Every number has period, currency, source, and freshness.
7. Every AI claim has evidence or is labeled interpretation.
8. Recommendations use conditional language and alternatives.
9. “No action” is a first-class outcome.
10. Novice and experienced modes share data truth but vary explanation depth.

## 3. Information architecture

~~~mermaid
flowchart TD
    H["Home"] --> P["Portfolios"]
    H --> R["Weekly review"]
    H --> C["AI Portfolio Chat"]
    P --> D["Dashboard"]
    P --> I["Imports and reconciliation"]
    P --> S["Scenarios and decisions"]
    H --> E["Evidence library"]
    H --> T["Settings, rules, connections"]
~~~

Primary navigation:

- Home
- Portfolios
- Review
- Ask AI
- Evidence
- Settings

Contextual portfolio navigation:

- Overview
- Holdings
- Performance
- Risk
- Transactions
- Scenarios
- Decisions
- Data sources

## 4. Global application shell

### 4.1 Desktop concept

~~~mermaid
block-beta
  columns 12
  top["Global navigation, portfolio, as-of date"]:12
  side["Portfolio sections"]:2
  main["Trusted metrics and analysis"]:7
  ai["AI review and ask"]:3
  quality["Data quality, freshness, and active rules"]:12
~~~

### 4.2 Mobile concept

Mobile uses a single content column:

1. Portfolio and as-of selector.
2. Data-quality banner.
3. Net value and goal progress.
4. “What changed” cards.
5. Allocation and risk summaries.
6. Primary action: review or ask.
7. Bottom navigation: Home, Portfolio, Review, Ask, More.

Do not compress wide financial tables into unreadable grids. On mobile, each row becomes a labeled card with a separate details view and CSV export.

### 4.3 Persistent status strip

Every portfolio screen shows:

- As-of market timestamp.
- Last ledger reconciliation time.
- Data-quality state: Trusted, Needs review, Partial, or Stale.
- Current product mode: Analytics, Research, or Registered Adviser.
- Active high-impact rules, including protected reserve.

## 5. User journeys

### 5.1 Entry choice

First meaningful screen:

| Choice | Label | Explanation |
|---|---|---|
| Existing investor | “Analyze what I own” | Upload or securely link current holdings |
| New investor | “Build a starting roadmap” | Define goals, reserve, horizon, and risk first |
| Explore portfolio | “Study a portfolio of interest” | Track a model or hypothetical portfolio separately |

No choice implies that the system will execute investments.

### 5.2 Existing-investor journey

~~~mermaid
journey
    title Existing investor: first trusted review
    section Set up
      Create portfolio: 5: Human
      Choose source role: 4: Human
      Upload or link: 4: Human
    section Establish truth
      Scan and parse: 3: System
      Review mappings: 3: Human
      Resolve conflicts: 2: Human
      Publish ledger: 5: Human, System
    section Decide
      Inspect dashboard: 5: Human
      Run bounded analysis: 4: Agents
      Review evidence and scenario: 4: Human
      Save decision or no-action: 5: Human
~~~

Success condition: the user reaches a trusted dashboard and understands whether any data remains unresolved.

### 5.3 New-investor journey

1. Welcome explains that investment value can fall and that goal scenarios are not guarantees.
2. User enters goal amount, current investable amount, recurring contribution, and horizon.
3. User identifies emergency/protected reserve; the initial workspace defaults to ₹25 lakh and requires an explicit versioned change.
4. User completes risk-capacity and experience questions one concept per page.
5. System highlights contradictions, such as a two-year horizon plus high equity dependence.
6. Roadmap shows required CAGR, contribution alternatives, allocation ranges, learning checklist, and next review date.
7. User may save the roadmap, upload future holdings, or request registered-adviser review when available.

Success condition: the user understands goal feasibility and the next safe step without receiving an unlicensed security-level instruction.

### 5.4 Returning weekly-review journey

1. Home shows one summary: “Three items changed; one needs review.”
2. User opens the review.
3. Each item contains trigger, portfolio impact, evidence change, uncertainty, and suggested examination.
4. User can ask a follow-up, compare a scenario, dismiss, snooze, or record no action.
5. Completion screen summarizes decisions and the next trigger.

## 6. Screen specifications

### 6.1 Authentication and consent

Components:

- Email/SSO sign-in, passkey/MFA prompt.
- Privacy notice summary with full policy link.
- Separate consent toggles for portfolio processing, optional broker connection, and optional product-improvement data.
- Product-mode disclosure.

Requirements:

- Consent is not bundled with marketing.
- A user can continue with file upload without linking a broker.
- Reauthentication is required for export, deletion, and broker relink.
- Session expiry preserves unsaved form input locally only when safe.

### 6.2 Portfolio creation

Fields:

- Portfolio name.
- Type: Self-managed, PMS, Model, Portfolio of Interest.
- Base currency.
- Benchmark.
- Valuation timezone.
- Goal and horizon.
- Review cadence.

Advanced fields are collapsed. The default benchmark must be selected explicitly, not guessed from holdings.

### 6.3 Upload center

Layout:

| Zone | Content |
|---|---|
| Source choice | Brokerage ledger, broker statement, PMS statement, research, manual |
| Drop zone | Accepted formats, 50 MB limit, privacy note |
| Processing list | Queued, scanning, parsing, review, published, failed |
| Help | Download template, supported providers, encrypted/password file guidance |

File card states:

- Uploading: progress and cancel.
- Scanning: security check.
- Parsing: pages/sheets processed.
- Needs password: one-time secure entry, never saved.
- Needs review: issue count and primary action.
- Published: batch, row count, portfolio, time.
- Failed: plain-language reason, safe retry, support trace ID.

### 6.4 Reconciliation workbench

[Certain] This is the trust-critical screen.

Desktop layout:

| Left | Center | Right |
|---|---|---|
| File/sheet/page navigator | Source row and normalized row | Issues, confidence, mapping, action |

Required controls:

- Filter by error, warning, duplicate, conflict, or low confidence.
- Compare conflicting files by source, report period, and import authority.
- Bulk-approve only rows meeting policy threshold.
- Edit symbol/ISIN mapping with exchange confirmation.
- Show .NS/.BO mapping before research runs.
- Approve, reject, mark duplicate, or keep both with explanation.
- Undo until publication; corrections after publication create reversal events.
- Show reconciliation equation and residual.
- Persistent counter: approved, unresolved, excluded.

Publication dialog:

- Summarizes transactions, holdings, cash, source precedence, unresolved exclusions, and analytics impact.
- Requires checkbox: “I reviewed the mappings and understand excluded rows.”
- Uses action label “Publish portfolio data,” not “Continue.”

### 6.5 Portfolio dashboard

#### Summary row

- Current value.
- Net invested capital.
- Total P/L and percentage.
- Time-weighted return.
- Benchmark return.
- Protected and available cash.

Each metric displays:

- Period.
- As-of timestamp.
- Formula/method tooltip.
- Source snapshot.
- Missing-data indicator.

#### Main panels

1. What changed: ranked exceptions since last review.
2. Allocation: asset, sector, position, cash; target/range only when configured.
3. Performance: portfolio versus benchmark with cash-flow markers.
4. Contribution: which positions drove result; separate contribution from current weight.
5. Risk: drawdown, volatility, concentration, liquidity proxy, and rule breaches.
6. Goal: required versus realized trajectory with scenario band.
7. AI review: concise synthesized findings and evidence count.

#### Data states

| State | Banner | Allowed actions |
|---|---|---|
| Trusted | “All authoritative sources reconciled” | Full analytics and bounded analysis |
| Needs review | “12 rows could change these totals” | Review; AI limited to unaffected data |
| Partial | “Cash or transaction history is incomplete” | Snapshot metrics only; no full return claim |
| Stale | “Prices last updated…” | Historical view; price-sensitive proposals suppressed |

### 6.6 Holdings and transactions

Table capabilities:

- Column customization.
- Sort and filter.
- Group by account, sector, or portfolio.
- Exact quantity, average price, current value, invested value, unrealized P/L, weight, data quality.
- Expand row for tax lots, source lineage, research, and decisions.
- Export with spreadsheet-formula neutralization.

Do not default-sort by largest gain; default to portfolio weight to reduce speculative salience.

### 6.7 AI Portfolio Chat

Chat composer:

- Portfolio and as-of context chips.
- Request type shortcuts: Explain performance, Review risk, Compare scenario, Research holding.
- Evidence scope selector.
- “Use current web research” toggle with freshness explanation.

Response anatomy:

1. Direct answer.
2. Key numbers.
3. Why this matters.
4. Evidence and timestamps.
5. Assumptions and uncertainty.
6. Scenario options.
7. Human action controls.

Agent run drawer:

- Run status.
- Stages completed.
- Tools used.
- Data cutoff.
- Evidence sources.
- Constraint checks.
- Suppressed claims or partial failures.
- Model/graph version available in technical details.

Do not expose hidden chain-of-thought. Present concise rationales and evidence.

### 6.8 Scenario comparison

~~~mermaid
flowchart TD
    B["Current portfolio"] --> O["Option A"]
    B --> T["Option B"]
    O --> C["Constraint and risk comparison"]
    T --> C
    C --> H["Human: save, reject, or revise"]
~~~

Comparison columns:

- Baseline.
- Option A.
- Option B.

Rows:

- Available cash and protected reserve.
- Allocation by sector/position.
- Largest position.
- Expected transaction cost.
- Tax impact marked “not calculated” in V1.
- Volatility and drawdown scenario.
- Goal-path range.
- Rule violations.
- Evidence strength.

The primary action is “Save decision record.” There is no buy/sell execution action.

### 6.9 Weekly review

Review-card hierarchy:

- Trigger label and severity.
- “What changed” in one sentence.
- Quantified impact.
- Evidence freshness.
- Recommended examination, not imperative action.
- Buttons: Ask why, Compare scenario, Record no action, Snooze.

Completion summary:

- Reviewed items.
- Saved decisions.
- Dismissed items with reason.
- Data issues still open.
- Next scheduled review.

### 6.10 Evidence library

Filters:

- Portfolio, instrument, source type, author/publisher, publication date, known-at time, freshness, and quality.

Evidence detail:

- Document metadata.
- Page/sheet/cell reference.
- Extracted passage or metric.
- Source authority badge: Ledger, Snapshot, Research, or External.
- Linked claims and decisions.
- Superseded/contradicted evidence.

### 6.11 Settings and controls

Sections:

- Profile and security.
- Suitability and goals.
- Portfolio rules.
- Data sources and broker connections.
- Notification cadence.
- Consent and privacy.
- Exports and deletion.
- Adviser or workspace roles.

High-impact policy changes show before/after impact and require reauthentication or confirmation.

## 7. Component requirements

| Component | Required states | Accessibility |
|---|---|---|
| Metric card | Loading, current, stale, partial, error | Programmatic label includes value, period, currency, status |
| Data-quality banner | Trusted, review, partial, stale | Role=status for update; no color-only meaning |
| Confidence badge | High, medium, low, unknown | Text label and explanation; not percentage theater |
| Evidence citation | Available, archived, inaccessible | Keyboard focus; source, date, and location announced |
| Upload card | All processing states | Live progress is polite, cancel is keyboard accessible |
| Financial table | Sort, filter, group, empty, error | Semantic table, caption, header association, focus order |
| Chart | Loading, current, insufficient data | Text summary and accessible data table |
| Rule chip | Active, breached, near limit | Includes threshold and current value |
| Scenario card | Baseline, option, invalid | Constraint failures announced before results |
| Agent progress | Queued, running, paused, complete, failed | Live region with throttled updates |
| Disclosure | Inline, expanded, acknowledged | Not hidden behind hover-only tooltip |

## 8. Visual and interaction system

### 8.1 Visual hierarchy

- Neutral canvas and restrained accent colors.
- Use tabular numerals for financial values.
- Positive/negative uses sign, words, icons, and color.
- Data-quality colors are independent from market gain/loss colors.
- One primary CTA per view.
- Dense tables for experienced users; summary mode for novices.

### 8.2 Tokens

| Token | Requirement |
|---|---|
| Type scale | Minimum 16 px body; 14 px only for secondary metadata at compliant contrast |
| Spacing | 4 px base grid; touch targets at least 24 × 24 CSS px, preferably 44 × 44 |
| Contrast | WCAG 2.2 AA for text, controls, charts, focus, and disabled-state alternatives |
| Focus | Visible 2 px or stronger indicator with sufficient contrast and no clipping |
| Motion | Respect prefers-reduced-motion; no essential information in animation |
| Numbers | Indian grouping option, currency code/symbol, consistent decimal policy |

## 9. Content design

### 9.1 Terminology

Use:

- “Scenario” instead of “forecast” when uncertainty is material.
- “Proposal” or “option” instead of “trade recommendation” in analytics mode.
- “Required annual return” instead of “target profit.”
- “Data needs review” instead of “AI confidence is low.”
- “No action recorded” as a valid decision.

Avoid:

- Guaranteed, safe return, sure, winner, beat the market.
- Unqualified “buy,” “sell,” or “you should.”
- False precision in probability or confidence.
- “AI thinks” without identifying evidence and method.
- “Real-time” when data is delayed.

### 9.2 Explanation pattern

For novice mode:

- Name the metric.
- Explain what it measures.
- Explain the user’s current value.
- Explain the limitation.
- Offer one next learning or review action.

For experienced mode:

- Lead with value, period, benchmark, and contribution.
- Expose methodology, evidence, and export.
- Preserve dense comparison and keyboard navigation.

## 10. Human control and agent autonomy

| UX signal | Meaning |
|---|---|
| “System calculated” | Deterministic and reproducible |
| “AI interpretation” | Model-generated synthesis grounded in listed inputs |
| “Needs your review” | Agent or parser cannot continue safely |
| “Policy blocked” | Output violated freshness, suitability, evidence, or constraint rule |
| “Saved decision” | User recorded intent; no order was placed |
| “Outcome evaluated” | Later portfolio/benchmark data was compared with prior proposal |

Required confirmation points:

- Publish an import.
- Resolve a material conflict.
- Change suitability or protected reserve.
- Save a scenario as a decision.
- Enable registered-adviser sharing.
- Export or delete data.
- Link/relink a broker.

## 11. Accessibility standard

[Certain] Target WCAG 2.2 Level AA. W3C organizes WCAG under perceivable, operable, understandable, and robust principles. Sources: [WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/) and [W3C WCAG overview](https://www.w3.org/WAI/standards-guidelines/wcag/).

Mandatory practices:

- Complete keyboard operation, logical focus, skip links, and focus restoration.
- Correct landmarks, headings, field labels, descriptions, and error associations.
- Accessible authentication and no cognitive-function test.
- Minimum target size and adequate spacing.
- Reflow at 320 CSS px without losing information.
- Charts paired with summaries and tables.
- Status updates via appropriate live regions without excessive announcements.
- Timeouts warned and extendable.
- Error prevention and review for financial-data publication.
- Language set per page and plain-language option.
- Screen-reader testing with NVDA/Chrome and VoiceOver/Safari.
- 200% and 400% zoom testing.

## 12. Responsive and browser support

MVP support:

- Latest two stable versions of Chrome, Edge, Safari, and Firefox.
- iOS Safari and Android Chrome current plus previous major version.
- Viewports from 320 CSS px to wide desktop.
- Graceful degradation when streaming responses or Web Workers are unavailable.

## 13. Empty, loading, and failure states

| Situation | Required message | Primary action |
|---|---|---|
| No portfolio | Explain both onboarding paths | Add portfolio |
| Portfolio not reconciled | State what is missing and metric impact | Review data |
| No historical prices | Explain unavailable return/risk metrics | Check instrument mapping |
| Agent unavailable | Keep dashboard usable | Retry analysis |
| Evidence inaccessible | Mark claim as unsupported/archived | View alternate evidence |
| Stale broker link | Show last sync and cause | Relink securely |
| Constraint makes scenario impossible | Explain breached rule and alternatives | Revise scenario, not rule |

Skeleton screens may preserve layout but must not display plausible fake values.

## 14. UX telemetry

Events must avoid raw financial values in analytics payloads.

| Event | Key properties |
|---|---|
| onboarding_path_selected | path, product_mode |
| upload_started/completed | format, size band, source role |
| reconciliation_issue_resolved | issue type, method, time |
| portfolio_published | source count, unresolved excluded count |
| metric_explained | metric ID, user mode |
| ai_question_submitted | intent, evidence mode, not question text |
| evidence_opened | source type, freshness band |
| scenario_compared | options count, constraint result |
| decision_recorded | accept, reject, no-action, snooze |
| weekly_review_completed | trigger count, decision count |

## 15. Design acceptance criteria

- A novice can explain the difference between invested capital, current value, and return after onboarding usability testing.
- At least 90% of test users notice a Needs review or Stale data banner before interpreting performance.
- No tested user believes “Save decision” places an order.
- Users can trace every key dashboard number to its source and period within two interactions.
- All critical paths work with keyboard and screen reader.
- All chart insights have equivalent text/table access.
- Protected reserve and other active constraints appear in onboarding, dashboard, and scenario review.
- Agent stage and evidence telemetry is understandable without exposing hidden reasoning.
- Error recovery preserves prior approved work.

## 16. Design deliverables

1. Content-tested low-fidelity flows for both investor segments.
2. Responsive Figma component library with tokens and accessibility annotations.
3. High-fidelity prototypes for upload/reconciliation, dashboard, chat, scenario, and weekly review.
4. Component-state matrix and empty/error copy.
5. WCAG checklist and screen-reader test scripts.
6. Analytics event specification.
7. Usability-test plan with novice, experienced, HNI/PMS, and adviser cohorts.
