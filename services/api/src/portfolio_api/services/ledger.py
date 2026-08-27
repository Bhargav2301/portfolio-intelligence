from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from portfolio_api.models import Transaction

ZERO = Decimal("0")
MONEY_QUANTUM = Decimal("0.00000001")
QUANTITY_QUANTUM = Decimal("0.0000000001")
PERCENT_QUANTUM = Decimal("0.01")


class LedgerInvariantError(ValueError):
    pass


@dataclass
class Position:
    quantity: Decimal = ZERO
    cost_basis: Decimal = ZERO
    last_price: Decimal | None = None
    price_as_of: datetime | None = None


def decimal_text(value: Decimal, quantum: Decimal = MONEY_QUANTUM) -> str:
    return format(value.quantize(quantum), "f")


def calculate_ledger(
    transactions: Iterable[Transaction],
    protected_cash: Decimal,
    *,
    reject_negative_cash: bool = False,
) -> dict[str, object]:
    def timestamp(value: datetime | None) -> float:
        if value is None:
            return 0
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.timestamp()

    events = sorted(
        transactions,
        key=lambda item: (timestamp(item.trade_date), timestamp(item.recorded_at)),
    )
    positions: dict[str, Position] = {}
    cash = ZERO
    net_invested = ZERO
    realized_pnl = ZERO
    limitations: list[str] = []

    for event in events:
        amount = Decimal(event.gross_amount)
        cash_delta = (
            Decimal(event.cash_delta) if getattr(event, "cash_delta", None) is not None else None
        )
        instrument = event.instrument_reference
        if event.event_type in {"buy", "sell", "price_mark"}:
            if not instrument or event.price is None:
                raise LedgerInvariantError("security events require an instrument and price")
            position = positions.setdefault(instrument, Position())
            price = Decimal(event.price)
            if event.event_type == "price_mark":
                position.last_price = price
                position.price_as_of = event.trade_date
                continue
            if event.quantity is None:
                raise LedgerInvariantError("buy and sell events require quantity")
            quantity = Decimal(event.quantity)
            if event.event_type == "buy":
                position.quantity += quantity
                cash_change = cash_delta if cash_delta is not None else -amount
                position.cost_basis += -cash_change
                cash += cash_change
            else:
                if quantity > position.quantity:
                    raise LedgerInvariantError(
                        f"sell quantity exceeds published position for {instrument}"
                    )
                average_cost = (
                    position.cost_basis / position.quantity if position.quantity else ZERO
                )
                released_cost = average_cost * quantity
                position.quantity -= quantity
                position.cost_basis -= released_cost
                cash_change = cash_delta if cash_delta is not None else amount
                realized_pnl += cash_change - released_cost
                cash += cash_change
            position.last_price = price
            position.price_as_of = event.trade_date
        elif event.event_type in {"transfer_in", "transfer_out"}:
            if not instrument or event.price is None or event.quantity is None:
                raise LedgerInvariantError(
                    "security transfers require an instrument, quantity, and price"
                )
            position = positions.setdefault(instrument, Position())
            quantity = Decimal(event.quantity)
            basis = quantity * Decimal(event.price)
            if event.event_type == "transfer_in":
                position.quantity += quantity
                position.cost_basis += basis
                net_invested += basis
            else:
                if quantity > position.quantity:
                    raise LedgerInvariantError(
                        f"transfer quantity exceeds published position for {instrument}"
                    )
                average_cost = (
                    position.cost_basis / position.quantity if position.quantity else ZERO
                )
                released_cost = average_cost * quantity
                position.quantity -= quantity
                position.cost_basis -= released_cost
                net_invested -= released_cost
            position.last_price = Decimal(event.price)
            position.price_as_of = event.trade_date
        elif event.event_type == "cash_deposit":
            change = cash_delta if cash_delta is not None else amount
            cash += change
            net_invested += change
        elif event.event_type == "cash_withdrawal":
            change = cash_delta if cash_delta is not None else -amount
            if -change > cash:
                raise LedgerInvariantError("cash withdrawal exceeds published cash balance")
            cash += change
            net_invested += change
        elif event.event_type in {"dividend", "dividend_cash"}:
            cash += cash_delta if cash_delta is not None else amount
        elif event.event_type == "fee":
            change = cash_delta if cash_delta is not None else -amount
            cash += change
            realized_pnl -= amount
        else:
            raise LedgerInvariantError(f"unsupported ledger event type: {event.event_type}")

    if cash < ZERO:
        if reject_negative_cash:
            raise LedgerInvariantError("published events would make portfolio cash negative")
        limitations.append(
            "Published security purchases and fees exceed published cash events; cash is negative."
        )

    securities_value = ZERO
    holding_rows: list[dict[str, object]] = []
    for instrument, position in sorted(positions.items()):
        if position.quantity == ZERO:
            continue
        market_value = (
            position.quantity * position.last_price if position.last_price is not None else None
        )
        if market_value is None:
            limitations.append(f"{instrument} has no published price mark.")
        else:
            securities_value += market_value
        holding_rows.append(
            {
                "instrument_reference": instrument,
                "quantity": decimal_text(position.quantity, QUANTITY_QUANTUM),
                "average_cost": decimal_text(
                    position.cost_basis / position.quantity if position.quantity else ZERO
                ),
                "last_price": decimal_text(position.last_price) if position.last_price else None,
                "market_value": decimal_text(market_value) if market_value is not None else None,
                "cost_basis": decimal_text(position.cost_basis),
                "unrealized_pnl": (
                    decimal_text(market_value - position.cost_basis)
                    if market_value is not None
                    else None
                ),
                "weight_percent": None,
                "price_as_of": position.price_as_of,
            }
        )

    total_value = cash + securities_value
    if total_value > ZERO:
        for row in holding_rows:
            market_value_text = row["market_value"]
            if market_value_text is not None:
                weight = Decimal(str(market_value_text)) / total_value * Decimal("100")
                row["weight_percent"] = decimal_text(weight, PERCENT_QUANTUM)

    available_cash = max(ZERO, cash - protected_cash)
    return {
        "as_of": datetime.now(UTC),
        "ledger_version": max(
            (int(getattr(event, "ledger_version", 0) or 0) for event in events),
            default=0,
        )
        or len(events),
        "cash_balance": decimal_text(cash),
        "available_cash": decimal_text(available_cash),
        "protected_cash": decimal_text(protected_cash),
        "net_invested_capital": decimal_text(net_invested),
        "securities_market_value": decimal_text(securities_value),
        "total_value": decimal_text(total_value),
        "realized_pnl": decimal_text(realized_pnl),
        "holdings": holding_rows,
        "limitations": limitations,
    }


def build_monitor_snapshot(
    portfolio_id: object,
    ledger: dict[str, object],
    max_position_weight_percent: Decimal,
) -> dict[str, object]:
    alerts: list[dict[str, object]] = []
    ledger_version = int(ledger["ledger_version"])
    cash = Decimal(str(ledger["cash_balance"]))
    protected = Decimal(str(ledger["protected_cash"]))
    if ledger_version == 0:
        alerts.append(
            {
                "id": "ledger-data-required",
                "severity": "critical",
                "kind": "data_quality",
                "title": "Publish a reconciled ledger",
                "detail": (
                    "Monitoring remains blocked until at least one ledger event is published."
                ),
                "evidence_ids": ["ledger:version"],
            }
        )
    if cash < protected:
        alerts.append(
            {
                "id": "protected-reserve-breach",
                "severity": "critical",
                "kind": "protected_reserve",
                "title": "Protected reserve is not fully covered",
                "detail": "Published cash is below the portfolio's protected reserve rule.",
                "observed_value": decimal_text(cash),
                "threshold_value": decimal_text(protected),
                "evidence_ids": ["ledger:cash_balance", "rule:protected_cash"],
            }
        )
    for holding in ledger["holdings"]:  # type: ignore[union-attr]
        weight_text = holding.get("weight_percent")
        if weight_text is None:
            continue
        weight = Decimal(str(weight_text))
        if weight > max_position_weight_percent:
            instrument = str(holding["instrument_reference"])
            alerts.append(
                {
                    "id": f"concentration-{instrument.lower()}",
                    "severity": "warning",
                    "kind": "concentration",
                    "title": f"{instrument} exceeds the concentration threshold",
                    "detail": (
                        "Review the position in context; this alert is not a sell instruction."
                    ),
                    "instrument_reference": instrument,
                    "observed_value": decimal_text(weight, PERCENT_QUANTUM),
                    "threshold_value": decimal_text(max_position_weight_percent, PERCENT_QUANTUM),
                    "evidence_ids": [f"holding:{instrument}:weight", "rule:max_position_weight"],
                }
            )
    critical = any(alert["severity"] == "critical" for alert in alerts)
    return {
        "portfolio_id": portfolio_id,
        "as_of": ledger["as_of"],
        "state": "blocked" if critical else ("attention" if alerts else "clear"),
        "alerts": alerts,
        "checked_rules": [
            "ledger_data_present",
            "protected_cash_covered",
            "max_position_weight",
        ],
        "limitations": list(ledger["limitations"]),  # type: ignore[arg-type]
    }
