# TradingAgents integration boundary

The portfolio research graph is adapted from TauricResearch/TradingAgents commit
`a33fd4c0f134485a43553a2c23a63cb14adbd88f` (Apache-2.0).

## Reused architecture

- Separate market, fundamentals, news, and sentiment analyst reports.
- A bounded bull/bear research comparison.
- Aggressive, neutral, and conservative risk perspectives.
- A final policy-controlled proposal for human review.

## Deliberate changes

- TradingAgents is an isolated research pattern, not the portfolio system of record.
- The upstream trader node is replaced by a typed, non-executable scenario proposal.
- Every run is tenant- and portfolio-scoped through the Core API.
- The deterministic ledger and monitors supply all portfolio numbers.
- Missing point-in-time evidence remains missing; live social/news sources are not used for historical runs.
- Debate and risk rounds are capped at one in this integration milestone.
- No broker order client, order endpoint, or execution tool is present.

The sibling `TradingAgents` checkout is reference material only. Production builds use the adapted
code under `src/portfolio_agents`, which keeps the service dependency graph small and makes the
safety boundary reviewable.
