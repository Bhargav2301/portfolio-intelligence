# ADR 0003: Atomic and immutable ledger publication

- Status: Accepted
- Date: 2026-08-27

The certified `spi-ledger-csv/v1` source remains candidate data until explicit review. Validation
records the exact included row IDs, excluded row IDs and reasons, source content hash, base ledger
version, and validated batch hash. Unknown columns, ambiguous instruments, duplicate references,
invalid signs/equations, oversells, and negative cash block approval.

Publication requires owner role, recent MFA, `If-Match`, a principal/endpoint-scoped idempotency
key, the unchanged validated hash and row selection, and the fixed acknowledgment phrase. A locked
portfolio row provides compare-and-swap against the base version. Events, cash events, ledger
version, completed job, audit receipt, and outbox record commit in one transaction. Failure rolls
back all of them. Corrections are new reversal/replacement events; published history is never
updated or deleted.
