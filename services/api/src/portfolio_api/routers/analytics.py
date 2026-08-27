from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.database import get_tenant_session
from portfolio_api.models import AnalyticsSnapshotRecord, Portfolio, Transaction
from portfolio_api.routers.intelligence import snapshot_detail
from portfolio_api.schemas import AnalyticsSnapshot
from portfolio_api.services.analytics import GoalInputError, required_cagr
from portfolio_api.services.ledger import calculate_ledger
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    stored = await session.scalar(
        select(AnalyticsSnapshotRecord)
        .where(
            AnalyticsSnapshotRecord.portfolio_id == portfolio.id,
            AnalyticsSnapshotRecord.tenant_id == context.tenant_id,
        )
        .order_by(AnalyticsSnapshotRecord.as_of.desc(), AnalyticsSnapshotRecord.created_at.desc())
        .limit(1)
    )
    if stored is not None:
        return await snapshot_detail(session, portfolio, stored)
    events = list(
        await session.scalars(
            select(Transaction)
            .where(
                Transaction.portfolio_id == portfolio.id,
                Transaction.tenant_id == context.tenant_id,
            )
            .order_by(Transaction.trade_date, Transaction.recorded_at)
        )
    )
    protected = Decimal(str((portfolio.rules.get("protected_cash") or {}).get("amount", "0")))
    ledger = calculate_ledger(events, protected)
    has_ledger = bool(events)
    limitations = list(ledger["limitations"])
    if not has_ledger:
        limitations.extend(
            [
                "No approved ledger has been published.",
                "Uploaded data remains candidate data until reconciliation.",
                "No investment action should be inferred from this empty snapshot.",
            ]
        )
    else:
        limitations.append(
            "Return, benchmark, volatility, and drawdown require historical valuation snapshots."
        )
    return AnalyticsSnapshot(
        portfolio_id=portfolio.id,
        quality_state="trusted" if has_ledger else "partial",
        as_of=ledger["as_of"] if has_ledger else datetime.now(UTC),
        base_currency=portfolio.base_currency,
        ledger_version=int(ledger["ledger_version"]),
        metrics={
            "current_value": str(ledger["total_value"]) if has_ledger else None,
            "net_invested_capital": (str(ledger["net_invested_capital"]) if has_ledger else None),
            "cash_balance": str(ledger["cash_balance"]) if has_ledger else None,
            "securities_market_value": (
                str(ledger["securities_market_value"]) if has_ledger else None
            ),
            "unrealized_pnl": (
                str(
                    sum(
                        Decimal(str(row["unrealized_pnl"]))
                        for row in ledger["holdings"]
                        if row["unrealized_pnl"] is not None
                    )
                )
                if has_ledger
                else None
            ),
            "realized_pnl": str(ledger["realized_pnl"]) if has_ledger else None,
            "time_weighted_return": None,
            "benchmark_return": None,
            "protected_cash": portfolio.rules["protected_cash"]["amount"],
        },
        rules=portfolio.rules,
        limitations=limitations,
    )
