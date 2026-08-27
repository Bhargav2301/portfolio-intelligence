from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.config import get_settings
from portfolio_api.database import apply_tenant_scope, get_tenant_session
from portfolio_api.models import AuditEvent, LedgerVersion, Portfolio, Transaction
from portfolio_api.schemas import (
    LedgerEventCreate,
    LedgerEventRead,
    LedgerSnapshot,
    MonitorSnapshot,
)
from portfolio_api.services.control_plane import canonical_hash
from portfolio_api.services.ledger import (
    LedgerInvariantError,
    build_monitor_snapshot,
    calculate_ledger,
)
from portfolio_api.tenant import RequestContext, request_context

router = APIRouter(prefix="/v1/portfolios/{portfolio_id}", tags=["ledger"])


async def _portfolio_or_404(
    portfolio_id: UUID, context: RequestContext, session: AsyncSession
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


async def _ledger_for(
    portfolio: Portfolio, context: RequestContext, session: AsyncSession
) -> dict[str, object]:
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
    return calculate_ledger(events, protected)


@router.post("/ledger/events", response_model=LedgerEventRead, status_code=status.HTTP_201_CREATED)
async def publish_ledger_event(
    portfolio_id: UUID,
    payload: LedgerEventCreate,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> Transaction:
    if get_settings().requires_oidc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MANUAL_PUBLICATION_DISABLED",
                "message": "Use the reviewed import or correction workflow.",
            },
        )
    portfolio = await _portfolio_or_404(portfolio_id, context, session)
    event_id = uuid4()
    new_version = portfolio.ledger_version + 1
    cash_delta = {
        "buy": -payload.gross_amount,
        "sell": payload.gross_amount,
        "cash_deposit": payload.gross_amount,
        "cash_withdrawal": -payload.gross_amount,
        "dividend": payload.gross_amount,
        "dividend_cash": payload.gross_amount,
        "fee": -payload.gross_amount,
        "price_mark": Decimal("0"),
    }.get(payload.event_type)
    event = Transaction(
        id=event_id,
        tenant_id=context.tenant_id,
        portfolio_id=portfolio.id,
        event_type=payload.event_type,
        trade_date=payload.trade_date,
        instrument_reference=payload.instrument_reference,
        quantity=payload.quantity,
        price=payload.price,
        gross_amount=payload.gross_amount,
        currency=payload.currency,
        source_reference=payload.source_reference,
        ledger_version=new_version,
        cash_delta=cash_delta,
    )
    existing_events = list(
        await session.scalars(
            select(Transaction).where(
                Transaction.portfolio_id == portfolio.id,
                Transaction.tenant_id == context.tenant_id,
            )
        )
    )
    try:
        calculate_ledger(
            [*existing_events, event],
            Decimal(str((portfolio.rules.get("protected_cash") or {}).get("amount", "0"))),
        )
    except LedgerInvariantError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "LEDGER_INVARIANT_VIOLATION", "message": str(error)},
        ) from error
    session.add(event)
    portfolio.ledger_version = new_version
    portfolio.version += 1
    session.add(
        LedgerVersion(
            tenant_id=context.tenant_id,
            portfolio_id=portfolio.id,
            version=new_version,
            event_count=1,
            content_hash=canonical_hash(payload.model_dump(mode="json")),
            published_by=context.user_id,
        )
    )
    session.add(
        AuditEvent(
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            action="ledger.event_published",
            resource_type="transaction",
            resource_id=event_id,
            details={
                "portfolio_id": str(portfolio.id),
                "event_type": payload.event_type,
                "source_reference": payload.source_reference,
                "human_confirmed": True,
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_LEDGER_EVENT",
                "message": "This source reference is already published for the portfolio.",
            },
        ) from error
    await apply_tenant_scope(session, context.tenant_id, context.user_id)
    await session.refresh(event)
    return event


@router.get("/ledger/events", response_model=list[LedgerEventRead])
async def list_ledger_events(
    portfolio_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[Transaction]:
    portfolio = await _portfolio_or_404(portfolio_id, context, session)
    return list(
        await session.scalars(
            select(Transaction)
            .where(
                Transaction.portfolio_id == portfolio.id,
                Transaction.tenant_id == context.tenant_id,
            )
            .order_by(Transaction.trade_date.desc(), Transaction.recorded_at.desc())
        )
    )


@router.get("/holdings", response_model=LedgerSnapshot)
async def get_holdings(
    portfolio_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> LedgerSnapshot:
    portfolio = await _portfolio_or_404(portfolio_id, context, session)
    return LedgerSnapshot(
        portfolio_id=portfolio.id, **await _ledger_for(portfolio, context, session)
    )


@router.get("/monitors/latest", response_model=MonitorSnapshot)
async def get_monitors(
    portfolio_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> MonitorSnapshot:
    portfolio = await _portfolio_or_404(portfolio_id, context, session)
    ledger = await _ledger_for(portfolio, context, session)
    threshold = Decimal(str(portfolio.rules.get("max_position_weight_percent", "25.00")))
    return MonitorSnapshot(**build_monitor_snapshot(portfolio.id, ledger, threshold))


@router.get("/agent-context")
async def get_agent_context(
    portfolio_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, object]:
    portfolio = await _portfolio_or_404(portfolio_id, context, session)
    ledger = await _ledger_for(portfolio, context, session)
    threshold = Decimal(str(portfolio.rules.get("max_position_weight_percent", "25.00")))
    monitoring = build_monitor_snapshot(portfolio.id, ledger, threshold)
    return {
        "portfolio": {
            "id": str(portfolio.id),
            "name": portfolio.name,
            "base_currency": portfolio.base_currency,
            "benchmark_code": portfolio.benchmark_code,
            "rules": portfolio.rules,
        },
        "ledger": ledger,
        "monitoring": monitoring,
        "evidence": [
            {
                "id": "ledger:snapshot",
                "source_type": "deterministic_ledger",
                "title": "Published portfolio ledger snapshot",
                "uri": f"/v1/portfolios/{portfolio.id}/holdings",
                "as_of": ledger["as_of"],
            },
            {
                "id": "monitor:snapshot",
                "source_type": "deterministic_monitor",
                "title": "Portfolio rule monitor snapshot",
                "uri": f"/v1/portfolios/{portfolio.id}/monitors/latest",
                "as_of": monitoring["as_of"],
            },
            {
                "id": "rule:portfolio",
                "source_type": "portfolio_policy",
                "title": "Versioned portfolio rules",
                "uri": f"/v1/portfolios/{portfolio.id}",
                "as_of": portfolio.updated_at,
            },
        ],
    }
