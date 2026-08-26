# PI TradingAgents runtime

This service is the process boundary between Portfolio Intelligence (PI) and
[`TauricResearch/TradingAgents`](https://github.com/TauricResearch/TradingAgents).
It never owns the portfolio ledger and it never places orders.

PI orchestration is an explicit LangGraph workflow:

`select_symbol → TradingAgents analysis → deterministic PI policy review → next symbol/end`

Future agentic PI capabilities must extend this graph or a versioned subgraph.
Financial calculations, ledger writes, authentication, and hard policy checks
remain deterministic services outside model-controlled nodes.

## Local test

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export PI_INTERNAL_API_TOKEN='replace-with-a-long-random-secret'
export OPENAI_API_KEY='...'
uvicorn pi_agent_runtime.app:app --reload
```

The runtime pins TradingAgents to commit
`a33fd4c0f134485a43553a2c23a63cb14adbd88f`. Set provider-specific API keys
required by the selected TradingAgents data and LLM providers.

Every request must include `Authorization: Bearer <PI_INTERNAL_API_TOKEN>` and a
validated `X-PI-Owner-Email` injected by the PI server. For development only,
`PI_ALLOW_INSECURE_LOCAL=true` bypasses this check.

Run exactly one Uvicorn worker per container. TradingAgents sets global runtime
configuration, so horizontal scale must use separate containers/processes rather
than concurrent graphs with different configuration in one process.

## Legacy portfolio normalization

The supplied legacy XLS format is normalized outside LLM nodes. This is a
deterministic LangGraph boundary service: it classifies rows, preserves tax lots,
requires confirmed instrument mappings, reconciles totals, and emits a
`pi-portfolio-import/v1` JSON document that the Sites onboarding screen can review
and commit.

```bash
pi-normalize-portfolio Qber-Aug2026.xls --portfolio-name "D1 Portfolio" > Qber-Aug2026.normalized.json
```

No raw workbook or PDF is written to D1. The web application stores only the
normalized rows, source SHA-256, and import audit metadata. PDFs remain evidence
candidates until private object storage and owner-scoped document review are
enabled.
