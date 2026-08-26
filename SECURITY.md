# Security policy

Portfolio Intelligence handles financial records and must fail closed.

## Reporting a vulnerability

Do not open a public issue containing:

- Credentials, tokens, or private keys.
- Portfolio or identity data.
- Uploaded statements or screenshots containing account details.
- A working exploit.

Use GitHub private vulnerability reporting when enabled, or contact the repository owner through a private channel.

Include the affected commit, component, reproduction steps using synthetic data, impact, and any safe mitigation.

## Supported version

Only the latest commit on main is supported during the initial build.

## Non-negotiable controls

- No order execution.
- No browser-held broker or model credentials.
- No unscanned production uploads.
- No cross-tenant access.
- No AI-generated portfolio arithmetic.
- No real secrets committed to Git.

