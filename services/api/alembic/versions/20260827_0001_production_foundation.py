"""Create the authoritative ledger and R0/R1 production foundation.

Revision ID: 20260827_0001
Revises:
Create Date: 2026-08-27
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "20260827_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    connection = op.get_bind()
    for filename in (
        "001_initial.sql",
        "002_production_foundation.sql",
        "003_runtime_roles.sql",
    ):
        sql = (repository_root / "infra" / "postgres" / filename).read_text(encoding="utf-8")
        adapted_connection = connection.connection
        if hasattr(adapted_connection, "run_async"):
            adapted_connection.run_async(lambda driver, statement=sql: driver.execute(statement))
        else:
            connection.exec_driver_sql(sql)


def downgrade() -> None:
    raise RuntimeError(
        "The production ledger foundation is intentionally forward-only; restore from backup."
    )
