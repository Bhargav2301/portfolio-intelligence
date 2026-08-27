from __future__ import annotations

import os
import secrets
import unittest
from urllib.parse import urlsplit, urlunsplit

import asyncpg

TENANT_A = "10000000-0000-0000-0000-000000000001"
TENANT_B = "20000000-0000-0000-0000-000000000001"
USER_A = "10000000-0000-0000-0000-000000000002"
USER_B = "20000000-0000-0000-0000-000000000002"
PORTFOLIO_A = "10000000-0000-0000-0000-000000000003"
PORTFOLIO_B = "20000000-0000-0000-0000-000000000003"
DATASET_A = "10000000-0000-0000-0000-000000000010"
DATASET_B = "20000000-0000-0000-0000-000000000010"
RUNTIME_PASSWORD = secrets.token_urlsafe(24)


def runtime_dsn(admin_dsn: str) -> str:
    parsed = urlsplit(admin_dsn)
    host = parsed.hostname or "localhost"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit(
        (parsed.scheme, f"spi_runtime:{RUNTIME_PASSWORD}@{host}", parsed.path, "", "")
    )


@unittest.skipUnless(
    os.getenv("TEST_POSTGRES_ADMIN_DSN"), "PostgreSQL RLS test DSN is not configured"
)
class PostgreSQLRlsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.admin_dsn = os.environ["TEST_POSTGRES_ADMIN_DSN"]
        admin = await asyncpg.connect(self.admin_dsn)
        try:
            await admin.execute(f"ALTER ROLE spi_runtime PASSWORD '{RUNTIME_PASSWORD}'")
            await admin.execute(
                """
                INSERT INTO tenants (id, name, tenant_type, base_currency)
                VALUES ($1, 'Tenant A', 'individual', 'INR'), ($2, 'Tenant B', 'individual', 'INR')
                ON CONFLICT (id) DO NOTHING
                """,
                TENANT_A,
                TENANT_B,
            )
            await admin.execute(
                """
                INSERT INTO users (id, identity_provider_subject, status)
                VALUES ($1, 'ci:user-a', 'active'), ($2, 'ci:user-b', 'active')
                ON CONFLICT (id) DO NOTHING
                """,
                USER_A,
                USER_B,
            )
            await admin.execute(
                """
                INSERT INTO tenant_memberships (tenant_id, user_id, role, status)
                VALUES ($1, $3, 'owner', 'active'), ($2, $4, 'owner', 'active')
                ON CONFLICT (tenant_id, user_id) DO NOTHING
                """,
                TENANT_A,
                TENANT_B,
                USER_A,
                USER_B,
            )
            await admin.execute(
                """
                INSERT INTO portfolios (
                    id, tenant_id, owner_user_id, name, portfolio_type, base_currency, benchmark_code,
                    valuation_timezone, status, version, ledger_version, rules
                ) VALUES
                    ($5, $1, $3, 'Portfolio A', 'self_managed', 'INR', 'NIFTY_500_TRI', 'Asia/Kolkata', 'active', 1, 0, '{}'::jsonb),
                    ($6, $2, $4, 'Portfolio B', 'self_managed', 'INR', 'NIFTY_500_TRI', 'Asia/Kolkata', 'active', 1, 0, '{}'::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                TENANT_A,
                TENANT_B,
                USER_A,
                USER_B,
                PORTFOLIO_A,
                PORTFOLIO_B,
            )
            await admin.execute(
                """
                INSERT INTO market_data_sets (
                    id, tenant_id, portfolio_id, provider, provider_version, rights_basis,
                    cutoff_at, known_at, content_hash, status, created_by
                ) VALUES
                    ($1, $3, $5, 'ci-feed', 'tenant-a', 'licensed',
                     '2026-08-26T10:00:00Z', '2026-08-26T10:01:00Z', $7, 'sealed', $9),
                    ($2, $4, $6, 'ci-feed', 'tenant-b', 'licensed',
                     '2026-08-26T10:00:00Z', '2026-08-26T10:01:00Z', $8, 'sealed', $10)
                ON CONFLICT (id) DO NOTHING
                """,
                DATASET_A,
                DATASET_B,
                TENANT_A,
                TENANT_B,
                PORTFOLIO_A,
                PORTFOLIO_B,
                "a" * 64,
                "b" * 64,
                USER_A,
                USER_B,
            )
        finally:
            await admin.close()

    async def test_runtime_role_is_non_owner_and_cannot_bypass_forced_rls(self) -> None:
        connection = await asyncpg.connect(runtime_dsn(self.admin_dsn))
        try:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                )
                await connection.execute("SELECT set_config('app.current_user', $1, true)", USER_A)
                rows = await connection.fetch("SELECT id, tenant_id FROM portfolios ORDER BY id")
                self.assertEqual(
                    [(str(row["id"]), str(row["tenant_id"])) for row in rows],
                    [(PORTFOLIO_A, TENANT_A)],
                )
                hidden = await connection.fetchval(
                    "SELECT count(*) FROM portfolios WHERE tenant_id = $1", TENANT_B
                )
                self.assertEqual(hidden, 0)
                with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                    await connection.execute("ALTER TABLE portfolios DISABLE ROW LEVEL SECURITY")
        finally:
            await connection.close()

    async def test_transaction_local_context_does_not_leak_on_pool_reuse(self) -> None:
        pool = await asyncpg.create_pool(runtime_dsn(self.admin_dsn), min_size=1, max_size=1)
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                    )
                    self.assertEqual(
                        await connection.fetchval("SELECT count(*) FROM portfolios"), 1
                    )
            async with pool.acquire() as connection:
                self.assertEqual(await connection.fetchval("SELECT count(*) FROM portfolios"), 0)
                async with connection.transaction():
                    await connection.execute(
                        "SELECT set_config('app.current_tenant', $1, true)", TENANT_B
                    )
                    rows = await connection.fetch("SELECT id FROM portfolios")
                    self.assertEqual([str(row["id"]) for row in rows], [PORTFOLIO_B])
        finally:
            await pool.close()

    async def test_cross_tenant_insert_is_rejected_by_database(self) -> None:
        connection = await asyncpg.connect(runtime_dsn(self.admin_dsn))
        try:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                )
                with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                    await connection.execute(
                        """
                        INSERT INTO portfolios (
                            id, tenant_id, owner_user_id, name, portfolio_type, base_currency, benchmark_code,
                            valuation_timezone, status, version, ledger_version, rules
                        ) VALUES (
                            '30000000-0000-0000-0000-000000000003', $1, $2, 'Cross tenant',
                            'self_managed', 'INR', 'NIFTY_500_TRI', 'Asia/Kolkata', 'active', 1, 0, '{}'::jsonb
                        )
                        """,
                        TENANT_B,
                        USER_B,
                    )
        finally:
            await connection.close()

    async def test_composite_foreign_key_rejects_cross_tenant_parent(self) -> None:
        connection = await asyncpg.connect(runtime_dsn(self.admin_dsn))
        try:
            with self.assertRaises(asyncpg.ForeignKeyViolationError):
                async with connection.transaction():
                    await connection.execute(
                        "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                    )
                    await connection.execute(
                        """
                        INSERT INTO uploads (
                            id, tenant_id, portfolio_id, created_by, object_key, original_name,
                            declared_type, detected_type, source_role, authority_level,
                            size_bytes, sha256, state, parser_summary
                        ) VALUES (
                            '30000000-0000-0000-0000-000000000004', $1, $2, $3,
                            'tenant-a/quarantine/test.csv', 'test.csv', 'text/csv', 'csv',
                            'brokerage_ledger', 'ledger_candidate', 1,
                            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                            'initiated', '{}'::jsonb
                        )
                        """,
                        TENANT_A,
                        PORTFOLIO_B,
                        USER_A,
                    )
        finally:
            await connection.close()

    async def test_r2_tables_are_forced_rls_and_cross_tenant_fk_safe(self) -> None:
        connection = await asyncpg.connect(runtime_dsn(self.admin_dsn))
        try:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                )
                visible = await connection.fetch("SELECT id FROM market_data_sets ORDER BY id")
                self.assertEqual([str(row["id"]) for row in visible], [DATASET_A])
                hidden = await connection.fetchval(
                    "SELECT count(*) FROM market_data_sets WHERE tenant_id = $1", TENANT_B
                )
                self.assertEqual(hidden, 0)
                with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                    await connection.execute(
                        "ALTER TABLE analytics_snapshots DISABLE ROW LEVEL SECURITY"
                    )

            with self.assertRaises(asyncpg.ForeignKeyViolationError):
                async with connection.transaction():
                    await connection.execute(
                        "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                    )
                    await connection.execute(
                        """
                        INSERT INTO price_observations (
                            tenant_id, market_data_set_id, instrument_reference,
                            observed_at, known_at, close_price, currency, quality, source_hash
                        ) VALUES (
                            $1, $2, 'TEST.NS', '2026-08-26T10:00:00Z',
                            '2026-08-26T10:01:00Z', 100, 'INR', 'verified', $3
                        )
                        """,
                        TENANT_A,
                        DATASET_B,
                        "c" * 64,
                    )
        finally:
            await connection.close()

    async def test_agent_run_transition_is_one_way_and_non_executable(self) -> None:
        connection = await asyncpg.connect(runtime_dsn(self.admin_dsn))
        run_id = "10000000-0000-0000-0000-000000000020"
        try:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                )
                await connection.execute(
                    """
                    INSERT INTO agent_runs (
                        id, tenant_id, portfolio_id, thread_id, initiated_by, request_id,
                        question_hash, as_of, known_at, graph_version, prompt_bundle_version,
                        model_route, policy_version, allowed_tools, checkpoint_thread_id,
                        state, can_execute
                    ) VALUES (
                        $1, $2, $3, '10000000-0000-0000-0000-000000000021', $4,
                        'postgres-transition-test', $5, '2026-08-26T10:00:00Z',
                        '2026-08-26T10:00:00Z', 'test/1', 'test/1',
                        'deterministic-safe', 'test/1', '[]'::jsonb, $6, 'running', false
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    run_id,
                    TENANT_A,
                    PORTFOLIO_A,
                    USER_A,
                    "d" * 64,
                    "e" * 64,
                )
                await connection.execute(
                    """
                    UPDATE agent_runs
                    SET state = 'completed', stages = '["output_validated"]'::jsonb,
                        result_hash = $2, completed_at = now()
                    WHERE id = $1
                    """,
                    run_id,
                    "f" * 64,
                )
                self.assertEqual(
                    await connection.fetchval("SELECT state FROM agent_runs WHERE id = $1", run_id),
                    "completed",
                )

            with self.assertRaises(asyncpg.RaiseError):
                async with connection.transaction():
                    await connection.execute(
                        "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                    )
                    await connection.execute(
                        "UPDATE agent_runs SET state = 'running' WHERE id = $1", run_id
                    )

            with self.assertRaises(asyncpg.CheckViolationError):
                async with connection.transaction():
                    await connection.execute(
                        "SELECT set_config('app.current_tenant', $1, true)", TENANT_A
                    )
                    await connection.execute(
                        """
                        INSERT INTO agent_runs (
                            id, tenant_id, portfolio_id, thread_id, initiated_by, request_id,
                            question_hash, as_of, known_at, graph_version,
                            prompt_bundle_version, model_route, policy_version, allowed_tools,
                            checkpoint_thread_id, state, can_execute
                        ) VALUES (
                            '10000000-0000-0000-0000-000000000022', $1, $2,
                            '10000000-0000-0000-0000-000000000023', $3,
                            'postgres-executable-test', $4, '2026-08-26T10:00:00Z',
                            '2026-08-26T10:00:00Z', 'test/1', 'test/1',
                            'deterministic-safe', 'test/1', '[]'::jsonb, $5, 'running', true
                        )
                        """,
                        TENANT_A,
                        PORTFOLIO_A,
                        USER_A,
                        "1" * 64,
                        "2" * 64,
                    )
        finally:
            await connection.close()
