from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.database import get_tenant_session
from portfolio_api.models import Portfolio
from portfolio_api.schemas import AnalyticsSnapshot
from portfolio_api.services.analytics import GoalInputError, required_cagr
from portfolio_api.tenant import RequestContext, request_context


router = APIRouter(prefix="/v1", tags=["analytics"])


@router.get("/goals/required-cagr")
async def goal_cagr(
    wealth_multiple: str = Query(...),
    years: str = Query(...),
) -> dict[str, str]:
    try:
        result = required_cagr(wealth_multiple, years)
    except GoalInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_GOAL", "message": str(error)},
        ) from error
    return {
        "wealth_multiple": wealth_multiple,
        "years": years,
        "required_cagr": str(result),
        "required_cagr_percent": str(result * 100),
    }


@router.get("/portfolios/{portfolio_id}/analytics/latest", response_model=AnalyticsSnapshot)
async def latest_analytics(
    portfolio_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> AnalyticsSnapshot:
    portfolio = await session.scalar(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.tenant_id == context.tenant_id,
        )
    )
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
    return AnalyticsSnapshot(
        portfolio_id=portfolio.id,
        quality_state="partial",
        as_of=datetime.now(timezone.utc),
        base_currency=portfolio.base_currency,
        ledger_version=0,
        metrics={
            "current_value": None,
            "net_invested_capital": None,
            "time_weighted_return": None,
            "benchmark_return": None,
            "protected_cash": portfolio.rules["protected_cash"]["amount"],
        },
        rules=portfolio.rules,
        limitations=[
            "No approved ledger has been published.",
            "Uploaded data remains candidate data until reconciliation.",
            "No investment action should be inferred from this empty snapshot.",
        ],
    )
