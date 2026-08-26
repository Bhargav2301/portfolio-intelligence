# Portfolio Intelligence

Portfolio Intelligence is an evidence-gated investment research and portfolio analytics
platform. Financial calculations and recommendation policies are deterministic. The LLM
layer is restricted to intent interpretation and explanation of already-computed results.

This repository implements **Branch C: Hybrid Deterministic Finance Engine with an
Evidence-Gated LLM**.

## Current vertical slice

- Immutable, idempotent transaction ledger
- Deterministic average-cost position and portfolio analytics
- Reversal-based corrections instead of historical mutation
- Evidence objects with source tier, timestamps, content hashes, and claim linkage
- Recommendation policy gates for freshness, evidence coverage, and personalized advice
- FastAPI adapter for ledger, position, and recommendation-policy endpoints
- PostgreSQL foundation schema
- Unit tests for core financial and evidence invariants
- CI workflow for tests, linting, and type checking

The initial release is decision support, not trade execution. Personalized advice is denied
by default and must be enabled only after jurisdiction-specific compliance controls are in
place.

## Architecture boundary

```text
Client -> API/tool orchestrator -> deterministic portfolio and analytics services
                                    -> evidence retrieval and provenance
                                    -> recommendation policy gates
                                    -> LLM explanation and claim verifier
```

The LLM cannot:

- write ledger entries without a confirmed typed command;
- calculate portfolio values or returns;
- change a recommendation policy result;
- cite a source that is absent from the evidence ledger; or
- place trades.

See [docs/architecture.md](docs/architecture.md) and the first
[architecture decision record](docs/adr/0001-hybrid-evidence-gated-core.md).

## Local development

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
docker compose up -d postgres
uvicorn portfolio_intelligence.api.app:app --reload
```

Run the dependency-free domain test suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

After installing development dependencies:

```bash
pytest
ruff check .
mypy src
```

## API endpoints

- `GET /health`
- `POST /v1/portfolios/{portfolio_id}/transactions`
- `GET /v1/portfolios/{portfolio_id}/positions`
- `POST /v1/recommendations/evaluate`

The current API uses an in-memory adapter to exercise the domain boundary. PostgreSQL
persistence, authentication, tenancy, and migrations are the next implementation milestone.

## Security and compliance

- Never commit broker credentials, portfolio exports, client records, or licensed market data.
- Broker integrations must be read-only by default and use scoped tokens from a secret manager.
- Uploaded and retrieved documents are untrusted content, never executable instructions.
- Every user-visible market fact must carry a source and an `as_of` timestamp.
- A disclaimer does not replace registration, suitability, disclosure, or recordkeeping duties.

This software is under active development and is not investment advice.

