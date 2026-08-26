from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from portfolio_api.config import get_settings
from portfolio_api.models import Base, Tenant
from portfolio_api.tenant import RequestContext, request_context


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def apply_tenant_scope(session: AsyncSession, tenant_id: UUID) -> None:
    """Bind PostgreSQL RLS to this transaction; explicit query filters remain mandatory."""
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )


async def get_tenant_session(
    context: RequestContext = Depends(request_context),
) -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        await apply_tenant_scope(session, context.tenant_id)
        yield session


async def initialize_database() -> None:
    if settings.is_production:
        return
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionFactory() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.id == settings.dev_workspace_id))
        if tenant is None:
            session.add(
                Tenant(
                    id=settings.dev_workspace_id,
                    name="Local Portfolio Intelligence",
                    tenant_type="individual",
                    base_currency="INR",
                )
            )
            await session.commit()


async def close_database() -> None:
    await engine.dispose()
