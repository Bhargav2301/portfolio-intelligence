# Security Policy

## Sensitive data

Do not submit credentials, access tokens, portfolio exports, tax documents, client data,
or licensed market-data payloads in issues or pull requests.

## Reporting

Report suspected vulnerabilities privately to the repository owner. Do not open a public
issue containing exploit details or personal financial data.

## Design controls

- Secrets are loaded from the environment or a production secret manager.
- Broker connectors must use least-privilege, read-only scopes by default.
- Tenant boundaries are enforced at the API and database layers.
- Evidence documents are treated as untrusted input and cannot issue tool instructions.
- Ledger corrections are append-only reversals with complete audit history.
- Recommendation outputs must pass evidence, freshness, and suitability policy gates.

