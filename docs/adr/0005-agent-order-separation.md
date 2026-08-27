# ADR 0005: Agent proposals and human order authority are separate systems

- Status: Accepted
- Date: 2026-08-27

Agents emit `AgentProposal` with required `Literal[False] can_execute`; PostgreSQL independently
checks `can_execute = false`. Agent IAM explicitly denies broker secrets, capability signing,
order-service discovery, and broker API invocation. Its security group has no route to order port
8010. Core is the only service that can sign a short-lived execution capability, and the order
gateway is disabled until legal, broker, identity, RLS, telemetry, and live-order gates all pass.

A future human creates a separate `OrderIntent` after reviewing exact instrument, side, quantity,
limit, charges, risks, and allocation effect. The capability is bound to tenant, human user,
operation, resource, exact payload hash, recent MFA, expiry, audience, and one-time `jti`. No agent
output is accepted as an order intent. Unknown broker outcomes must be reconciled by client tag
before retry.
