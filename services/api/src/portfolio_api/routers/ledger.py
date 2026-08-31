from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.config import get_settings
from portfolio_api.database import apply_tenant_scope, get_tenant_session
from portfolio_api.models import (
    AnalyticsSnapshotRecord,
    AuditEvent,
    EvidenceItem,
    EvidenceLink,
    LedgerVersion,
    MetricValue,
    Portfolio,
    Transaction,
)
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


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


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
    portfolio: Portfolio,
    context: RequestContext,
    session: AsyncSession,
    *,
    as_of: datetime | None = None,
) -> dict[str, object]:
    cutoff = as_of or datetime.now(UTC)
    events = list(
        await session.scalars(
            select(Transaction)
            .where(
                Transaction.portfolio_id == portfolio.id,
                Transaction.tenant_id == context.tenant_id,
                Transaction.trade_date <= cutoff,
                Transaction.recorded_at <= cutoff,
            )
            .order_by(Transaction.trade_date, Transaction.recorded_at)
        )
    )
    protected = Decimal(str((portfolio.rules.get("protected_cash") or {}).get("amount", "0")))
    ledger = calculate_ledger(events, protected)
    ledger["as_of"] = cutoff
    return ledger


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


async def build_agent_context(
    portfolio_id: UUID,
    cutoff: datetime,
    context: RequestContext,
    session: AsyncSession,
) -> dict[str, object]:
    portfolio = await _portfolio_or_404(portfolio_id, context, session)
    ledger = await _ledger_for(portfolio, context, session, as_of=cutoff)
    threshold = Decimal(str(portfolio.rules.get("max_position_weight_percent", "25.00")))
    monitoring = build_monitor_snapshot(portfolio.id, ledger, threshold)
    stored_snapshot = await session.scalar(
        select(AnalyticsSnapshotRecord)
        .where(
            AnalyticsSnapshotRecord.tenant_id == context.tenant_id,
            AnalyticsSnapshotRecord.portfolio_id == portfolio.id,
            AnalyticsSnapshotRecord.as_of <= cutoff,
            AnalyticsSnapshotRecord.known_at <= cutoff,
        )
        .order_by(
            AnalyticsSnapshotRecord.as_of.desc(),
            AnalyticsSnapshotRecord.known_at.desc(),
            AnalyticsSnapshotRecord.created_at.desc(),
        )
        .limit(1)
    )
    analytics: dict[str, object] | None = None
    persistent_evidence: list[dict[str, object]] = []
    if stored_snapshot is not None:
        metric_rows = list(
            await session.scalars(
                select(MetricValue).where(
                    MetricValue.tenant_id == context.tenant_id,
                    MetricValue.analytics_snapshot_id == stored_snapshot.id,
                )
            )
        )
        analytics = {
            "snapshot_id": str(stored_snapshot.id),
            "as_of": _utc(stored_snapshot.as_of),
            "known_at": _utc(stored_snapshot.known_at),
            "quality_state": stored_snapshot.quality_state,
            "ledger_version": stored_snapshot.ledger_version,
            "market_data_version": stored_snapshot.market_data_version,
            "methodology_version": stored_snapshot.methodology_version,
            "metrics": {
                item.metric_code: (
                    format(Decimal(item.value), "f") if item.value is not None else None
                )
                for item in metric_rows
            },
        }
        linked_items = list(
            await session.scalars(
                select(EvidenceItem)
                .join(EvidenceLink, EvidenceLink.evidence_item_id == EvidenceItem.id)
                .where(
                    EvidenceItem.tenant_id == context.tenant_id,
                    EvidenceItem.portfolio_id == portfolio.id,
                    EvidenceItem.cutoff_eligible.is_(True),
                    EvidenceItem.known_at <= cutoff,
                    EvidenceLink.tenant_id == context.tenant_id,
                    EvidenceLink.from_type == "analytics_snapshot",
                    EvidenceLink.from_id == stored_snapshot.id,
                )
                .distinct()
            )
        )
        persistent_evidence.extend(
            {
                "id": str(item.id),
                "source_type": item.source_type,
                "title": item.title,
                "publisher": item.publisher,
                "uri": f"/v1/evidence/{item.id}",
                "as_of": _utc(stored_snapshot.as_of),
                "known_at": _utc(item.known_at),
                "content_hash": item.content_hash,
                "quality": item.quality,
                "claims": item.claims,
            }
            for item in linked_items
        )
    research_items = list(
        await session.scalars(
            select(EvidenceItem)
            .where(
                EvidenceItem.tenant_id == context.tenant_id,
                EvidenceItem.portfolio_id == portfolio.id,
                EvidenceItem.cutoff_eligible.is_(True),
                EvidenceItem.known_at <= cutoff,
                EvidenceItem.source_type.in_(
                    ["market", "fundamentals", "news", "sentiment", "research"]
                ),
            )
            .order_by(EvidenceItem.known_at.desc())
            .limit(100)
        )
    )
    persistent_evidence.extend(
        {
            "id": str(item.id),
            "source_type": item.source_type,
            "title": item.title,
            "publisher": item.publisher,
            "uri": f"/v1/evidence/{item.id}",
            "as_of": _utc(item.published_at),
            "known_at": _utc(item.known_at),
            "content_hash": item.content_hash,
            "quality": item.quality,
            "claims": item.claims,
        }
        for item in research_items
    )
    ledger_claims = [
        {
            "claim_key": key,
            "statement": f"Published ledger metric {key}.",
            "numeric_value": str(ledger[key]),
            "unit": "INR",
        }
        for key in (
            "cash_balance",
            "available_cash",
            "protected_cash",
            "net_invested_capital",
            "securities_market_value",
            "total_value",
            "realized_pnl",
        )
        if ledger.get(key) is not None
    ]
    for holding in ledger["holdings"]:  # type: ignore[index]
        instrument = str(holding["instrument_reference"])
        for field, unit in (
            ("quantity", "units"),
            ("last_price", "INR"),
            ("market_value", "INR"),
            ("unrealized_pnl", "INR"),
            ("weight_percent", "percent"),
        ):
            if holding.get(field) is not None:
                ledger_claims.append(
                    {
                        "claim_key": f"holding.{instrument}.{field}",
                        "statement": f"Published {field} for {instrument}.",
                        "numeric_value": str(holding[field]),
                        "unit": unit,
                    }
                )
    monitor_claims: list[dict[str, str]] = [
        {
            "claim_key": "active_alert_count",
            "statement": "Number of active deterministic monitor alerts.",
            "numeric_value": str(len(monitoring["alerts"])),
            "unit": "count",
        }
    ]
    for alert in monitoring["alerts"]:
        alert_id = str(alert["id"])
        if alert.get("observed_value") is not None:
            monitor_claims.append(
                {
                    "claim_key": f"alert.{alert_id}.observed_value",
                    "statement": f"Observed value for monitor alert {alert_id}.",
                    "numeric_value": str(alert["observed_value"]),
                    "unit": "percent" if alert.get("kind") == "concentration" else "INR",
                }
            )
        if alert.get("threshold_value") is not None:
            monitor_claims.append(
                {
                    "claim_key": f"alert.{alert_id}.threshold_value",
                    "statement": f"Threshold value for monitor alert {alert_id}.",
                    "numeric_value": str(alert["threshold_value"]),
                    "unit": "percent" if alert.get("kind") == "concentration" else "INR",
                }
            )
    evidence: list[dict[str, object]] = [
        {
            "id": "ledger:snapshot",
            "source_type": "deterministic_ledger",
            "title": "Published portfolio ledger snapshot",
            "uri": f"/v1/portfolios/{portfolio.id}/holdings",
            "as_of": ledger["as_of"],
            "known_at": cutoff,
            "quality": "verified",
            "claims": ledger_claims,
        },
        {
            "id": "monitor:snapshot",
            "source_type": "deterministic_monitor",
            "title": "Portfolio rule monitor snapshot",
            "uri": f"/v1/portfolios/{portfolio.id}/monitors/latest",
            "as_of": monitoring["as_of"],
            "known_at": cutoff,
            "quality": "verified",
            "claims": monitor_claims,
        },
    ]
    if _utc(portfolio.updated_at) <= _utc(cutoff):
        evidence.append(
            {
                "id": "rule:portfolio",
                "source_type": "portfolio_policy",
                "title": "Versioned portfolio rules",
                "uri": f"/v1/portfolios/{portfolio.id}",
                "as_of": _utc(portfolio.updated_at),
                "known_at": _utc(portfolio.updated_at),
                "quality": "verified",
                "claims": [
                    {
                        "claim_key": "protected_cash",
                        "statement": "Protected reserve in the active portfolio rule.",
                        "numeric_value": str(
                            (portfolio.rules.get("protected_cash") or {}).get("amount", "0")
                        ),
                        "unit": "INR",
                    },
                    {
                        "claim_key": "max_position_weight_percent",
                        "statement": "Maximum position weight in the active portfolio rule.",
                        "numeric_value": str(
                            portfolio.rules.get("max_position_weight_percent", "25.00")
                        ),
                        "unit": "percent",
                    },
                ],
            }
        )
    evidence.extend(persistent_evidence)
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
        "analytics": analytics,
        "evidence": evidence,
    }


@router.get("/agent-context")
async def get_agent_context(
    portfolio_id: UUID,
    as_of: datetime | None = Query(default=None),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, object]:
    return await build_agent_context(
        portfolio_id,
        as_of or datetime.now(UTC),
        context,
        session,
    )
