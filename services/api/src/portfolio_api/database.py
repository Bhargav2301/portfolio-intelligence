from __future__ import annotations

import asyncio
import ssl
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import engine as sqlalchemy_engine
from sqlalchemy import event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from portfolio_api.config import get_settings
from portfolio_api.models import Base, Tenant, TenantMembership, User
from portfolio_api.tenant import RequestContext, request_context

settings = get_settings()


async def _rds_iam_connection():
    """Create a TLS PostgreSQL connection with a fresh 15-minute IAM auth token."""
    import asyncpg
    import boto3

    url = make_url(settings.database_url)
    if not url.host or not url.username or not url.database:
        raise RuntimeError("DATABASE_URL must include host, runtime role, and database.")
    port = url.port or 5432
    client = boto3.client("rds", region_name=settings.aws_region)
    token = await asyncio.to_thread(
        client.generate_db_auth_token,
        DBHostname=url.host,
        Port=port,
        DBUsername=url.username,
        Region=settings.aws_region,
    )
    return await asyncpg.connect(
        host=url.host,
        port=port,
        user=url.username,
        password=token,
        database=url.database,
        ssl=ssl.create_default_context(),
        timeout=10,
        command_timeout=30,
    )


engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=600 if settings.rds_iam_auth else -1,
    **({"async_creator": _rds_iam_connection} if settings.rds_iam_auth else {}),
)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _restore_transaction_scope(session: Session, _transaction: object, connection: object) -> None:
    """Reapply transaction-local identity after a commit starts a new transaction."""
    tenant_id = session.info.get("tenant_id")
    user_id = session.info.get("user_id")
    if connection.dialect.name != "postgresql" or not tenant_id:
        return
    connection.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    connection.execute(
        text("SELECT set_config('app.current_user', :user_id, true)"),
        {"user_id": str(user_id or "")},
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def apply_tenant_scope(
    session: AsyncSession, tenant_id: UUID, user_id: UUID | None = None
) -> None:
    """Bind PostgreSQL RLS to this transaction; explicit query filters remain mandatory."""
    session.info["tenant_id"] = tenant_id
    session.info["user_id"] = user_id
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        await session.execute(
            text("SELECT set_config('app.current_user', :user_id, true)"),
            {"user_id": str(user_id or "")},
        )


async def get_tenant_session(
    context: RequestContext = Depends(request_context),
) -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        await apply_tenant_scope(session, context.tenant_id, context.user_id)
        settings = get_settings()
        if settings.requires_oidc:
            membership = await session.scalar(
                select(TenantMembership)
                .join(User, User.id == TenantMembership.user_id)
                .where(
                    TenantMembership.tenant_id == context.tenant_id,
                    TenantMembership.user_id == context.user_id,
                    TenantMembership.status == "active",
                    User.identity_provider_subject == context.identity_subject,
                    User.status == "active",
                )
            )
            if membership is None:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "WORKSPACE_ACCESS_DENIED",
                        "message": "You are not an active member of this workspace.",
                    },
                )
            context.role = membership.role
        yield session


async def initialize_database() -> None:
    if settings.is_production:
        return
    database_name = sqlalchemy_engine.make_url(settings.database_url).database
    if settings.database_url.startswith("sqlite") and database_name not in {None, ":memory:"}:
        Path(database_name).expanduser().parent.mkdir(parents=True, exist_ok=True)
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
        user = await session.scalar(select(User).where(User.id == settings.dev_user_id))
        if user is None:
            session.add(
                User(
                    id=settings.dev_user_id,
                    identity_provider_subject=f"development:{settings.dev_user_id}",
                    status="active",
                )
            )
        membership = await session.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == settings.dev_workspace_id,
                TenantMembership.user_id == settings.dev_user_id,
            )
        )
        if membership is None:
            session.add(
                TenantMembership(
                    tenant_id=settings.dev_workspace_id,
                    user_id=settings.dev_user_id,
                    role="owner",
                    status="active",
                )
            )
        await session.commit()


async def close_database() -> None:
    await engine.dispose()
