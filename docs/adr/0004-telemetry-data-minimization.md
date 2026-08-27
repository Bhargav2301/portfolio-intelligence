# ADR 0004: Metadata-only observability

- Status: Accepted
- Date: 2026-08-27

Application logs and spans are allowlisted metadata, not captured requests. Allowed fields are
service, environment, route template, method/status/duration, generated request and trace IDs, safe
job/run identifiers, safe error codes, model identifier, token counts, and cost. Raw paths are not
logged for unmatched or parameterized resources and untrusted request IDs are replaced.

Documents, rows, holdings, prompts, responses, credentials, account numbers, tokens, order
payloads, and hidden reasoning are prohibited. OpenTelemetry uses a manual span with route-template
attributes instead of automatic HTTP capture. Tests seed sensitive path, header, and body values
and assert that none reach logs. WAF sampled request bodies are disabled.
