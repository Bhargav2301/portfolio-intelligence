# ADR 0002: Forced PostgreSQL RLS and transaction-local tenant context

- Status: Accepted
- Date: 2026-08-27

Every tenant table enables and forces row-level security. Runtime identities are login roles that
are non-owner, non-superuser, and `NOBYPASSRLS`; only the migration role owns application tables.
Core sets `app.current_tenant` and `app.current_user` with transaction-local `set_config` before any
query and reapplies them when a new transaction begins.

Tenant-bearing parent and child tables also use composite `(resource_id, tenant_id)` foreign keys.
This prevents a tenant-visible child row from referencing an otherwise valid parent in another
tenant. Append-only ledger, cash, audit, and outbox objects deny destructive runtime operations.

The CI PostgreSQL 16 suite proves raw SQL isolation, forced-RLS non-bypass, cross-tenant foreign-key
denial, and that a one-connection pool exposes zero rows between transaction-local contexts.
