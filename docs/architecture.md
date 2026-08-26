# Architecture

## Goal

Portfolio Intelligence turns portfolio, market, and research facts into reproducible
analytics and evidence-backed explanations. It does not delegate financial truth to an LLM.

## Logical components

1. **Portfolio ledger** records immutable transactions and reversals.
2. **Position engine** folds the ledger into quantities and cost basis.
3. **Analytics engine** values positions using explicitly time-stamped observations.
4. **Evidence ledger** stores canonical sources, hashes, timestamps, and claim relationships.
5. **Signal engine** will generate deterministic or statistically validated factors.
6. **Policy engine** applies freshness, evidence, suitability, and compliance gates.
7. **LLM boundary** translates intent and explains approved structured results.
8. **Audit ledger** records inputs, tool calls, model versions, and policy decisions.

## Data flow

```text
Broker/CSV ----> normalization ----> immutable portfolio ledger
Market feed ---> identity + time ---> price observations
Filings/news --> provenance -------> evidence ledger

portfolio ledger + prices --> analytics --> factors
factors + evidence + user mode --> policy gates --> approved structured result
approved result + cited claims --> LLM explanation --> claim verifier --> user
```

## Invariants

- Ledger events are immutable and idempotent.
- Corrections append reversals; they do not update original events.
- A sale cannot create a negative long-only position.
- Every valuation includes currency, price timestamp, and source.
- Every external factual claim points to an evidence item.
- Evidence integrity is checked using SHA-256.
- Personalized advice is denied unless suitability is complete and the product mode permits it.
- Stale or insufficient evidence yields `insufficient_evidence`.
- The LLM cannot override a policy result.

## Deployment evolution

The first release is a modular monolith with background workers. Logical components become
independent services only when throughput, release cadence, or isolation requirements justify
the operational cost.

PostgreSQL is the transactional source of truth. Object storage holds immutable source
documents. PostgreSQL/pgvector can serve initial semantic retrieval. Redis can provide cache
and job coordination. An event stream is introduced when ingestion volume requires it.

## Threat model highlights

- Prompt injection in filings or uploaded PDFs
- Incorrect ticker-to-instrument resolution
- Stale or delayed licensed data
- Duplicate broker events
- Look-ahead leakage in research and backtests
- Cross-tenant data exposure
- Hallucinated or weakly supported citations
- Recommendation policy drift

Each source record therefore preserves effective time, publication time, retrieval time,
canonical instrument identity, source classification, entitlement, and content hash.

