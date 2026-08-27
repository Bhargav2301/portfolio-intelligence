from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.database import apply_tenant_scope, get_tenant_session
from portfolio_api.models import AuditEvent, Portfolio
from portfolio_api.schemas import PortfolioCreate, PortfolioRead
from portfolio_api.tenant import RequestContext, request_context

router = APIRouter(prefix="/v1/portfolios", tags=["portfolios"])


@router.post("", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: PortfolioCreate,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> Portfolio:
    portfolio_id = uuid4()
    portfolio = Portfolio(
        id=portfolio_id,
        tenant_id=context.tenant_id,
        owner_user_id=context.user_id,
        **payload.model_dump(),
    )
    session.add(portfolio)
    session.add(
        AuditEvent(
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            action="portfolio.created",
            resource_type="portfolio",
            resource_id=portfolio_id,
            details={"portfolio_type": payload.portfolio_type},
        )
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PORTFOLIO_NAME_EXISTS",
                "message": "A portfolio with this name already exists in the workspace.",
            },
        ) from error
    await apply_tenant_scope(session, context.tenant_id)
    await session.refresh(portfolio)
    return portfolio


@router.get("", response_model=list[PortfolioRead])
async def list_portfolios(
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[Portfolio]:
    result = await session.scalars(
        select(Portfolio)
        .where(Portfolio.tenant_id == context.tenant_id)
        .order_by(Portfolio.created_at.desc())
    )
    return list(result)


@router.get("/{portfolio_id}", response_model=PortfolioRead)
async def get_portfolio(
    portfolio_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> Portfolio:
    portfolio = await session.scalar(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.tenant_id == context.tenant_id,
        )
    )
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
    return portfolio
