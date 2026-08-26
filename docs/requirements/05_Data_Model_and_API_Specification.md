# Portfolio Intelligence — Data Model and API Specification

Version: 1.0  
Date: 26 August 2026  
Status: Contract baseline  
Protocol: REST/JSON plus server-sent events  
Primary database: PostgreSQL

Related architecture: [Technical Design and System Architecture](03_Technical_Design_and_System_Architecture.md)

## 1. Design rules

1. PostgreSQL is the authoritative production database.
2. Every tenant-owned table includes tenant_id and row-level security.
3. Identity comes from the authenticated context, not a request-body owner field.
4. Ledger history is append-only; corrections reverse and replace.
5. Money, price, quantity, rate, and percentage use fixed-precision NUMERIC, not floating point.
6. Dates and timestamps are separate: trade/effective date, source publication time, as-of market time, and recorded-at time.
7. Raw uploaded data, normalized candidates, approved ledger, evidence, and AI interpretation remain distinct.
8. Every derived metric stores input and methodology versions.
9. Every agent output stores graph, prompt, model, tool, policy, evidence, and as-of versions.
10. Client-visible identifiers use UUIDv7 or equally sortable opaque IDs.
11. Personally identifiable data is classified and minimized.
12. Deletion and retention rules apply to raw, derived, vector, log, backup, and evaluation copies.

## 2. Domain relationships

### 2.1 Portfolio system of record

~~~mermaid
erDiagram
    TENANT ||--o{ MEMBERSHIP : has
    USER ||--o{ MEMBERSHIP : joins
    TENANT ||--o{ PORTFOLIO : owns
    PORTFOLIO ||--o{ ACCOUNT : contains
    PORTFOLIO ||--o{ TRANSACTION : records
    INSTRUMENT ||--o{ TRANSACTION : identifies
    IMPORT_BATCH ||--o{ TRANSACTION : publishes
    PORTFOLIO ||--o{ ANALYTICS_SNAPSHOT : derives
~~~

### 2.2 Evidence and agent system

~~~mermaid
erDiagram
    DOCUMENT ||--o{ EVIDENCE_ITEM : yields
    PORTFOLIO ||--o{ CHAT_THREAD : scopes
    CHAT_THREAD ||--o{ AGENT_RUN : contains
    AGENT_RUN ||--o{ AGENT_STEP : executes
    AGENT_RUN ||--o{ RECOMMENDATION : proposes
    RECOMMENDATION }o--o{ EVIDENCE_ITEM : cites
    RECOMMENDATION ||--o{ DECISION : receives
    RECOMMENDATION ||--o{ OUTCOME : evaluates
~~~

## 3. Entity catalogue

### 3.1 Identity, tenancy, consent, and suitability

| Entity | Key fields | Constraints and notes |
|---|---|---|
| users | id, identity_provider_subject, email_ciphertext, status, locale, timezone, created_at | Provider subject unique; email encrypted or tokenized |
| tenants | id, name, type, base_currency, region, status, created_at | Type: individual, household, adviser |
| memberships | id, tenant_id, user_id, role, status, invited_by, created_at | Unique tenant_id plus user_id; roles are owner, editor, viewer, adviser, compliance |
| sessions | id, user_id, refresh_family_hash, device_id, expires_at, revoked_at | Server-side; no raw refresh token |
| consents | id, tenant_id, user_id, purpose, document_version, granted_at, withdrawn_at, source | Append-only consent history |
| suitability_profiles | id, tenant_id, user_id, version, status, horizon_months, loss_capacity_band, risk_tolerance_band, experience_band, liquidity_need, effective_at | Immutable versions; status incomplete, valid, stale, superseded |
| goals | id, tenant_id, portfolio_id nullable, name, target_amount, target_currency, target_date, contribution_amount, contribution_frequency, priority | Goal scenario input, not guaranteed outcome |
| portfolio_rules | id, tenant_id, portfolio_id, version, rule_type, parameters_json, severity, effective_at, superseded_at | Protected cash, no equal weight, max position, exclusion, cadence |

Rule examples for the initial workspace:

- protected_cash: amount ₹25,00,000, currency INR, enforcement hard.
- weighting_policy: equal_weighting_allowed false.
- review_cadence: weekly.

### 3.2 Portfolio and ledger

| Entity | Key fields | Constraints and notes |
|---|---|---|
| portfolios | id, tenant_id, owner_user_id, name, type, base_currency, benchmark_id, valuation_timezone, status, version, created_at | Type self_managed, pms, model, interest |
| accounts | id, tenant_id, portfolio_id, provider, account_type, masked_reference, currency, status | Provider account identifier encrypted/tokenized |
| instruments | id, canonical_type, isin, exchange, exchange_symbol, vendor_symbols_json, name, currency, active_from, active_to | Unique ISIN/exchange where available |
| instrument_aliases | id, instrument_id, provider, alias, valid_from, valid_to, verification_status | .NS/.BO mapping stored explicitly |
| transactions | id, tenant_id, portfolio_id, account_id, instrument_id nullable, event_type, trade_date, settlement_date, quantity, price, gross_amount, currency, source_reference, import_batch_id, reversal_of_id, recorded_at | Append-only; unique source reference per authority; decimal values |
| transaction_lots | id, tenant_id, transaction_id, source_lot_reference, open_quantity, source_cost, acquisition_date | Preserves broker tax-lot input; V1 does not promise tax calculation |
| cash_events | id, tenant_id, portfolio_id, account_id, event_type, effective_date, amount, currency, import_batch_id, reversal_of_id | Deposit, withdrawal, dividend, fee_unallocated, cash_adjustment |
| holding_snapshots | id, tenant_id, portfolio_id, account_id, instrument_id, as_of, quantity, average_price, source_document_id, reconciliation_status | Snapshot evidence; not silently converted to transactions |
| position_snapshots | id, tenant_id, portfolio_id, instrument_id, as_of, ledger_version, quantity, cost_basis, market_price, market_value, currency | Derived and reproducible |
| cash_snapshots | id, tenant_id, portfolio_id, as_of, ledger_version, available_cash, protected_cash, currency | Protected cash separated |
| benchmarks | id, code, name, provider, currency, methodology_url, active | Global reference table |
| market_prices | instrument_id, provider, price_type, as_of, known_at, price, currency, quality | Time-series partition candidate; unique instrument/provider/type/as_of |
| fx_rates | base_currency, quote_currency, as_of, known_at, rate, provider | Fixed precision and point-in-time metadata |
| corporate_actions | id, instrument_id, action_type, ex_date, effective_date, terms_json, source, status | Only certified action types affect ledger |

Ledger event_type includes:

- buy, sell, transfer_in, transfer_out.
- dividend_cash, deposit, withdrawal.
- split, bonus, merger_exchange, demerger.
- fee_unallocated.
- manual_adjustment.
- reversal.

### 3.3 File ingestion and reconciliation

| Entity | Key fields | Constraints and notes |
|---|---|---|
| uploads | id, tenant_id, created_by, object_key, original_name_ciphertext, declared_type, detected_type, size_bytes, sha256, state, created_at | Object key random; raw object immutable |
| documents | id, tenant_id, portfolio_id nullable, upload_id, source_role, document_family, authority_level, period_start, period_end, publication_at, known_at, status | Source role ledger, snapshot, research, unknown |
| document_pages | id, tenant_id, document_id, page_number, text_object_key, render_object_key, text_coverage, ocr_status, confidence | Unique document/page |
| extraction_runs | id, tenant_id, document_id, parser_name, parser_version, template_id, state, started_at, completed_at, metrics_json | Multiple runs retained; one selected |
| extracted_records | id, tenant_id, extraction_run_id, record_type, source_locator_json, raw_json, normalized_json, field_confidence_json, status | Candidate only |
| mapping_rules | id, tenant_id, provider, document_family, source_field, target_field, transform_version, status | Tenant rule can override general template with audit |
| reconciliation_cases | id, tenant_id, portfolio_id, type, severity, state, affected_record_ids, residual_amount, assigned_to, resolution_json | Conflict, duplicate, balance, identifier, coverage |
| import_batches | id, tenant_id, portfolio_id, source_authority, extraction_run_id, approved_by, approved_at, content_hash, ledger_version, state | Idempotent content_hash plus portfolio |
| import_batch_records | import_batch_id, extracted_record_id, disposition, normalized_hash | Approved, excluded, duplicate |

State machines:

uploads:

initiated → uploading → uploaded → scanning → accepted → parsing → review or failed

documents:

quarantined → parsed → review_required → approved → published or rejected

import_batches:

draft → validating → approved → publishing → published; or failed

No state may skip scanning or validation.

### 3.4 Analytics and scenarios

| Entity | Key fields | Constraints and notes |
|---|---|---|
| analytics_snapshots | id, tenant_id, portfolio_id, as_of, known_at, ledger_version, market_data_version, methodology_version, benchmark_id, input_hash, quality_state | Unique portfolio/as_of/versions |
| metric_values | id, tenant_id, analytics_snapshot_id, metric_code, dimension_type, dimension_id, period_start, period_end, value, unit, status, details_json | Metric dictionary controls definitions |
| scenario_runs | id, tenant_id, portfolio_id, created_by, base_snapshot_id, name, status, assumption_set_json, engine_version, created_at | Immutable once completed |
| scenario_actions | id, tenant_id, scenario_run_id, instrument_id nullable, action_type, quantity nullable, amount nullable, target_range_json, rationale_ref | Proposal only |
| scenario_results | id, tenant_id, scenario_run_id, case_type, metrics_json, constraint_results_json, warnings_json | Baseline, upside, downside, stress |
| review_triggers | id, tenant_id, portfolio_id, trigger_type, rule_version_id, observed_at, severity, metric_snapshot_id, state | Deduplicated by trigger window |
| market_state_snapshots | id, tenant_id, scope_code, as_of, known_at, methodology_version, features_json, regime_label, stability_score, coverage, input_hash | Deterministic point-in-time context; label is descriptive, not a forecast |

Metric codes include:

- current_value, net_invested_capital, cash.
- unrealized_pnl, time_weighted_return, money_weighted_return.
- benchmark_return, active_return, contribution.
- volatility, downside_deviation, max_drawdown, tracking_error.
- position_weight, sector_weight, top_n_concentration.
- data_coverage, price_freshness, goal_required_cagr.

### 3.5 Evidence, chat, agents, and outcomes

| Entity | Key fields | Constraints and notes |
|---|---|---|
| evidence_items | id, tenant_id, document_id nullable, source_uri_ciphertext nullable, source_type, title, publisher, published_at, retrieved_at, known_at, content_hash, locator_json, text_object_key, quality, cutoff_eligible | Tenant scope required even for cached licensed data |
| evidence_links | id, tenant_id, from_type, from_id, evidence_item_id, relation, claim_key | Supports, contradicts, contextualizes |
| chat_threads | id, tenant_id, portfolio_id, created_by, title, mode, created_at, archived_at | Thread ID never authorizes access |
| chat_messages | id, tenant_id, thread_id, role, content_object_key, created_at, agent_run_id nullable, redaction_status | Content separated from operational logs |
| agent_runs | id, tenant_id, portfolio_id, thread_id, initiated_by, request_id, intent, as_of, known_at, product_mode, graph_version, prompt_bundle_version, model_route, policy_version_id, state, started_at, completed_at, token_usage_json, cost_amount | Durable run root |
| agent_steps | id, tenant_id, agent_run_id, node_name, attempt, state, input_hash, output_hash, started_at, completed_at, public_summary, error_code | No hidden reasoning |
| tool_calls | id, tenant_id, agent_step_id, tool_name, tool_version, capability_scope_hash, request_hash, response_hash, source_cutoff, state, latency_ms, cost_amount | Sensitive payloads stored separately or omitted |
| recommendations | id, tenant_id, portfolio_id, agent_run_id, type, status, summary, rationale_object_key, confidence_band, valid_until, policy_decision_id, created_at | Proposal, not order |
| recommendation_items | id, tenant_id, recommendation_id, instrument_id nullable, direction, target_range_json, condition_json, invalidation_json | Direction increase, reduce, hold, monitor, research |
| recommendation_evidence | recommendation_id, evidence_item_id, claim_key, relation | Many-to-many |
| policy_decisions | id, tenant_id, agent_run_id, decision, reasons_json, policy_version, reviewed_by nullable, created_at | Allow, revise, suppress, human_review |
| decisions | id, tenant_id, recommendation_id nullable, scenario_run_id nullable, user_id, decision_type, note_object_key, decided_at | Accept, reject, no_action, snooze, revise |
| outcomes | id, tenant_id, recommendation_id, evaluation_horizon, due_at, evaluated_at, portfolio_snapshot_id, benchmark_id, metrics_json, evaluator_version | Observational evaluation; no causal claim |
| user_feedback | id, tenant_id, user_id, message_id nullable, recommendation_id nullable, rating, reason_codes, comment_object_key, created_at | Separate subjective signal |
| lesson_records | id, tenant_id, portfolio_id, source_outcome_id, summary_object_key, applicability_json, status, approved_by, version | Candidate, approved, rejected, superseded |
| prompt_versions | id, name, version, content_hash, approval_state, effective_at | Actual prompt stored securely outside logs |
| evaluation_runs | id, candidate_bundle, dataset_version, result_json, approved_by, created_at | Offline promotion gate |

### 3.6 Connections, operations, and audit

| Entity | Key fields | Constraints and notes |
|---|---|---|
| broker_connections | id, tenant_id, portfolio_id, provider, encrypted_grant_ref, scopes, status, expires_at, last_sync_at | Scopes checked against read-only allowlist |
| broker_sync_runs | id, tenant_id, connection_id, cursor, state, started_at, completed_at, result_json | Idempotent by provider cursor |
| jobs | id, tenant_id, type, resource_id, state, priority, idempotency_key, attempts, available_at, lease_until, result_ref | Durable user-visible job |
| outbox_events | id, tenant_id, aggregate_type, aggregate_id, event_type, payload_json, created_at, published_at | Written in same transaction as domain mutation |
| notification_preferences | id, tenant_id, user_id, channel, event_type, enabled, quiet_hours_json | Weekly review opt-in/out |
| notifications | id, tenant_id, user_id, event_type, resource_ref, state, dedupe_key, sent_at | No sensitive details in email subject |
| audit_events | id, tenant_id, actor_type, actor_id, action, resource_type, resource_id, purpose, before_hash, after_hash, trace_id, occurred_at, metadata_json | Append-only, restricted, integrity monitored |
| support_access_grants | id, tenant_id, operator_id, case_id, scope_json, approved_by, starts_at, expires_at, revoked_at | Just-in-time and purpose-bound |
| deletion_requests | id, tenant_id, requested_by, scope, state, legal_hold_reason nullable, created_at, completed_at | Tracks downstream deletion |

## 4. Data types and invariants

### 4.1 Precision

Recommended types:

- Monetary amount: NUMERIC(28, 8).
- Quantity: NUMERIC(28, 10).
- Price: NUMERIC(28, 10).
- Ratio/rate: NUMERIC(20, 12).
- Currency: CHAR(3), ISO 4217.
- Business date: DATE.
- Instant: TIMESTAMPTZ, stored in UTC.

API transmits decimals as strings to prevent JavaScript precision loss.

### 4.2 Required invariants

- quantity cannot be zero for buy/sell events.
- price and gross amount signs follow event-type policy.
- reversal_of_id references an event in the same tenant and portfolio.
- protected_cash cannot exceed total modeled cash without an explicit warning state.
- recommendation cannot be released without a policy_decision.
- every material recommendation claim must have evidence or analytics linkage.
- historical agent run may use only evidence with known_at on or before run cutoff.
- published import content hash is unique per portfolio and source authority.
- source research cannot be assigned ledger authority.

### 4.3 Indexes

Minimum:

- Every tenant table: index tenant_id plus primary query dimension.
- transactions: tenant_id, portfolio_id, trade_date, id.
- transactions: tenant_id, portfolio_id, source_reference where not null.
- position_snapshots: tenant_id, portfolio_id, as_of descending.
- evidence_items: tenant_id, published_at, known_at; vector index with mandatory tenant filter.
- agent_runs: tenant_id, portfolio_id, started_at descending.
- jobs: state, available_at, priority.
- audit_events: tenant_id, occurred_at descending.
- market_prices: instrument_id, as_of descending, provider.

## 5. Row-level security and authorization

### 5.1 Database policy pattern

For each tenant table:

- Enable and force row-level security.
- Policy reads current tenant from a transaction-local database setting established by the API.
- USING limits existing-row visibility.
- WITH CHECK limits inserted/updated tenant_id.
- Application role does not own the table and cannot bypass RLS.
- Administrative migrations use a separate non-runtime role.

PostgreSQL requires row security to be enabled before policies apply; policy expressions control existing and new rows. See [CREATE POLICY](https://www.postgresql.org/docs/current/sql-createpolicy.html).

### 5.2 API authorization

Decision inputs:

- Authenticated user.
- Selected workspace from X-Workspace-Id.
- Verified active membership and role.
- Resource tenant and portfolio assignment.
- Requested action.
- Product mode and compliance state.
- Step-up authentication when required.

The API returns 404 for inaccessible opaque resources where existence disclosure is unnecessary.

## 6. Authentication schema

### 6.1 Browser flow

1. Browser starts OIDC authorization code flow with PKCE through the BFF.
2. BFF exchanges code and stores provider tokens server-side.
3. Browser receives an HttpOnly, Secure, SameSite session cookie.
4. BFF creates a short-lived internal access token for the Core API with audience, subject, workspace, membership version, session ID, issued-at, and expiry.
5. Core API validates issuer, audience, signature, time, session revocation, workspace membership, and resource authorization.

### 6.2 Service flow

- Workload identity or OAuth client credentials.
- mTLS inside the private service network where supported.
- Audience-restricted tokens lasting at most 10 minutes.
- Service name, deployment, and job/run context in claims.
- Agent tools additionally receive a signed capability with exact actions and resource IDs.

### 6.3 Security events

Session revocation, password/passkey change, MFA reset, membership change, export, deletion, broker link, and support elevation produce audit events and user notifications.

## 7. API conventions

Base path: /v1  
Media type: application/json  
Timestamps: RFC 3339 UTC  
Decimals: JSON strings  
Identifiers: opaque UUID-like strings  
Workspace selector: X-Workspace-Id  
Trace response header: Trace-Id  
Idempotency request header: Idempotency-Key  
Concurrency: If-Match with resource version or ETag

### 7.1 Response envelope

Single resource:

~~~json
{
  "data": {
    "id": "port_01...",
    "type": "portfolio",
    "attributes": {}
  },
  "meta": {
    "trace_id": "tr_01..."
  }
}
~~~

List:

~~~json
{
  "data": [],
  "page": {
    "next_cursor": "opaque-or-null",
    "has_more": false
  },
  "meta": {
    "trace_id": "tr_01..."
  }
}
~~~

Error:

~~~json
{
  "error": {
    "code": "RECONCILIATION_REQUIRED",
    "message": "Resolve 12 material records before publishing.",
    "field_issues": [],
    "retryable": false,
    "trace_id": "tr_01..."
  }
}
~~~

### 7.2 Error codes

- AUTHENTICATION_REQUIRED
- ACCESS_DENIED
- RESOURCE_NOT_FOUND
- VALIDATION_FAILED
- VERSION_CONFLICT
- IDEMPOTENCY_CONFLICT
- FILE_TYPE_UNSUPPORTED
- FILE_SECURITY_REJECTED
- FILE_PASSWORD_REQUIRED
- EXTRACTION_FAILED
- RECONCILIATION_REQUIRED
- DATA_STALE
- SUITABILITY_REQUIRED
- POLICY_BLOCKED
- RESEARCH_CUTOFF_UNAVAILABLE
- RATE_LIMITED
- PROVIDER_UNAVAILABLE
- INTERNAL_ERROR

## 8. Portfolio APIs

### 8.1 Create portfolio

POST /v1/portfolios

Request:

~~~json
{
  "name": "Core Equity",
  "portfolio_type": "self_managed",
  "base_currency": "INR",
  "benchmark_code": "NIFTY_500_TRI",
  "valuation_timezone": "Asia/Kolkata",
  "review_cadence": "weekly"
}
~~~

Response: 201 with portfolio, version, default data-quality state, and links.

Acceptance:

- benchmark must exist.
- type must be allowed.
- tenant comes from auth context.
- creation writes audit and default rule versions.

### 8.2 Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /v1/portfolios | List authorized portfolios |
| POST | /v1/portfolios | Create portfolio |
| GET | /v1/portfolios/{portfolio_id} | Get metadata and quality state |
| PATCH | /v1/portfolios/{portfolio_id} | Update with If-Match |
| GET | /v1/portfolios/{portfolio_id}/holdings | Versioned position view |
| GET | /v1/portfolios/{portfolio_id}/transactions | Cursor-paginated ledger |
| GET | /v1/portfolios/{portfolio_id}/cash | Available and protected cash |
| GET | /v1/portfolios/{portfolio_id}/performance | Return and benchmark metrics |
| GET | /v1/portfolios/{portfolio_id}/risk | Risk metrics and quality |
| GET | /v1/portfolios/{portfolio_id}/snapshots | Historical snapshots |
| GET | /v1/portfolios/{portfolio_id}/rules | Effective rules |
| POST | /v1/portfolios/{portfolio_id}/rules | Create a versioned rule |

Holding response excerpt:

~~~json
{
  "data": {
    "portfolio_id": "port_01...",
    "as_of": "2026-08-26T10:00:00Z",
    "ledger_version": 42,
    "quality_state": "trusted",
    "items": [
      {
        "instrument_id": "ins_01...",
        "symbol": "EXAMPLE.NS",
        "quantity": "125.0000000000",
        "market_price": "742.3500000000",
        "market_value": "92793.75000000",
        "weight": "0.037500000000",
        "currency": "INR",
        "source_lineage_url": "/v1/holdings/..."
      }
    ]
  }
}
~~~

## 9. Upload and ingestion APIs

### 9.1 Initiate upload

POST /v1/uploads

Request:

~~~json
{
  "portfolio_id": "port_01...",
  "original_name": "broker-ledger.xls",
  "size_bytes": 843221,
  "sha256": "hex",
  "declared_type": "application/vnd.ms-excel",
  "source_role": "brokerage_ledger"
}
~~~

Response: 201 with upload_id, short-lived upload_url, required headers, expires_at, and limits.

### 9.2 Complete upload

POST /v1/uploads/{upload_id}/complete

- Requires Idempotency-Key.
- Server verifies object size/checksum.
- Returns 202 with job URL.

### 9.3 Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /v1/uploads/{upload_id} | Upload and scan status |
| POST | /v1/uploads/{upload_id}/password | One-time encrypted job input; never persisted |
| GET | /v1/documents/{document_id} | Document metadata and role |
| GET | /v1/documents/{document_id}/extractions | Extraction runs and quality |
| GET | /v1/extractions/{run_id}/records | Review candidates |
| PATCH | /v1/extractions/{run_id}/records/{record_id} | Correct mapping/value with If-Match |
| POST | /v1/reconciliations/{case_id}/resolve | Resolve conflict with reason |
| POST | /v1/extractions/{run_id}/validate | Re-run validation |
| POST | /v1/extractions/{run_id}/publish | Approve and publish batch |
| GET | /v1/import-batches/{batch_id} | Publication and lineage |

Publish request:

~~~json
{
  "portfolio_id": "port_01...",
  "accepted_record_ids": ["rec_01...", "rec_02..."],
  "excluded": [
    {
      "record_id": "rec_03...",
      "reason": "duplicate"
    }
  ],
  "acknowledgement": {
    "mapping_reviewed": true,
    "unresolved_exclusions_understood": true
  }
}
~~~

Publish response: 202 job. Final job result links to import batch, new ledger version, analytics recompute job, and audit event.

## 10. Analytics and scenario APIs

| Method | Path | Purpose |
|---|---|---|
| GET | /v1/portfolios/{id}/analytics/latest | Latest full snapshot |
| GET | /v1/analytics/{snapshot_id}/metrics | Filtered metric values |
| GET | /v1/market-state | Point-in-time features, regime context, and coverage |
| POST | /v1/portfolios/{id}/analytics/recompute | Authorized recompute |
| POST | /v1/portfolios/{id}/scenarios | Create scenario |
| GET | /v1/scenarios/{scenario_id} | Scenario state/results |
| POST | /v1/scenarios/{scenario_id}/compare | Compare with other scenarios |
| POST | /v1/scenarios/{scenario_id}/decisions | Save human decision |

Scenario request:

~~~json
{
  "base_snapshot_id": "ana_01...",
  "name": "Reduce concentration without using reserve",
  "actions": [
    {
      "action_type": "target_range",
      "instrument_id": "ins_01...",
      "target_weight_min": "0.060000000000",
      "target_weight_max": "0.080000000000"
    }
  ],
  "assumptions": {
    "transaction_cost_bps": "20.000000000000",
    "taxes_included": false
  }
}
~~~

The API rejects any scenario that attempts to consume protected cash without an explicit, separately authorized rule change.

## 11. Chat and agent APIs

### 11.1 Thread and message

| Method | Path | Purpose |
|---|---|---|
| POST | /v1/chat/threads | Create portfolio-scoped thread |
| GET | /v1/chat/threads | List authorized threads |
| GET | /v1/chat/threads/{thread_id} | Thread metadata |
| GET | /v1/chat/threads/{thread_id}/messages | Cursor-paginated messages |
| POST | /v1/chat/threads/{thread_id}/messages | Submit question and create run |
| GET | /v1/agent-runs/{run_id} | Run status and public telemetry |
| GET | /v1/agent-runs/{run_id}/events | SSE progress stream |
| POST | /v1/agent-runs/{run_id}/resume | Resume human interrupt |
| POST | /v1/agent-runs/{run_id}/cancel | Cancel within policy |

Message request:

~~~json
{
  "content": "What changed in my portfolio risk this week?",
  "as_of": "2026-08-26T10:00:00Z",
  "research_mode": "current_allowlisted_sources",
  "response_depth": "standard"
}
~~~

Response: 202

~~~json
{
  "data": {
    "message_id": "msg_01...",
    "agent_run_id": "run_01...",
    "state": "queued",
    "events_url": "/v1/agent-runs/run_01.../events"
  },
  "meta": {
    "trace_id": "tr_01..."
  }
}
~~~

### 11.2 SSE events

- run.queued
- node.started
- node.completed
- evidence.retrieved
- policy.checked
- human_input.required
- response.delta
- run.completed
- run.failed

Public node events contain stage name, timestamp, status, evidence count, and safe summary. They exclude prompts, secrets, hidden reasoning, and raw tool payloads.

### 11.3 Human interrupt resume

POST /v1/agent-runs/{run_id}/resume

~~~json
{
  "interrupt_id": "int_01...",
  "action": "confirm_instrument",
  "payload": {
    "instrument_id": "ins_01...",
    "exchange_symbol": "EXAMPLE.NS"
  }
}
~~~

The server verifies that the interrupt belongs to the current run, tenant, portfolio, user capability, and graph checkpoint.

## 12. Recommendations, evidence, feedback, and outcomes

| Method | Path | Purpose |
|---|---|---|
| GET | /v1/recommendations | Filtered authorized list |
| GET | /v1/recommendations/{id} | Proposal, policy, evidence, validity |
| POST | /v1/recommendations/{id}/decisions | Accept, reject, no-action, snooze, revise |
| POST | /v1/recommendations/{id}/feedback | Usefulness feedback |
| GET | /v1/recommendations/{id}/outcomes | Later evaluation |
| GET | /v1/evidence/{id} | Evidence metadata and authorized excerpt |
| GET | /v1/evidence | Search within authorized tenant |

Recommendation response includes:

- product_mode.
- valid_until and data_cutoff.
- summary and conditional rationale.
- analytics references.
- evidence references and freshness.
- candidate actions/ranges.
- assumptions and invalidation conditions.
- constraint and suitability result.
- no-order-execution statement.

## 13. Weekly review APIs

| Method | Path | Purpose |
|---|---|---|
| GET | /v1/reviews/current | Current workspace review summary |
| GET | /v1/portfolios/{id}/review-triggers | Portfolio triggers |
| POST | /v1/reviews/{id}/items/{item_id}/decision | Record action/no-action/snooze |
| POST | /v1/reviews/{id}/complete | Complete review |
| PATCH | /v1/notification-preferences | Change cadence/channel |

Weekly review generation is asynchronous and idempotent by portfolio, rule version, and review window.

## 14. Broker connection APIs

| Method | Path | Purpose |
|---|---|---|
| POST | /v1/connections/upstox/authorize | Create server-side OAuth state and return authorization URL |
| GET | /v1/connections/upstox/callback | Server callback; exchanges code |
| GET | /v1/connections | List masked connection status |
| POST | /v1/connections/{id}/sync | Start read-only sync |
| DELETE | /v1/connections/{id} | Revoke and delete grant subject to audit |

Requirements:

- Authorization state binds session, tenant, portfolio, nonce, and expiry.
- Callback validates state and exact redirect URI.
- Stored scopes must match the read-only allowlist.
- Order endpoints do not exist in the connector interface.
- Browser never sees access or refresh tokens.
- Sync data remains candidate until reconciliation policy approves publication.

## 15. Privacy and user-right APIs

| Method | Path | Purpose |
|---|---|---|
| GET | /v1/privacy/consents | Current and historical consent |
| POST | /v1/privacy/consents | Grant a purpose/version |
| POST | /v1/privacy/consents/{id}/withdraw | Withdraw future processing where applicable |
| POST | /v1/privacy/exports | Start secure export |
| GET | /v1/privacy/exports/{job_id} | Status and short-lived download |
| POST | /v1/privacy/deletions | Request deletion |
| GET | /v1/privacy/deletions/{id} | Deletion status and legal-hold explanation |

Exports require reauthentication and encrypted, expiring delivery. They include source/ledger/decision lineage without internal secrets.

## 16. Jobs and operations

GET /v1/jobs/{job_id} returns:

~~~json
{
  "data": {
    "id": "job_01...",
    "type": "document_extraction",
    "state": "running",
    "progress": {
      "completed_units": 17,
      "total_units": 50,
      "label": "Processing pages"
    },
    "retryable": false,
    "created_at": "2026-08-26T09:00:00Z",
    "updated_at": "2026-08-26T09:00:08Z"
  }
}
~~~

Operations endpoints are separately routed and authorized:

- GET /v1/ops/reconciliation-cases
- GET /v1/ops/failed-jobs
- POST /v1/ops/jobs/{id}/retry
- POST /v1/ops/support-grants
- POST /v1/ops/policy-decisions/{id}/review

Every operation requires reason and produces audit events.

## 17. Idempotency and concurrency

### Idempotency

- Client provides a random key for each logical mutation.
- Server stores key, authenticated principal, endpoint, request hash, status, and response for at least 24 hours.
- Reuse with identical request returns original response.
- Reuse with different request returns IDEMPOTENCY_CONFLICT.
- Upload content hash and provider cursors add domain-level deduplication.

### Optimistic concurrency

- Mutable user resources return ETag or version.
- PATCH and high-impact POST operations require If-Match.
- Stale write returns 409 VERSION_CONFLICT with current version.
- Ledger events are not updated; corrections use reversal.

## 18. API rate and cost controls

Example starting limits:

| Operation | Limit |
|---|---:|
| Standard reads | 300 requests per 5 minutes per user |
| Upload initiation | 20 per hour per tenant |
| Published imports | 20 per day per portfolio |
| Standard chat | Plan-specific; burst 5 per minute |
| Deep research run | Plan-specific; one concurrent per portfolio |
| Export | 3 per day per tenant |
| Login/verification | Risk-based and IP/device limited |

Return Retry-After on 429. Tenant budgets apply to model and external-data calls independent of HTTP limits.

## 19. Event contracts

Event envelope:

~~~json
{
  "event_id": "evt_01...",
  "event_type": "portfolio.snapshot_ready",
  "event_version": 1,
  "occurred_at": "2026-08-26T09:05:00Z",
  "tenant_id": "ten_01...",
  "aggregate": {
    "type": "portfolio",
    "id": "port_01...",
    "version": 42
  },
  "trace_id": "tr_01...",
  "payload": {}
}
~~~

Rules:

- Consumers are idempotent by event_id.
- Payloads contain references and minimal safe data, not documents or chat.
- Schema registry compatibility is backward-first.
- Dead-letter messages retain tenant and trace context without secrets.
- Authorization is rechecked before a consumer reads referenced data.

## 20. Retention and deletion

[Likely] Exact retention periods require legal approval. Proposed defaults:

| Data class | Proposed active retention | Deletion treatment |
|---|---|---|
| Quarantined rejected upload | 7 days | Automatic hard deletion |
| Approved source document | While account active plus required record period | Crypto-delete plus lifecycle |
| Ledger and advice records | Regulatory/business period defined by mode | Legal hold may override user deletion |
| Operational logs | 30–90 days | Redacted and lifecycle deleted |
| Audit events | 7 years where justified | Restricted, integrity protected |
| Agent checkpoints | 30 days after completion unless linked to decision | Delete content, retain minimal audit hash |
| Feedback/evaluation content | Until consent withdrawn or dataset expiry | Remove raw/embedding/lesson copies |
| Backups | 35 days rolling | Expire automatically; no selective restore into production |

The deletion service maintains a dependency graph and completion receipts.

## 21. Schema migration and data quality

- All migrations are reviewed, forward-compatible, and tested on production-scale copies with synthetic data.
- Expand/migrate/contract pattern for zero-downtime changes.
- Every derived table can be rebuilt from authoritative records.
- Daily invariant jobs detect cross-tenant references, orphaned evidence, unresolved publication, precision drift, and stale prices.
- Reconciliation metrics are segmented by parser/template version.
- Data repair uses versioned scripts, dry-run report, approval, and audit.

## 22. Contract acceptance criteria

- OpenAPI document validates and generates typed frontend and test clients.
- Every endpoint has positive, validation, authorization, cross-tenant, idempotency, and concurrency tests.
- All decimal fields are strings on the wire and fixed precision in storage.
- Every material metric resolves to analytics snapshot and source lineage.
- Every recommendation resolves to policy decision and evidence/metric claims.
- Historical queries enforce known_at cutoff.
- Broker interface exposes no order method.
- Deletion reaches source objects, normalized content, vectors, chat, checkpoints, and lesson records.
- RLS is forced and verified on every tenant table.
