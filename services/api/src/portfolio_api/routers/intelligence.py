from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.config import get_settings
from portfolio_api.database import get_tenant_session
from portfolio_api.models import (
    AgentProposalRecord,
    AgentRunEvidence,
    AgentRunRecord,
    AgentRunStep,
    AnalyticsSnapshotRecord,
    CorporateAction,
    EvidenceItem,
    EvidenceLink,
    MarketDataSet,
    MetricValue,
    Portfolio,
    PriceObservation,
    ScenarioRun,
    Transaction,
    ValuationPosition,
)
from portfolio_api.routers.ledger import build_agent_context
from portfolio_api.schemas import (
    AgentRunComplete,
    AgentRunRead,
    AgentRunStart,
    AnalyticsRecompute,
    AnalyticsSnapshotDetail,
    EvidenceCreate,
    EvidenceRead,
    MarketDataSetCreate,
    MarketDataSetRead,
    MetricRead,
    ScenarioCreate,
    ScenarioRead,
    ValuationPositionRead,
)
from portfolio_api.services.control_plane import (
    audit_event,
    canonical_hash,
    idempotent_replay,
    require_recent_owner,
    store_idempotency,
)
from portfolio_api.services.evidence import numeric_citation_coverage
from portfolio_api.services.ledger import MONEY_QUANTUM
from portfolio_api.services.valuation import (
    METHODOLOGY_VERSION,
    RATE_QUANTUM,
    SCENARIO_ENGINE_VERSION,
    SnapshotPoint,
    ValuationInputError,
    calculate_point_in_time_valuation,
    calculate_return_and_risk,
    calculate_xirr,
    run_market_stress_scenario,
)
from portfolio_api.tenant import RequestContext, request_context

router = APIRouter(prefix="/v1", tags=["intelligence"])


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


async def _portfolio_or_404(
    session: AsyncSession, context: RequestContext, portfolio_id: UUID
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


def _require_analytics_role(context: RequestContext) -> None:
    if context.role not in {"owner", "adviser", "analyst"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ANALYTICS_ROLE_REQUIRED",
                "message": "This workspace role cannot create derived analytics.",
            },
        )


def _require_agent_service(token: str | None) -> None:
    settings = get_settings()
    expected = settings.agent_core_shared_secret
    if expected and token and secrets.compare_digest(expected, token):
        return
    if not settings.requires_oidc and not expected:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "AGENT_SERVICE_DENIED", "message": "Agent service identity is invalid."},
    )


def _decimal_text(value: Decimal | None, unit: str) -> str | None:
    if value is None:
        return None
    quantum = MONEY_QUANTUM if unit in {"INR", "currency"} else RATE_QUANTUM
    return format(Decimal(value).quantize(quantum), "f")


async def snapshot_detail(
    session: AsyncSession,
    portfolio: Portfolio,
    snapshot: AnalyticsSnapshotRecord,
) -> AnalyticsSnapshotDetail:
    metrics = list(
        await session.scalars(
            select(MetricValue)
            .where(
                MetricValue.tenant_id == snapshot.tenant_id,
                MetricValue.analytics_snapshot_id == snapshot.id,
            )
            .order_by(MetricValue.metric_code, MetricValue.dimension_type, MetricValue.dimension_id)
        )
    )
    positions = list(
        await session.scalars(
            select(ValuationPosition)
            .where(
                ValuationPosition.tenant_id == snapshot.tenant_id,
                ValuationPosition.analytics_snapshot_id == snapshot.id,
            )
            .order_by(ValuationPosition.instrument_reference)
        )
    )
    metric_rows = [
        MetricRead(
            metric_code=item.metric_code,
            dimension_type=item.dimension_type,
            dimension_id=item.dimension_id,
            value=_decimal_text(item.value, item.unit),
            unit=item.unit,
            status=item.status,
            details=item.details,
        )
        for item in metrics
    ]
    return AnalyticsSnapshotDetail(
        snapshot_id=snapshot.id,
        portfolio_id=snapshot.portfolio_id,
        quality_state=snapshot.quality_state,  # type: ignore[arg-type]
        as_of=snapshot.as_of,
        known_at=snapshot.known_at,
        base_currency=snapshot.base_currency,
        ledger_version=snapshot.ledger_version,
        market_data_version=snapshot.market_data_version,
        methodology_version=snapshot.methodology_version,
        input_hash=snapshot.input_hash,
        metrics={item.metric_code: item.value for item in metric_rows},
        metrics_list=metric_rows,
        positions=[
            ValuationPositionRead(
                instrument_reference=item.instrument_reference,
                quantity=format(Decimal(item.quantity), "f"),
                cost_basis=_decimal_text(item.cost_basis, "INR") or "0.00000000",
                price=(format(Decimal(item.price), "f") if item.price is not None else None),
                price_as_of=item.price_as_of,
                market_value=_decimal_text(item.market_value, "INR"),
                weight=_decimal_text(item.weight, "ratio"),
                status=item.status,
            )
            for item in positions
        ],
        rules=portfolio.rules,
        limitations=list(snapshot.limitations),
    )


@router.post(
    "/portfolios/{portfolio_id}/market-data/datasets",
    response_model=MarketDataSetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_market_data_set(
    portfolio_id: UUID,
    payload: MarketDataSetCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> MarketDataSetRead | dict[str, Any]:
    settings = get_settings()
    portfolio = await _portfolio_or_404(session, context, portfolio_id)
    require_recent_owner(context, settings)
    if max(_utc(payload.cutoff_at), _utc(payload.known_at)) > datetime.now(UTC) + timedelta(
        minutes=5
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "FUTURE_MARKET_DATA",
                "message": "Market-data cutoffs cannot be in the future.",
            },
        )
    endpoint = f"POST:/v1/portfolios/{portfolio_id}/market-data/datasets"
    body = payload.model_dump(mode="json")
    request_hash, replay, _ = await idempotent_replay(
        session, context, endpoint=endpoint, key=idempotency_key, request_body=body
    )
    if replay is not None:
        return replay
    existing = await session.scalar(
        select(MarketDataSet).where(
            MarketDataSet.tenant_id == context.tenant_id,
            MarketDataSet.portfolio_id == portfolio.id,
            MarketDataSet.provider == payload.provider,
            MarketDataSet.provider_version == payload.provider_version,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MARKET_DATA_VERSION_EXISTS",
                "message": "This provider version is already sealed for the portfolio.",
            },
        )
    dataset = MarketDataSet(
        id=uuid4(),
        tenant_id=context.tenant_id,
        portfolio_id=portfolio.id,
        provider=payload.provider,
        provider_version=payload.provider_version,
        rights_basis=payload.rights_basis,
        cutoff_at=payload.cutoff_at,
        known_at=payload.known_at,
        content_hash=canonical_hash(body),
        status="sealed",
        created_by=context.user_id,
    )
    session.add(dataset)
    session.add_all(
        [
            PriceObservation(
                tenant_id=context.tenant_id,
                market_data_set_id=dataset.id,
                instrument_reference=item.instrument_reference.upper(),
                observed_at=item.observed_at,
                known_at=item.known_at,
                close_price=item.close_price,
                currency=item.currency,
                quality=item.quality,
                source_hash=item.source_hash,
            )
            for item in payload.prices
        ]
    )
    session.add_all(
        [
            CorporateAction(
                tenant_id=context.tenant_id,
                market_data_set_id=dataset.id,
                instrument_reference=item.instrument_reference.upper(),
                action_type=item.action_type,
                effective_at=item.effective_at,
                known_at=item.known_at,
                split_factor=item.split_factor,
                cash_amount_per_unit=item.cash_amount_per_unit,
                currency=item.currency,
                source_hash=item.source_hash,
            )
            for item in payload.corporate_actions
        ]
    )
    session.add(
        audit_event(
            context,
            action="market_data.dataset_sealed",
            resource_type="market_data_set",
            resource_id=dataset.id,
            details={
                "provider": payload.provider,
                "price_count": len(payload.prices),
                "corporate_action_count": len(payload.corporate_actions),
                "rights_basis": payload.rights_basis,
            },
        )
    )
    await session.flush()
    response_body = MarketDataSetRead.model_validate(dataset).model_dump(mode="json")
    store_idempotency(
        session,
        context,
        settings,
        endpoint=endpoint,
        key=str(idempotency_key),
        request_hash=request_hash,
        status_code=201,
        response_body=response_body,
    )
    await session.commit()
    return MarketDataSetRead.model_validate(dataset)


def _metric(
    tenant_id: UUID,
    snapshot_id: UUID,
    code: str,
    value: Decimal | None,
    unit: str,
    *,
    details: dict[str, Any] | None = None,
) -> MetricValue:
    return MetricValue(
        tenant_id=tenant_id,
        analytics_snapshot_id=snapshot_id,
        metric_code=code,
        dimension_type="portfolio",
        dimension_id="portfolio",
        value=value,
        unit=unit,
        status="available" if value is not None else "insufficient_data",
        details=details or {},
    )


@router.post(
    "/portfolios/{portfolio_id}/analytics/recompute",
    response_model=AnalyticsSnapshotDetail,
    status_code=status.HTTP_201_CREATED,
)
async def recompute_analytics(
    portfolio_id: UUID,
    payload: AnalyticsRecompute,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> AnalyticsSnapshotDetail | dict[str, Any]:
    settings = get_settings()
    portfolio = await _portfolio_or_404(session, context, portfolio_id)
    _require_analytics_role(context)
    endpoint = f"POST:/v1/portfolios/{portfolio_id}/analytics/recompute"
    body = payload.model_dump(mode="json")
    request_hash, replay, _ = await idempotent_replay(
        session, context, endpoint=endpoint, key=idempotency_key, request_body=body
    )
    if replay is not None:
        return replay
    dataset = await session.scalar(
        select(MarketDataSet).where(
            MarketDataSet.id == payload.market_data_set_id,
            MarketDataSet.tenant_id == context.tenant_id,
            MarketDataSet.portfolio_id == portfolio.id,
        )
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market data not found.")
    if dataset.status != "sealed" or _utc(dataset.known_at) > _utc(payload.known_at):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "MARKET_DATA_NOT_KNOWN_AT_CUTOFF",
                "message": "The sealed market-data version was not available by known_at.",
            },
        )
    if _utc(payload.as_of) > _utc(dataset.cutoff_at) or _utc(payload.known_at) < _utc(
        payload.as_of
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_ANALYTICS_CUTOFF",
                "message": "as_of/known_at exceed the sealed dataset or reverse time.",
            },
        )

    transactions = list(
        await session.scalars(
            select(Transaction)
            .where(
                Transaction.tenant_id == context.tenant_id,
                Transaction.portfolio_id == portfolio.id,
                Transaction.trade_date <= payload.as_of,
                Transaction.recorded_at <= payload.known_at,
            )
            .order_by(Transaction.trade_date, Transaction.recorded_at, Transaction.id)
        )
    )
    prices = list(
        await session.scalars(
            select(PriceObservation).where(
                PriceObservation.tenant_id == context.tenant_id,
                PriceObservation.market_data_set_id == dataset.id,
            )
        )
    )
    actions = list(
        await session.scalars(
            select(CorporateAction).where(
                CorporateAction.tenant_id == context.tenant_id,
                CorporateAction.market_data_set_id == dataset.id,
            )
        )
    )
    protected_cash = Decimal(str((portfolio.rules.get("protected_cash") or {}).get("amount", "0")))
    try:
        valuation = calculate_point_in_time_valuation(
            transactions,
            prices,
            actions,
            as_of=payload.as_of,
            known_at=payload.known_at,
            base_currency=portfolio.base_currency,
            protected_cash=protected_cash,
            max_price_age_days=payload.max_price_age_days,
        )
    except (ValuationInputError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "VALUATION_INPUT_INVALID", "message": str(error)},
        ) from error

    ledger_version = max((int(item.ledger_version or 0) for item in transactions), default=0)
    input_hash = canonical_hash(
        {
            "ledger": [
                {
                    "id": str(item.id),
                    "ledger_version": item.ledger_version,
                    "event_type": item.event_type,
                    "trade_date": item.trade_date,
                    "recorded_at": item.recorded_at,
                    "instrument_reference": item.instrument_reference,
                    "quantity": item.quantity,
                    "price": item.price,
                    "gross_amount": item.gross_amount,
                    "cash_delta": item.cash_delta,
                    "fees": item.fees,
                    "taxes": item.taxes,
                    "currency": item.currency,
                    "reversal_of_id": item.reversal_of_id,
                }
                for item in transactions
            ],
            "market_data_hash": dataset.content_hash,
            "portfolio_version": portfolio.version,
            "portfolio_rules": portfolio.rules,
            "base_currency": portfolio.base_currency,
            "benchmark_code": portfolio.benchmark_code,
            "as_of": payload.as_of,
            "known_at": payload.known_at,
            "methodology_version": METHODOLOGY_VERSION,
            "max_price_age_days": payload.max_price_age_days,
        }
    )
    existing = await session.scalar(
        select(AnalyticsSnapshotRecord).where(
            AnalyticsSnapshotRecord.tenant_id == context.tenant_id,
            AnalyticsSnapshotRecord.portfolio_id == portfolio.id,
            AnalyticsSnapshotRecord.input_hash == input_hash,
        )
    )
    if existing is not None:
        detail = await snapshot_detail(session, portfolio, existing)
        response_body = detail.model_dump(mode="json")
        store_idempotency(
            session,
            context,
            settings,
            endpoint=endpoint,
            key=str(idempotency_key),
            request_hash=request_hash,
            status_code=201,
            response_body=response_body,
        )
        await session.commit()
        return detail

    snapshot_id = uuid4()
    snapshot = AnalyticsSnapshotRecord(
        id=snapshot_id,
        tenant_id=context.tenant_id,
        portfolio_id=portfolio.id,
        market_data_set_id=dataset.id,
        as_of=payload.as_of,
        known_at=payload.known_at,
        ledger_version=ledger_version,
        market_data_version=dataset.provider_version,
        methodology_version=METHODOLOGY_VERSION,
        benchmark_code=portfolio.benchmark_code,
        base_currency=portfolio.base_currency,
        input_hash=input_hash,
        quality_state=valuation["quality_state"],
        limitations=valuation["limitations"],
    )
    session.add(snapshot)
    session.add_all(
        [
            ValuationPosition(
                tenant_id=context.tenant_id,
                analytics_snapshot_id=snapshot_id,
                instrument_reference=row["instrument_reference"],
                quantity=row["quantity"],
                cost_basis=row["cost_basis"],
                price=row["price"],
                price_as_of=row["price_as_of"],
                market_value=row["market_value"],
                weight=row["weight"],
                status=row["status"],
            )
            for row in valuation["positions"]
        ]
    )

    previous_snapshots = list(
        await session.scalars(
            select(AnalyticsSnapshotRecord)
            .where(
                AnalyticsSnapshotRecord.tenant_id == context.tenant_id,
                AnalyticsSnapshotRecord.portfolio_id == portfolio.id,
                AnalyticsSnapshotRecord.as_of < payload.as_of,
                AnalyticsSnapshotRecord.known_at <= payload.known_at,
                AnalyticsSnapshotRecord.quality_state == "trusted",
                AnalyticsSnapshotRecord.methodology_version == METHODOLOGY_VERSION,
            )
            .order_by(
                AnalyticsSnapshotRecord.as_of,
                AnalyticsSnapshotRecord.known_at.desc(),
                AnalyticsSnapshotRecord.created_at.desc(),
            )
        )
    )
    # More than one immutable method/input version may exist for an economic date. Use the latest
    # version that was actually known by this run's information cutoff.
    prior_by_as_of: dict[datetime, AnalyticsSnapshotRecord] = {}
    for previous in previous_snapshots:
        prior_by_as_of.setdefault(_utc(previous.as_of), previous)
    historical_points: list[SnapshotPoint] = []
    for previous in prior_by_as_of.values():
        previous_metrics = list(
            await session.scalars(
                select(MetricValue).where(
                    MetricValue.tenant_id == context.tenant_id,
                    MetricValue.analytics_snapshot_id == previous.id,
                    MetricValue.metric_code.in_(["current_value", "external_cash_flow"]),
                )
            )
        )
        by_code = {item.metric_code: item.value for item in previous_metrics}
        if by_code.get("current_value") is not None:
            historical_points.append(
                SnapshotPoint(
                    as_of=previous.as_of,
                    total_value=Decimal(by_code["current_value"]),
                    external_flow=Decimal(by_code.get("external_cash_flow") or 0),
                )
            )
    previous_as_of = _utc(historical_points[-1].as_of) if historical_points else None
    current_external_flow = sum(
        (
            amount
            for flow_at, amount in valuation["external_flows"]
            if previous_as_of is None or _utc(flow_at) > previous_as_of
        ),
        Decimal(0),
    )
    historical_points.append(
        SnapshotPoint(
            as_of=payload.as_of,
            total_value=valuation["total_value"],
            external_flow=current_external_flow,
        )
    )
    risk = calculate_return_and_risk(historical_points)
    xirr_flows = [
        (flow_at, -amount) for flow_at, amount in valuation["external_flows"] if amount != 0
    ]
    xirr_flows.append((payload.as_of, valuation["total_value"]))
    money_weighted_return = calculate_xirr(xirr_flows)

    metric_rows = [
        _metric(context.tenant_id, snapshot_id, "current_value", valuation["total_value"], "INR"),
        _metric(context.tenant_id, snapshot_id, "cash", valuation["cash_balance"], "INR"),
        _metric(
            context.tenant_id,
            snapshot_id,
            "available_cash",
            valuation["available_cash"],
            "INR",
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "protected_cash",
            valuation["protected_cash"],
            "INR",
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "net_invested_capital",
            valuation["net_invested_capital"],
            "INR",
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "securities_market_value",
            valuation["securities_market_value"],
            "INR",
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "realized_pnl",
            valuation["realized_pnl"],
            "INR",
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "external_cash_flow",
            current_external_flow,
            "INR",
            details={"flow_timing": "end_of_period"},
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "price_coverage",
            valuation["price_coverage"],
            "ratio",
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "time_weighted_return",
            risk["time_weighted_return"],
            "ratio",
            details={"flow_timing": "end_of_period", "annualization_periods": 252},
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "money_weighted_return",
            money_weighted_return,
            "ratio",
            details={"day_count": "actual/365.25"},
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "volatility",
            risk["volatility"],
            "ratio",
            details={"annualization_periods": 252},
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "downside_deviation",
            risk["downside_deviation"],
            "ratio",
            details={"annualization_periods": 252, "target_return": "0"},
        ),
        _metric(
            context.tenant_id,
            snapshot_id,
            "max_drawdown",
            risk["max_drawdown"],
            "ratio",
        ),
    ]
    session.add_all(metric_rows)

    evidence_id = uuid4()
    available_claims = [
        {
            "claim_key": item.metric_code,
            "statement": f"Deterministic metric {item.metric_code}.",
            "numeric_value": _decimal_text(item.value, item.unit),
            "unit": item.unit,
        }
        for item in metric_rows
        if item.value is not None
    ]
    evidence = EvidenceItem(
        id=evidence_id,
        tenant_id=context.tenant_id,
        portfolio_id=portfolio.id,
        source_type="analytics_snapshot",
        title=f"Deterministic analytics snapshot {payload.as_of.isoformat()}",
        publisher="Portfolio Intelligence",
        published_at=payload.known_at,
        retrieved_at=payload.known_at,
        known_at=payload.known_at,
        content_hash=canonical_hash({"snapshot_id": str(snapshot_id), "input_hash": input_hash}),
        locator={"resource": f"/v1/analytics/{snapshot_id}/metrics"},
        claims=available_claims,
        quality="verified",
        rights_basis="internal",
        cutoff_eligible=True,
        created_by=context.user_id,
    )
    session.add(evidence)
    session.add_all(
        [
            EvidenceLink(
                tenant_id=context.tenant_id,
                from_type="analytics_snapshot",
                from_id=snapshot_id,
                evidence_item_id=evidence_id,
                relation="supports",
                claim_key=item["claim_key"],
            )
            for item in available_claims
        ]
    )
    session.add(
        audit_event(
            context,
            action="analytics.snapshot_created",
            resource_type="analytics_snapshot",
            resource_id=snapshot_id,
            details={
                "ledger_version": ledger_version,
                "market_data_version": dataset.provider_version,
                "methodology_version": METHODOLOGY_VERSION,
                "quality_state": valuation["quality_state"],
            },
        )
    )
    await session.flush()
    detail = await snapshot_detail(session, portfolio, snapshot)
    response_body = detail.model_dump(mode="json")
    store_idempotency(
        session,
        context,
        settings,
        endpoint=endpoint,
        key=str(idempotency_key),
        request_hash=request_hash,
        status_code=201,
        response_body=response_body,
    )
    await session.commit()
    return detail


@router.get("/analytics/{snapshot_id}/metrics", response_model=AnalyticsSnapshotDetail)
async def get_analytics_snapshot(
    snapshot_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> AnalyticsSnapshotDetail:
    snapshot = await session.scalar(
        select(AnalyticsSnapshotRecord).where(
            AnalyticsSnapshotRecord.id == snapshot_id,
            AnalyticsSnapshotRecord.tenant_id == context.tenant_id,
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    portfolio = await _portfolio_or_404(session, context, snapshot.portfolio_id)
    return await snapshot_detail(session, portfolio, snapshot)


@router.post(
    "/portfolios/{portfolio_id}/scenarios",
    response_model=ScenarioRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    portfolio_id: UUID,
    payload: ScenarioCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> ScenarioRead | dict[str, Any]:
    settings = get_settings()
    portfolio = await _portfolio_or_404(session, context, portfolio_id)
    _require_analytics_role(context)
    endpoint = f"POST:/v1/portfolios/{portfolio_id}/scenarios"
    body = payload.model_dump(mode="json")
    request_hash, replay, _ = await idempotent_replay(
        session, context, endpoint=endpoint, key=idempotency_key, request_body=body
    )
    if replay is not None:
        return replay
    snapshot = await session.scalar(
        select(AnalyticsSnapshotRecord).where(
            AnalyticsSnapshotRecord.id == payload.base_snapshot_id,
            AnalyticsSnapshotRecord.tenant_id == context.tenant_id,
            AnalyticsSnapshotRecord.portfolio_id == portfolio.id,
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    if snapshot.quality_state != "trusted":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "TRUSTED_SNAPSHOT_REQUIRED",
                "message": "A trusted valuation snapshot is required for a scenario.",
            },
        )
    positions = list(
        await session.scalars(
            select(ValuationPosition).where(
                ValuationPosition.tenant_id == context.tenant_id,
                ValuationPosition.analytics_snapshot_id == snapshot.id,
            )
        )
    )
    cash_metric = await session.scalar(
        select(MetricValue).where(
            MetricValue.tenant_id == context.tenant_id,
            MetricValue.analytics_snapshot_id == snapshot.id,
            MetricValue.metric_code == "cash",
        )
    )
    if cash_metric is None or cash_metric.value is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "CASH_METRIC_REQUIRED", "message": "Cash is unavailable."},
        )
    protected = Decimal(str((portfolio.rules.get("protected_cash") or {}).get("amount", "0")))
    try:
        result = run_market_stress_scenario(
            [
                {
                    "instrument_reference": item.instrument_reference,
                    "market_value": item.market_value,
                }
                for item in positions
            ],
            cash_balance=Decimal(cash_metric.value),
            protected_cash=protected,
            price_shocks={key: Decimal(value) for key, value in payload.price_shocks.items()},
            allocations={key: Decimal(value) for key, value in payload.allocations.items()},
            max_position_weight_percent=Decimal(
                str(portfolio.rules.get("max_position_weight_percent", "25"))
            ),
            equal_weighting_allowed=bool(portfolio.rules.get("equal_weighting_allowed", False)),
        )
    except ValuationInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "SCENARIO_INPUT_INVALID", "message": str(error)},
        ) from error
    scenario = ScenarioRun(
        id=uuid4(),
        tenant_id=context.tenant_id,
        portfolio_id=portfolio.id,
        created_by=context.user_id,
        base_snapshot_id=snapshot.id,
        name=payload.name,
        status="blocked" if result["status"] == "blocked" else "completed",
        assumptions={
            "price_shocks": {key: str(value) for key, value in payload.price_shocks.items()},
            "allocations": {key: str(value) for key, value in payload.allocations.items()},
            "taxes_included": False,
        },
        results={key: value for key, value in result.items() if key != "constraints"},
        constraint_results=result["constraints"],
        engine_version=SCENARIO_ENGINE_VERSION,
        can_execute=False,
        input_hash=canonical_hash(
            {
                "payload": body,
                "snapshot_input_hash": snapshot.input_hash,
                "engine": SCENARIO_ENGINE_VERSION,
            }
        ),
    )
    session.add(scenario)
    session.add(
        audit_event(
            context,
            action="scenario.created",
            resource_type="scenario_run",
            resource_id=scenario.id,
            details={"status": scenario.status, "constraint_count": len(result["constraints"])},
        )
    )
    await session.flush()
    response_body = ScenarioRead.model_validate(scenario).model_dump(mode="json")
    store_idempotency(
        session,
        context,
        settings,
        endpoint=endpoint,
        key=str(idempotency_key),
        request_hash=request_hash,
        status_code=201,
        response_body=response_body,
    )
    await session.commit()
    return ScenarioRead.model_validate(scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioRead)
async def get_scenario(
    scenario_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> ScenarioRun:
    scenario = await session.scalar(
        select(ScenarioRun).where(
            ScenarioRun.id == scenario_id,
            ScenarioRun.tenant_id == context.tenant_id,
        )
    )
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    return scenario


@router.post(
    "/portfolios/{portfolio_id}/evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_evidence(
    portfolio_id: UUID,
    payload: EvidenceCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> EvidenceRead | dict[str, Any]:
    settings = get_settings()
    portfolio = await _portfolio_or_404(session, context, portfolio_id)
    require_recent_owner(context, settings)
    if payload.known_at > datetime.now(UTC) + timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "FUTURE_EVIDENCE", "message": "Evidence known_at is in the future."},
        )
    allowed_locator_keys = {
        "page",
        "section",
        "field",
        "provider_record_id",
        "object_key",
        "url_hash",
    }
    if set(payload.locator) - allowed_locator_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "EVIDENCE_LOCATOR_INVALID",
                "message": "Only non-secret structured locator fields are accepted.",
            },
        )
    endpoint = f"POST:/v1/portfolios/{portfolio_id}/evidence"
    body = payload.model_dump(mode="json")
    request_hash, replay, _ = await idempotent_replay(
        session, context, endpoint=endpoint, key=idempotency_key, request_body=body
    )
    if replay is not None:
        return replay
    existing = await session.scalar(
        select(EvidenceItem).where(
            EvidenceItem.tenant_id == context.tenant_id,
            EvidenceItem.portfolio_id == portfolio.id,
            EvidenceItem.content_hash == payload.content_hash,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EVIDENCE_EXISTS", "message": "Evidence is already registered."},
        )
    item = EvidenceItem(
        id=uuid4(),
        tenant_id=context.tenant_id,
        portfolio_id=portfolio.id,
        source_type=payload.source_type,
        title=payload.title,
        publisher=payload.publisher,
        published_at=payload.published_at,
        retrieved_at=payload.retrieved_at,
        known_at=payload.known_at,
        content_hash=payload.content_hash,
        locator=payload.locator,
        claims=[claim.model_dump(mode="json") for claim in payload.claims],
        quality=payload.quality,
        rights_basis=payload.rights_basis,
        cutoff_eligible=payload.cutoff_eligible,
        created_by=context.user_id,
    )
    session.add(item)
    session.add(
        audit_event(
            context,
            action="evidence.accepted",
            resource_type="evidence_item",
            resource_id=item.id,
            details={
                "source_type": item.source_type,
                "quality": item.quality,
                "rights_basis": item.rights_basis,
                "claim_count": len(item.claims),
            },
        )
    )
    await session.flush()
    response_body = EvidenceRead.model_validate(item).model_dump(mode="json")
    store_idempotency(
        session,
        context,
        settings,
        endpoint=endpoint,
        key=str(idempotency_key),
        request_hash=request_hash,
        status_code=201,
        response_body=response_body,
    )
    await session.commit()
    return EvidenceRead.model_validate(item)


@router.get("/evidence/{evidence_id}", response_model=EvidenceRead)
async def get_evidence(
    evidence_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> EvidenceItem:
    item = await session.scalar(
        select(EvidenceItem).where(
            EvidenceItem.id == evidence_id,
            EvidenceItem.tenant_id == context.tenant_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    return item


@router.post("/portfolios/{portfolio_id}/agent-runs", response_model=AgentRunRead)
async def start_agent_run(
    portfolio_id: UUID,
    payload: AgentRunStart,
    x_agent_service_token: str | None = Header(default=None, alias="X-Agent-Service-Token"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> AgentRunRecord:
    _require_agent_service(x_agent_service_token)
    portfolio = await _portfolio_or_404(session, context, portfolio_id)
    existing = await session.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.tenant_id == context.tenant_id,
            or_(
                AgentRunRecord.id == payload.run_id,
                AgentRunRecord.request_id == payload.request_id,
            ),
        )
    )
    if existing is not None:
        if (
            existing.id != payload.run_id
            or existing.portfolio_id != portfolio.id
            or existing.thread_id != payload.thread_id
            or existing.question_hash != payload.question_hash
            or _utc(existing.as_of) != _utc(payload.as_of)
            or _utc(existing.known_at) != _utc(payload.known_at)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "AGENT_RUN_CONFLICT",
                    "message": "Run or request ID was reused with different immutable inputs.",
                },
            )
        return existing
    run = AgentRunRecord(
        id=payload.run_id,
        tenant_id=context.tenant_id,
        portfolio_id=portfolio.id,
        thread_id=payload.thread_id,
        initiated_by=context.user_id,
        request_id=payload.request_id,
        question_hash=payload.question_hash,
        as_of=payload.as_of,
        known_at=payload.known_at,
        graph_version=payload.graph_version,
        prompt_bundle_version=payload.prompt_bundle_version,
        model_route=payload.model_route,
        policy_version=payload.policy_version,
        allowed_tools=list(payload.allowed_tools),
        checkpoint_thread_id=payload.checkpoint_thread_id,
        state="running",
        can_execute=False,
    )
    session.add(run)
    session.add(
        audit_event(
            context,
            action="agent_run.started",
            resource_type="agent_run",
            resource_id=run.id,
            details={"graph_version": run.graph_version, "tool_count": len(run.allowed_tools)},
        )
    )
    await session.commit()
    return run


@router.post("/agent-runs/{run_id}/complete", response_model=AgentRunRead)
async def complete_agent_run(
    run_id: UUID,
    payload: AgentRunComplete,
    x_agent_service_token: str | None = Header(default=None, alias="X-Agent-Service-Token"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> AgentRunRecord:
    _require_agent_service(x_agent_service_token)
    run = await session.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.id == run_id,
            AgentRunRecord.tenant_id == context.tenant_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")
    if run.state != "running":
        if (
            run.state == payload.state
            and run.result_hash == payload.answer_hash
            and run.error_code == payload.error_code
        ):
            return run
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "AGENT_RUN_TERMINAL", "message": "Agent run is already terminal."},
        )
    evidence_by_id: dict[str, dict[str, Any]] = {}
    if payload.citations:
        eligible_context = await build_agent_context(
            run.portfolio_id,
            _utc(run.as_of),
            context,
            session,
        )
        eligible_evidence = eligible_context.get("evidence")
        if not isinstance(eligible_evidence, list):
            eligible_evidence = []
        evidence_by_id = {
            str(item["id"]): item
            for item in eligible_evidence
            if isinstance(item, dict) and "id" in item
        }

    persistent_citations: list[tuple[str, EvidenceItem]] = []
    validated_citations: list[dict[str, str]] = []
    for citation in payload.citations:
        context_item = evidence_by_id.get(citation.evidence_id)
        if context_item is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "EVIDENCE_CUTOFF_FAILED",
                    "message": "Citation was not present in the cutoff-safe run context.",
                },
            )
        matching_context_claim = next(
            (
                claim
                for claim in context_item.get("claims", [])
                if claim.get("claim_key") == citation.claim_key
                and str(claim.get("numeric_value")) == citation.value
                and claim.get("unit") == citation.unit
            ),
            None,
        )
        expected_as_of = context_item.get("as_of")
        expected_locator = str(context_item.get("uri") or "")
        if (
            matching_context_claim is None
            or not isinstance(expected_as_of, datetime)
            or _utc(citation.as_of) != _utc(expected_as_of)
            or citation.locator != expected_locator
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "NUMERIC_CITATION_MISMATCH",
                    "message": "Citation does not match the cutoff-safe claim and locator.",
                },
            )
        validated_citations.append(
            {
                "claim_key": citation.claim_key,
                "evidence_id": citation.evidence_id,
                "value": str(matching_context_claim["numeric_value"]),
                "unit": str(matching_context_claim["unit"]),
                "as_of": _utc(expected_as_of).isoformat(),
                "locator": expected_locator,
            }
        )
        try:
            evidence_uuid = UUID(citation.evidence_id)
        except ValueError:
            if citation.evidence_id not in {
                "ledger:snapshot",
                "monitor:snapshot",
                "rule:portfolio",
            }:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail={
                        "code": "EVIDENCE_ID_INVALID",
                        "message": "Citation evidence ID is not registered.",
                    },
                ) from None
            continue
        evidence = await session.scalar(
            select(EvidenceItem).where(
                EvidenceItem.id == evidence_uuid,
                EvidenceItem.tenant_id == context.tenant_id,
                EvidenceItem.portfolio_id == run.portfolio_id,
                EvidenceItem.cutoff_eligible.is_(True),
                EvidenceItem.known_at <= run.known_at,
            )
        )
        if evidence is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "EVIDENCE_CUTOFF_FAILED",
                    "message": "Citation was unavailable at the run cutoff.",
                },
            )
        persistent_citations.append((citation.claim_key, evidence))

    computed_coverage = Decimal(1)
    if payload.state == "completed":
        assert payload.answer is not None and payload.answer_hash is not None
        if hashlib.sha256(payload.answer.encode("utf-8")).hexdigest() != payload.answer_hash:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "ANSWER_HASH_MISMATCH",
                    "message": "The terminal answer does not match its integrity hash.",
                },
            )
        computed_coverage, missing_numbers = numeric_citation_coverage(
            payload.answer,
            validated_citations,
        )
        if computed_coverage != Decimal(1):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "NUMERIC_CITATION_GATE_FAILED",
                    "message": "Every numeric claim must resolve to cutoff-eligible evidence.",
                    "missing_count": len(missing_numbers),
                },
            )
    if payload.numeric_citation_coverage != computed_coverage:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "NUMERIC_CITATION_COVERAGE_MISMATCH",
                "message": "Agent-reported coverage does not match Core verification.",
            },
        )

    run.state = payload.state
    run.intent = payload.intent
    run.stages = list(payload.stages)
    run.citations = validated_citations
    run.policy = {
        **payload.policy,
        "numeric_citation_coverage": str(computed_coverage),
    }
    run.result_hash = payload.answer_hash
    run.error_code = payload.error_code
    run.completed_at = datetime.now(UTC)
    session.add_all(
        [
            AgentRunStep(
                tenant_id=context.tenant_id,
                agent_run_id=run.id,
                node_name=stage_name,
                attempt=1,
                state=payload.state,
                public_summary=stage_name.replace("_", " ")[:255],
            )
            for stage_name in dict.fromkeys(payload.stages)
        ]
    )
    session.add_all(
        [
            AgentRunEvidence(
                tenant_id=context.tenant_id,
                agent_run_id=run.id,
                evidence_item_id=evidence.id,
                claim_key=claim_key,
                relation="supports",
            )
            for claim_key, evidence in persistent_citations
        ]
    )
    if payload.proposal is not None:
        session.add(
            AgentProposalRecord(
                tenant_id=context.tenant_id,
                portfolio_id=run.portfolio_id,
                run_id=run.id,
                proposal=payload.proposal.model_dump(mode="json"),
                can_execute=False,
            )
        )
    session.add(
        audit_event(
            context,
            action=f"agent_run.{payload.state}",
            resource_type="agent_run",
            resource_id=run.id,
            details={
                "stage_count": len(payload.stages),
                "citation_count": len(payload.citations),
                "policy_decision": str(payload.policy.get("decision", "unavailable")),
            },
        )
    )
    await session.commit()
    return run


@router.get("/agent-runs/{run_id}", response_model=AgentRunRead)
async def get_agent_run(
    run_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> AgentRunRecord:
    run = await session.scalar(
        select(AgentRunRecord).where(
            AgentRunRecord.id == run_id,
            AgentRunRecord.tenant_id == context.tenant_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found.")
    return run
