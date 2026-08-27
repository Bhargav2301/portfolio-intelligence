from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext


class GoalInputError(ValueError):
    pass


def required_cagr(wealth_multiple: Decimal | str, years: Decimal | str) -> Decimal:
    """Return annualized rate for a terminal wealth multiple and horizon."""
    try:
        multiple = Decimal(wealth_multiple)
        horizon = Decimal(years)
    except InvalidOperation as error:
        raise GoalInputError("wealth multiple and years must be numeric") from error
    if multiple <= 0:
        raise GoalInputError("wealth multiple must be greater than zero")
    if horizon <= 0:
        raise GoalInputError("years must be greater than zero")
    with localcontext() as context:
        context.prec = 28
        return multiple ** (Decimal(1) / horizon) - Decimal(1)


def allocate_available_cash(total_cash: Decimal, protected_cash: Decimal) -> Decimal:
    if total_cash < 0 or protected_cash < 0:
        raise ValueError("cash values cannot be negative")
    return max(Decimal(0), total_cash - protected_cash)
