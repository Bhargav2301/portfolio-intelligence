from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from portfolio_intelligence.domain.models import Position, PriceObservation, ValuedPosition


class MissingPriceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    positions: tuple[ValuedPosition, ...]
    total_cost_basis: Decimal
    total_market_value: Decimal
    total_unrealized_gain: Decimal
    as_of: datetime

    @property
    def absolute_return(self) -> Decimal | None:
        if self.total_cost_basis == 0:
            return None
        return self.total_unrealized_gain / self.total_cost_basis


def value_positions(
    positions: dict[UUID, Position],
    prices: dict[UUID, PriceObservation],
    *,
    as_of: datetime,
) -> PortfolioValuation:
    valued: list[ValuedPosition] = []
    for instrument_id, position in positions.items():
        observation = prices.get(instrument_id)
        if observation is None or observation.effective_at > as_of:
            raise MissingPriceError(f"no valid price for instrument {instrument_id}")
        market_value = position.quantity * observation.price
        valued.append(
            ValuedPosition(
                position=position,
                market_price=observation.price,
                market_value=market_value,
                unrealized_gain=market_value - position.cost_basis,
                price_source=observation.source,
                price_as_of=observation.effective_at,
            )
        )

    return PortfolioValuation(
        positions=tuple(valued),
        total_cost_basis=sum((item.position.cost_basis for item in valued), Decimal("0")),
        total_market_value=sum((item.market_value for item in valued), Decimal("0")),
        total_unrealized_gain=sum((item.unrealized_gain for item in valued), Decimal("0")),
        as_of=as_of,
    )

