from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from portfolio_api.services.ledger import (
    PERCENT_QUANTUM,
    ZERO,
    LedgerInvariantError,
    decimal_text,
)

RATE_QUANTUM = Decimal("0.000000000001")
METHODOLOGY_VERSION = "spi-valuation-risk/1.0.0"
SCENARIO_ENGINE_VERSION = "spi-market-stress/1.0.0"


class ValuationInputError(ValueError):
    """Raised when point-in-time inputs cannot produce a defensible valuation."""


@dataclass
class PositionState:
    quantity: Decimal = ZERO
    cost_basis: Decimal = ZERO


@dataclass(frozen=True)
class SnapshotPoint:
    as_of: datetime
    total_value: Decimal
    external_flow: Decimal = ZERO


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _decimal(value: object | None, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return Decimal(str(value))


def _event_cash_delta(event: Any, fallback: Decimal) -> Decimal:
    value = getattr(event, "cash_delta", None)
    return _decimal(value, fallback) if value is not None else fallback


def calculate_point_in_time_valuation(
    transactions: Iterable[Any],
    prices: Iterable[Any],
    corporate_actions: Iterable[Any],
    *,
    as_of: datetime,
    known_at: datetime,
    base_currency: str,
    protected_cash: Decimal,
    max_price_age_days: int = 7,
) -> dict[str, Any]:
    """Roll the immutable ledger forward and value it using only cutoff-eligible inputs.

    `as_of` controls economic time. `known_at` controls information time. A row recorded or
    learned after `known_at` is excluded even when its economic date is earlier, preventing
    revised data from leaking into historical runs.
    """

    as_of_utc = _utc(as_of)
    known_at_utc = _utc(known_at)
    if known_at_utc < as_of_utc:
        raise ValuationInputError("known_at cannot be earlier than as_of")
    if max_price_age_days < 0:
        raise ValuationInputError("max_price_age_days cannot be negative")

    timeline: list[tuple[datetime, int, datetime, Any]] = []
    eligible_transactions: list[Any] = []
    for event in transactions:
        effective_at = _utc(event.trade_date)
        recorded_at = _utc(event.recorded_at)
        if effective_at <= as_of_utc and recorded_at <= known_at_utc:
            eligible_transactions.append(event)
            timeline.append((effective_at, 0, recorded_at, event))

    eligible_actions: list[Any] = []
    for action in corporate_actions:
        effective_at = _utc(action.effective_at)
        action_known_at = _utc(action.known_at)
        if effective_at <= as_of_utc and action_known_at <= known_at_utc:
            eligible_actions.append(action)
            timeline.append((effective_at, 1, action_known_at, action))

    timeline.sort(key=lambda row: (row[0], row[1], row[2], str(getattr(row[3], "id", ""))))
    positions: dict[str, PositionState] = {}
    cash = ZERO
    net_invested = ZERO
    realized_pnl = ZERO
    external_flows: list[tuple[datetime, Decimal]] = []
    limitations: list[str] = []

    for effective_at, kind, _, item in timeline:
        if kind == 1:
            instrument = str(item.instrument_reference)
            position = positions.setdefault(instrument, PositionState())
            if item.action_type == "split":
                factor = _decimal(item.split_factor)
                if factor <= ZERO:
                    raise ValuationInputError(f"invalid split factor for {instrument}")
                position.quantity *= factor
            elif item.action_type == "cash_dividend":
                if item.currency != base_currency:
                    limitations.append(
                        f"{instrument} dividend currency {item.currency} is unsupported."
                    )
                    continue
                amount = _decimal(item.cash_amount_per_unit)
                if amount < ZERO:
                    raise ValuationInputError(f"negative dividend for {instrument}")
                cash += position.quantity * amount
            else:
                limitations.append(
                    f"Unsupported corporate action {item.action_type} for {instrument}."
                )
            continue

        event = item
        amount = _decimal(event.gross_amount)
        instrument = event.instrument_reference
        event_type = event.event_type
        if event.currency != base_currency:
            raise ValuationInputError(
                f"ledger currency {event.currency} does not match {base_currency}"
            )
        if event_type in {"buy", "sell"}:
            if not instrument or event.quantity is None or event.price is None:
                raise LedgerInvariantError(
                    "security events require instrument, quantity, and price"
                )
            quantity = _decimal(event.quantity)
            if quantity <= ZERO:
                raise LedgerInvariantError("security quantity must be positive")
            position = positions.setdefault(str(instrument), PositionState())
            if event_type == "buy":
                change = _event_cash_delta(event, -amount)
                position.quantity += quantity
                position.cost_basis += -change
                cash += change
            else:
                if quantity > position.quantity:
                    raise LedgerInvariantError(
                        f"sell quantity exceeds point-in-time position for {instrument}"
                    )
                average_cost = position.cost_basis / position.quantity
                released_cost = average_cost * quantity
                change = _event_cash_delta(event, amount)
                position.quantity -= quantity
                position.cost_basis -= released_cost
                realized_pnl += change - released_cost
                cash += change
        elif event_type in {"transfer_in", "transfer_out"}:
            if not instrument or event.quantity is None or event.price is None:
                raise LedgerInvariantError(
                    "security transfers require instrument, quantity, and price"
                )
            quantity = _decimal(event.quantity)
            basis = quantity * _decimal(event.price)
            position = positions.setdefault(str(instrument), PositionState())
            if event_type == "transfer_in":
                position.quantity += quantity
                position.cost_basis += basis
                net_invested += basis
                external_flows.append((effective_at, basis))
            else:
                if quantity > position.quantity:
                    raise LedgerInvariantError(
                        f"transfer quantity exceeds point-in-time position for {instrument}"
                    )
                average_cost = position.cost_basis / position.quantity
                released_cost = average_cost * quantity
                position.quantity -= quantity
                position.cost_basis -= released_cost
                # A security leaving the portfolio is an external flow at the value published on
                # the transfer event, not at its historical cost basis.
                net_invested -= basis
                external_flows.append((effective_at, -basis))
        elif event_type == "cash_deposit":
            change = _event_cash_delta(event, amount)
            cash += change
            net_invested += change
            external_flows.append((effective_at, change))
        elif event_type == "cash_withdrawal":
            change = _event_cash_delta(event, -amount)
            if -change > cash:
                raise LedgerInvariantError("cash withdrawal exceeds point-in-time cash")
            cash += change
            net_invested += change
            external_flows.append((effective_at, change))
        elif event_type in {"dividend", "dividend_cash"}:
            cash += _event_cash_delta(event, amount)
        elif event_type == "fee":
            cash += _event_cash_delta(event, -amount)
            realized_pnl -= amount
        elif event_type == "price_mark":
            # R2 valuations deliberately ignore ledger price marks. Only the sealed market-data
            # version may supply valuation prices.
            continue
        else:
            raise LedgerInvariantError(f"unsupported ledger event type: {event_type}")

    selected_prices: dict[str, Any] = {}
    for price in prices:
        observed_at = _utc(price.observed_at)
        price_known_at = _utc(price.known_at)
        if observed_at > as_of_utc or price_known_at > known_at_utc:
            continue
        instrument = str(price.instrument_reference)
        current = selected_prices.get(instrument)
        if current is None or (
            observed_at,
            price_known_at,
            str(getattr(price, "source_hash", "")),
        ) > (
            _utc(current.observed_at),
            _utc(current.known_at),
            str(getattr(current, "source_hash", "")),
        ):
            selected_prices[instrument] = price

    securities_value = ZERO
    rows: list[dict[str, Any]] = []
    missing_prices = 0
    stale_prices = 0
    active_positions = [item for item in positions.items() if item[1].quantity != ZERO]
    for instrument, position in sorted(active_positions):
        price_row = selected_prices.get(instrument)
        price_value: Decimal | None = None
        price_as_of: datetime | None = None
        status = "valued"
        if price_row is None:
            missing_prices += 1
            status = "missing_price"
            limitations.append(f"{instrument} has no cutoff-eligible price.")
        elif price_row.currency != base_currency:
            missing_prices += 1
            status = "currency_mismatch"
            limitations.append(
                f"{instrument} price currency {price_row.currency} does not match {base_currency}."
            )
        else:
            price_value = _decimal(price_row.close_price)
            if price_value <= ZERO:
                raise ValuationInputError(f"non-positive price for {instrument}")
            price_as_of = _utc(price_row.observed_at)
            if as_of_utc - price_as_of > timedelta(days=max_price_age_days):
                stale_prices += 1
                status = "stale_price"
                limitations.append(f"{instrument} price is older than {max_price_age_days} day(s).")

        market_value = position.quantity * price_value if price_value is not None else None
        if market_value is not None:
            securities_value += market_value
        rows.append(
            {
                "instrument_reference": instrument,
                "quantity": position.quantity,
                "cost_basis": position.cost_basis,
                "price": price_value,
                "price_as_of": price_as_of,
                "market_value": market_value,
                "weight": None,
                "status": status,
            }
        )

    total_value = cash + securities_value
    if total_value > ZERO:
        for row in rows:
            if row["market_value"] is not None:
                row["weight"] = _decimal(row["market_value"]) / total_value

    position_count = len(active_positions)
    coverage = (
        Decimal(position_count - missing_prices) / Decimal(position_count)
        if position_count
        else Decimal(1)
    )
    if not eligible_transactions:
        quality_state = "partial"
        limitations.append("No cutoff-eligible published ledger event exists.")
    elif missing_prices:
        quality_state = "partial"
    elif stale_prices:
        quality_state = "stale"
    elif any(item.startswith("Unsupported corporate action") for item in limitations):
        quality_state = "needs_review"
    else:
        quality_state = "trusted"
    if cash < protected_cash:
        limitations.append("Published cash is below the protected reserve.")

    return {
        "as_of": as_of_utc,
        "known_at": known_at_utc,
        "cash_balance": cash,
        "available_cash": max(ZERO, cash - protected_cash),
        "protected_cash": protected_cash,
        "net_invested_capital": net_invested,
        "securities_market_value": securities_value,
        "total_value": total_value,
        "realized_pnl": realized_pnl,
        "positions": rows,
        "external_flows": external_flows,
        "price_coverage": coverage,
        "quality_state": quality_state,
        "limitations": list(dict.fromkeys(limitations)),
    }


def calculate_return_and_risk(points: Iterable[SnapshotPoint]) -> dict[str, Decimal | None]:
    """Calculate deterministic chain-linked return and risk from ordered valuation snapshots.

    External flows use an end-of-period convention: `(end - flow) / start - 1`.
    Daily observations are annualized with 252 periods. Insufficient series return `None`.
    """

    ordered = sorted(points, key=lambda point: _utc(point.as_of))
    returns: list[Decimal] = []
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous.total_value <= ZERO:
            continue
        returns.append(
            (current.total_value - current.external_flow) / previous.total_value - Decimal(1)
        )
    if not returns:
        return {
            "time_weighted_return": None,
            "volatility": None,
            "downside_deviation": None,
            "max_drawdown": None,
        }

    linked = Decimal(1)
    wealth = Decimal(1)
    peak = Decimal(1)
    max_drawdown = ZERO
    for rate in returns:
        linked *= Decimal(1) + rate
        wealth *= Decimal(1) + rate
        peak = max(peak, wealth)
        if peak > ZERO:
            max_drawdown = min(max_drawdown, wealth / peak - Decimal(1))

    volatility: Decimal | None = None
    downside: Decimal | None = None
    if len(returns) >= 2:
        with localcontext() as context:
            context.prec = 34
            mean = sum(returns, ZERO) / Decimal(len(returns))
            variance = sum((value - mean) ** 2 for value in returns) / Decimal(len(returns) - 1)
            volatility = variance.sqrt() * Decimal(252).sqrt()
            downside_variance = sum(min(value, ZERO) ** 2 for value in returns) / Decimal(
                len(returns)
            )
            downside = downside_variance.sqrt() * Decimal(252).sqrt()

    return {
        "time_weighted_return": linked - Decimal(1),
        "volatility": volatility,
        "downside_deviation": downside,
        "max_drawdown": max_drawdown,
    }


def calculate_xirr(cash_flows: Iterable[tuple[datetime, Decimal]]) -> Decimal | None:
    """Return a deterministic annual money-weighted return or `None` when undefined."""

    flows = sorted(
        ((_utc(date), Decimal(amount)) for date, amount in cash_flows), key=lambda x: x[0]
    )
    if (
        len(flows) < 2
        or not any(amount < ZERO for _, amount in flows)
        or not any(amount > ZERO for _, amount in flows)
    ):
        return None
    origin = flows[0][0]

    def npv(rate: Decimal) -> Decimal:
        if rate <= Decimal("-1"):
            raise InvalidOperation
        total = ZERO
        with localcontext() as context:
            context.prec = 40
            for date, amount in flows:
                years = Decimal((_utc(date) - origin).total_seconds()) / Decimal("31557600")
                total += amount / ((Decimal(1) + rate) ** years)
        return total

    low = Decimal("-0.999999999")
    high = Decimal("10")
    try:
        low_value = npv(low)
        high_value = npv(high)
        while low_value * high_value > ZERO and high < Decimal("1000000"):
            high *= Decimal(10)
            high_value = npv(high)
    except (InvalidOperation, OverflowError):
        return None
    if low_value * high_value > ZERO:
        return None
    for _ in range(240):
        midpoint = (low + high) / Decimal(2)
        value = npv(midpoint)
        if abs(value) <= Decimal("0.00000001"):
            return midpoint.quantize(RATE_QUANTUM)
        if low_value * value <= ZERO:
            high = midpoint
        else:
            low = midpoint
            low_value = value
    return ((low + high) / Decimal(2)).quantize(RATE_QUANTUM)


def run_market_stress_scenario(
    positions: Iterable[dict[str, Any]],
    *,
    cash_balance: Decimal,
    protected_cash: Decimal,
    price_shocks: dict[str, Decimal],
    allocations: dict[str, Decimal],
    max_position_weight_percent: Decimal,
    equal_weighting_allowed: bool,
) -> dict[str, Any]:
    """Evaluate a non-executable price/cash-allocation scenario against hard constraints."""

    normalized_shocks = {key.upper(): Decimal(value) for key, value in price_shocks.items()}
    normalized_allocations = {key.upper(): Decimal(value) for key, value in allocations.items()}
    for instrument, shock in normalized_shocks.items():
        if shock < Decimal("-1") or shock > Decimal("5"):
            raise ValuationInputError(f"shock for {instrument} must be between -1 and 5")
    if any(amount < ZERO for amount in normalized_allocations.values()):
        raise ValuationInputError("scenario allocations cannot be negative")

    constraints: list[dict[str, str]] = []
    allocation_total = sum(normalized_allocations.values(), ZERO)
    available_cash = max(ZERO, cash_balance - protected_cash)
    if allocation_total > available_cash:
        constraints.append(
            {
                "code": "PROTECTED_CASH_BREACH",
                "state": "blocked",
                "detail": "Proposed allocation exceeds cash available after the protected reserve.",
            }
        )
    rows: list[dict[str, str]] = []
    base_securities = ZERO
    stressed_securities = ZERO
    known_instruments: set[str] = set()
    for row in positions:
        instrument = str(row["instrument_reference"]).upper()
        known_instruments.add(instrument)
        market_value = _decimal(row.get("market_value"))
        allocation = normalized_allocations.get(instrument, ZERO)
        combined = market_value + allocation
        shock = normalized_shocks.get(instrument, normalized_shocks.get("*", ZERO))
        stressed = combined * (Decimal(1) + shock)
        base_securities += combined
        stressed_securities += stressed
        rows.append(
            {
                "instrument_reference": instrument,
                "base_value": decimal_text(combined),
                "shock_percent": decimal_text(shock * Decimal(100), PERCENT_QUANTUM),
                "stressed_value": decimal_text(stressed),
            }
        )
    projected_nonzero = [
        _decimal(row["base_value"]) for row in rows if _decimal(row["base_value"]) > ZERO
    ]
    if (
        allocation_total > ZERO
        and not equal_weighting_allowed
        and len(projected_nonzero) > 1
        and len(set(projected_nonzero)) == 1
    ):
        constraints.append(
            {
                "code": "EQUAL_WEIGHTING_PROHIBITED",
                "state": "blocked",
                "detail": "The hypothetical allocation would create equal-weight positions.",
            }
        )
    unknown = sorted(set(normalized_allocations) - known_instruments)
    if unknown:
        constraints.append(
            {
                "code": "PRICE_REQUIRED_FOR_NEW_POSITION",
                "state": "blocked",
                "detail": "No trusted price exists for: " + ", ".join(unknown) + ".",
            }
        )

    projected_cash = cash_balance - allocation_total
    baseline_total = projected_cash + base_securities
    stressed_total = projected_cash + stressed_securities
    if stressed_total > ZERO:
        for row in rows:
            weight = _decimal(row["stressed_value"]) / stressed_total * Decimal(100)
            row["stressed_weight_percent"] = decimal_text(weight, PERCENT_QUANTUM)
            if weight > max_position_weight_percent:
                constraints.append(
                    {
                        "code": "MAX_POSITION_WEIGHT_EXCEEDED",
                        "state": "blocked",
                        "detail": (
                            f"{row['instrument_reference']} reaches "
                            f"{decimal_text(weight, PERCENT_QUANTUM)}%."
                        ),
                    }
                )

    blocked = any(item["state"] == "blocked" for item in constraints)
    loss = stressed_total - baseline_total
    loss_rate = loss / baseline_total if baseline_total > ZERO else ZERO
    return {
        "status": "blocked" if blocked else "valid",
        "baseline_total": decimal_text(baseline_total),
        "stressed_total": decimal_text(stressed_total),
        "change_amount": decimal_text(loss),
        "change_percent": decimal_text(loss_rate * Decimal(100), PERCENT_QUANTUM),
        "projected_cash": decimal_text(projected_cash),
        "protected_cash": decimal_text(protected_cash),
        "positions": rows,
        "constraints": constraints,
        "can_execute": False,
        "taxes_included": False,
    }
