"""Run Alembic with a fresh RDS IAM token without logging the credential."""

from __future__ import annotations

import os
import subprocess
from urllib.parse import quote

import boto3


def main() -> int:
    required = [
        "MIGRATION_DB_HOST",
        "MIGRATION_DB_USER",
        "MIGRATION_DB_NAME",
        "AWS_REGION",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing migration configuration: " + ", ".join(missing))
    host = os.environ["MIGRATION_DB_HOST"]
    user = os.environ["MIGRATION_DB_USER"]
    database = os.environ["MIGRATION_DB_NAME"]
    region = os.environ["AWS_REGION"]
    port = int(os.getenv("MIGRATION_DB_PORT", "5432"))
    token = boto3.client("rds", region_name=region).generate_db_auth_token(
        DBHostname=host,
        Port=port,
        DBUsername=user,
        Region=region,
    )
    child_environment = {
        **os.environ,
        "APP_ENV": "migration",
        "DATABASE_URL": (
            f"postgresql+asyncpg://{quote(user)}:{quote(token, safe='')}@{host}:{port}/"
            f"{quote(database)}?ssl=require"
        ),
    }
    completed = subprocess.run(
        ["alembic", "-c", "/app/alembic.ini", "upgrade", "head"],
        check=False,
        env=child_environment,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
