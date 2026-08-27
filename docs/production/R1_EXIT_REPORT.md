# R1 exit report

Status: **not approved for production traffic**

## Verified in this implementation session

- [x] API suite: 24 tests cover the certified CSV golden lifecycle, duplicate handling,
  tenant-scoped ledger/API behavior, telemetry, and PostgreSQL isolation (20 local plus 4 PostgreSQL).
- [x] Agent suite: 7 tests cover bounded graph behavior, execution-language suppression,
  and `Literal[False]` validation.
- [x] PostgreSQL 16 migration applied to a disposable real cluster.
- [x] Forced RLS blocks cross-tenant reads/inserts and runtime RLS disable.
- [x] Composite foreign keys block cross-tenant parent references.
- [x] A one-connection pool exposes zero rows between transaction-local tenant scopes.
- [x] Telemetry canary excludes seeded path/header/body values and uses route templates.
- [x] Next.js type-check and production build pass.
- [x] Terraform 1.10.5 with AWS provider 6.62 validates without warnings.

## Required external staging evidence

- [ ] Cut certified CSV completion over from in-process scanning/parsing to the retry-safe SQS
  ingestion worker, then prove duplicate delivery, crash recovery, and DLQ behavior.
- [ ] Invalid, expired, wrong-client, wrong-issuer, revoked-session, revoked-membership, stale-MFA,
  and downgraded-role Cognito tests.
- [ ] Cognito passkey and password-plus-TOTP enrollment/recovery exercise for all pilot users.
- [ ] S3 presign, checksum, KMS, malware, lifecycle, and tenant-prefix tests in staging.
- [ ] Concurrent publication and injected transaction-failure test on RDS PostgreSQL.
- [ ] CloudWatch/X-Ray seeded-sensitive-value scan across synchronous and asynchronous paths.
- [ ] Queue retry/DLQ and alarm-delivery exercise.
- [ ] Point-in-time and cross-region restore drill proving RPO ≤15 minutes and RTO ≤4 hours.
- [ ] Container signature/SBOM/scan evidence and 5% canary rollback exercise.
- [ ] Product owner and security owner signatures.

Until every unchecked item is evidenced, `enable_services`, `identity_gate_passed`,
`rls_gate_passed`, and `telemetry_gate_passed` must not all be true.
