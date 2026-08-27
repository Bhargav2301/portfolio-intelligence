# Production roadmap and exit gates

Production is an invite-only ten-user pilot. No environment may receive data or traffic until the
identity, forced-RLS, and telemetry gates are signed. Terraform desired counts enforce this rule.

| Release | Technical milestone | Exit gate | Main mitigation |
|---|---|---|---|
| R0 | Cognito BFF, membership authorization, forced RLS, safe telemetry, migrations, AWS foundation | Token-negative suite; PostgreSQL cross-tenant and pool tests; telemetry canary; measured restore | Opaque sessions, non-owner roles, transaction-local context, gate flags default off |
| R1 | Certified CSV quarantine, reconciliation, idempotent atomic publication, source lineage | Golden/fuzz files, exact row coverage, concurrent CAS, rollback, duplicate and tenant denial | One template, Decimal values, malware scan, checksums, owner/MFA review |
| R2 | Versioned prices/corporate actions, valuation snapshots, deterministic returns/risk/scenarios | Finance golden/property tests and historical reproducibility | Dataset/methodology versions, freshness gates, no V1 tax calculations |
| R3 | Licensed evidence gateway, durable agent runs/checkpoints, evidence-linked chat | No cutoff leakage, bounded completion ≥99%, numeric citation coverage, abstention tests | Tool allowlists, budgets, prompt isolation, durable versions, kill switch |
| R4 | Privacy/suitability and isolated Upstox order gateway | Agent isolation, capability replay/mutation tests, full sandbox scenario certification | Separate IAM/network/database roles, exact payload review, strict product/limit rules |
| R5 | Operational qualification and controlled rollout | Performance, restore, accessibility, adversarial, security, and launch approvals | Dark launch, two-user pilot, sandbox, one-user live, then ten users |

Indicative staffing remains two application engineers, one platform/security engineer, and
part-time QA/UX over 16–20 weeks. R0/R1 code can be reviewed before cloud-account onboarding, but
the Terraform gates prohibit traffic until staging evidence exists.

## Current implementation checkpoint

- R0 repository foundation: implemented and locally verified.
- R1 certified parse/reconciliation/publication: implemented and locally verified.
- AWS Terraform and signed-digest pipeline: implemented and provider-schema validated.
- Staging account provisioning, Cognito end-to-end tests, backup restore drill, telemetry canary,
  and formal R1 sign-off: pending external AWS accounts, DNS/certificates, secrets, and approvals.
- R2–R5 product capabilities: roadmap only unless separately marked in `R1_EXIT_REPORT.md`.
