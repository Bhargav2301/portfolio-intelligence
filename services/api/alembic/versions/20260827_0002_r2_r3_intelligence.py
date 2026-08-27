"""Add deterministic R2 analytics and evidence-linked R3 run records.

Revision ID: 20260827_0002
Revises: 20260827_0001
Create Date: 2026-08-27
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "20260827_0002"
down_revision = "20260827_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    sql = (repository_root / "infra" / "postgres" / "004_r2_r3_intelligence.sql").read_text(
        encoding="utf-8"
    )
    connection = op.get_bind()
    adapted_connection = connection.connection
    if hasattr(adapted_connection, "run_async"):
        adapted_connection.run_async(lambda driver: driver.execute(sql))
    else:
        connection.exec_driver_sql(sql)


def downgrade() -> None:
    raise RuntimeError(
        "R2/R3 financial lineage is intentionally forward-only; restore from backup."
    )
