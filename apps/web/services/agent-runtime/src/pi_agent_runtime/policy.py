from __future__ import annotations

from datetime import timezone

from .models import (
    AnalysisRunRequest,
    HoldingSnapshot,
    PolicyCheck,
    SymbolResult,
    utc_now,
)


def readiness_checks(request: AnalysisRunRequest) -> list[PolicyCheck]:
    checks: list[PolicyCheck] = []
    selected = request.selected_symbols or [
        holding.symbol for holding in request.holdings
    ]
    holdings = {holding.symbol: holding for holding in request.holdings}

    for symbol in selected:
        holding = holdings[symbol]
        if not holding.analysis_symbol:
            checks.append(PolicyCheck(
                code="instrument_mapping_missing",
                severity="block",
                symbol=symbol,
                message=(
                    f"{symbol} does not have a confirmed TradingAgents "
                    "market-data symbol."
                ),
            ))

        observed = holding.price_as_of
        if observed.tzinfo is None:
            observed = observed.replace(
                tzinfo=timezone.utc  # noqa: UP017 - Python 3.10 runtime
            )
        age_minutes = max(0, (utc_now() - observed).total_seconds() / 60)
        if age_minutes > request.policy.data_max_age_minutes:
            checks.append(PolicyCheck(
                code="price_snapshot_stale",
                severity="block",
                symbol=symbol,
                message=(
                    f"{symbol} price is {age_minutes:.0f} minutes old; "
                    "refresh before analysis."
                ),
            ))

    total_allocation = sum(holding.allocation_percent for holding in request.holdings)
    if not 99 <= total_allocation <= 101:
        checks.append(PolicyCheck(
            code="allocation_reconciliation_failed",
            severity="block",
            message=(
                f"Portfolio allocation totals {total_allocation:.2f}%, outside the "
                "99–101% reconciliation band."
            ),
        ))

    if request.policy.max_single_deployment_inr > request.policy.deployable_cash_inr:
        checks.append(PolicyCheck(
            code="deployment_exceeds_cash",
            severity="block",
            message="Maximum single deployment exceeds deployable cash.",
        ))

    checks.append(PolicyCheck(
        code="human_confirmation_required",
        severity="pass",
        message=(
            "Analysis can produce a proposal, but every order requires explicit "
            "human confirmation."
        ),
    ))
    return checks


def result_policy_checks(
    request: AnalysisRunRequest,
    holding: HoldingSnapshot,
    result: SymbolResult,
) -> list[PolicyCheck]:
    checks: list[PolicyCheck] = []
    position_cap_reached = (
        holding.allocation_percent >= request.policy.max_position_weight_percent
    )
    if position_cap_reached and result.trader_action == "Buy":
        checks.append(PolicyCheck(
            code="position_cap",
            severity="block",
            symbol=holding.symbol,
            message=(
                f"Buy proposal blocked: {holding.symbol} is already "
                f"{holding.allocation_percent:.2f}% versus the "
                f"{request.policy.max_position_weight_percent:.2f}% policy cap."
            ),
        ))
    else:
        checks.append(PolicyCheck(
            code="position_cap",
            severity="pass",
            symbol=holding.symbol,
            message=f"Current weight is {holding.allocation_percent:.2f}%.",
        ))

    checks.append(PolicyCheck(
        code="execution_disabled",
        severity="pass",
        symbol=holding.symbol,
        message="The runtime cannot place brokerage orders.",
    ))
    return checks


def is_blocked(checks: list[PolicyCheck]) -> bool:
    return any(check.severity == "block" for check in checks)
