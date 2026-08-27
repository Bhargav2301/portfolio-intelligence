# Database migrations

Run migrations with the dedicated migration role, never an application runtime role:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://..."
alembic upgrade head
```

The first migration is idempotent so it can baseline an existing vertical-slice database. The
runtime login role must be granted membership in `spi_runtime` without inheriting table ownership or
`BYPASSRLS`. LangGraph uses a separate database/schema and the `spi_checkpoint` role.

Downgrades are deliberately disabled because published ledger and audit records are immutable.
