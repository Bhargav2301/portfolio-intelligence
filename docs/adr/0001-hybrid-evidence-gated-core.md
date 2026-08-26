# ADR 0001: Hybrid evidence-gated core

- Status: Accepted
- Date: 2026-08-13

## Context

The product must combine portfolio tracking, deterministic analytics, research retrieval,
scenario analysis, and conversational interaction. Free-form LLM recommendations are not
reproducible and can misstate calculations, freshness, or source support.

## Decision

Use a hybrid architecture:

- immutable deterministic portfolio ledger;
- deterministic/statistically controlled analytics and signal generation;
- source provenance and claim-level evidence contracts;
- policy gates for freshness, suitability, evidence, and product mode; and
- an LLM restricted to intent parsing and explanation.

The initial deployment is a modular monolith with workers, not a microservice fleet.

## Consequences

Positive:

- Financial results are reproducible.
- Recommendation decisions are auditable across model upgrades.
- Unsupported or stale answers fail closed.
- Components can later be extracted without changing domain contracts.

Negative:

- More up-front domain and provenance engineering is required.
- The chat experience may refuse requests instead of improvising.
- Source licences and jurisdiction policies remain product dependencies.

