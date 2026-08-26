from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

NORMALIZED_FORMAT = "pi-portfolio-import/v1"
STOCK_PATTERN = re.compile(
    r"^(?P<name>.+?)\s+-\s+(?P<exchange>[A-Z]+)\s+-\s+"
    r"(?P<quote_day>\d{2}/\d{2})\s+\((?P<quote_time>\d{2}:\d{2})\)$"
)

# Source exports abbreviate instrument names. Every alias is an explicit mapping;
# an unknown name blocks the import instead of becoming a guessed market symbol.
INSTRUMENT_ALIASES: dict[str, tuple[str, str, str]] = {
    "Adani Ports": ("ADANIPORTS", "Adani Ports and Special Economic Zone", "ADANIPORTS.NS"),
    "Axis Bank": ("AXISBANK", "Axis Bank", "AXISBANK.NS"),
    "Axiscades Tech": ("AXISCADES", "AXISCADES Technologies", "AXISCADES.NS"),
    "Bharat Elec": ("BEL", "Bharat Electronics", "BEL.NS"),
    "COFORGE": ("COFORGE", "Coforge", "COFORGE.NS"),
    "Carysil": ("CARYSIL", "Carysil", "CARYSIL.NS"),
    "IDFC First Bank": ("IDFCFIRSTB", "IDFC First Bank", "IDFCFIRSTB.NS"),
    "Indian Hotels": ("INDHOTEL", "The Indian Hotels Company", "INDHOTEL.NS"),
    "Larsen": ("LT", "Larsen & Toubro", "LT.NS"),
    "Lemon Tree": ("LEMONTREE", "Lemon Tree Hotels", "LEMONTREE.NS"),
    "Nipp Gold Bees": ("GOLDBEES", "Nippon India ETF Gold BeES", "GOLDBEES.NS"),
    "Nipp SilverETF": ("SILVERBEES", "Nippon India ETF Silver BeES", "SILVERBEES.NS"),
    "Oberoi Realty": ("OBEROIRLTY", "Oberoi Realty", "OBEROIRLTY.NS"),
    "Tanfac Ind": ("TANFAC", "Tanfac Industries", "506854.BO"),
    "Timex Group Ind": ("TIMEX", "Timex Group India", "500414.BO"),
    "Viyash Scientif": ("VIYASH", "Viyash Scientific", "VIYASH.NS"),
    "Websol Energy": ("WEBELSOLAR", "Websol Energy System", "WEBELSOLAR.NS"),
    "Yatharth HOSP": ("YATHARTH", "Yatharth Hospital & Trauma Care Services", "YATHARTH.NS"),
}


class NormalizationError(ValueError):
    """Raised when source data is not safe to commit."""


def _number(value: Any, field: str, row_number: int) -> float:
    if value is None or pd.isna(value):
        raise NormalizationError(f"row {row_number}: {field} is missing")
    cleaned = str(value).replace(",", "").strip()
    try:
        number = float(cleaned)
    except ValueError as error:
        raise NormalizationError(
            f"row {row_number}: {field} is not numeric"
        ) from error
    if not pd.notna(number):
        raise NormalizationError(f"row {row_number}: {field} is not finite")
    return number


def _date(value: Any, row_number: int) -> str:
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        raise NormalizationError(f"row {row_number}: acquisition date is invalid")
    return parsed.date().isoformat() + "T00:00:00+05:30"


def _expected_columns() -> set[str]:
    return {
        "Stock",
        "Latest Price",
        "Quantity",
        "Inv. Price",
        "Inv. Date",
        "Inv. Amt",
        "Overall Gain",
        "Latest Value",
        "allocation",
    }


def normalize_qber_rows(
    frame: pd.DataFrame,
    *,
    filename: str,
    source_hash: str,
    portfolio_name: str = "D1 Portfolio",
) -> dict[str, Any]:
    missing = sorted(_expected_columns() - set(frame.columns))
    if missing:
        raise NormalizationError(
            "workbook is missing required columns: " + ", ".join(missing)
        )

    lots: list[dict[str, Any]] = []
    allocations: list[float] = []
    summary: dict[str, float] | None = None
    warnings: list[str] = []
    seen_lots: set[tuple[Any, ...]] = set()

    for index, row in frame.iterrows():
        row_number = int(index) + 2
        stock = "" if pd.isna(row["Stock"]) else str(row["Stock"]).strip()
        allocation = row["allocation"]

        if not stock:
            if pd.notna(allocation):
                allocations.append(_number(allocation, "allocation", row_number))
            continue
        if stock.upper() == "TOTAL":
            summary = {
                "quantity": _number(row["Quantity"], "total quantity", row_number),
                "investment": _number(row["Inv. Amt"], "total investment", row_number),
                "gain": _number(row["Overall Gain"], "total gain", row_number),
                "latest_value": _number(row["Latest Value"], "total latest value", row_number),
            }
            continue

        match = STOCK_PATTERN.match(stock)
        if not match:
            raise NormalizationError(
                f"row {row_number}: stock identity does not match the expected export format"
            )
        source_name = match.group("name").strip()
        exchange = match.group("exchange").strip().upper()
        alias = INSTRUMENT_ALIASES.get(source_name)
        if not alias:
            raise NormalizationError(
                f"row {row_number}: {source_name!r} has no confirmed instrument mapping"
            )
        symbol, canonical_name, analysis_symbol = alias
        expected_suffix = ".NS" if exchange == "NSE" else ".BO" if exchange == "BSE" else ""
        if not expected_suffix or not analysis_symbol.endswith(expected_suffix):
            raise NormalizationError(
                f"row {row_number}: confirmed mapping conflicts with exchange {exchange}"
            )

        quantity = _number(row["Quantity"], "quantity", row_number)
        unit_cost = _number(row["Inv. Price"], "investment price", row_number)
        current_price = _number(row["Latest Price"], "latest price", row_number)
        investment = _number(row["Inv. Amt"], "investment amount", row_number)
        gain = _number(row["Overall Gain"], "overall gain", row_number)
        latest_value = _number(row["Latest Value"], "latest value", row_number)
        if quantity <= 0 or unit_cost < 0 or current_price < 0:
            raise NormalizationError(
                f"row {row_number}: quantity must be positive and prices non-negative"
            )
        if abs(quantity * unit_cost - investment) > 1:
            raise NormalizationError(
                f"row {row_number}: investment amount does not reconcile within INR 1"
            )
        if abs(quantity * current_price - latest_value) > 1:
            raise NormalizationError(
                f"row {row_number}: latest value does not reconcile within INR 1"
            )
        if abs(latest_value - investment - gain) > 1:
            raise NormalizationError(
                f"row {row_number}: gain does not reconcile within INR 1"
            )

        acquired_at = _date(row["Inv. Date"], row_number)
        lot_key = (exchange, symbol, acquired_at, quantity, unit_cost)
        if lot_key in seen_lots:
            raise NormalizationError(f"row {row_number}: duplicate tax lot")
        seen_lots.add(lot_key)
        lots.append(
            {
                "symbol": symbol,
                "name": canonical_name,
                "exchange": exchange,
                "analysis_symbol": analysis_symbol,
                "quantity": quantity,
                "unit_cost": unit_cost,
                "acquired_at": acquired_at,
                "source_row_number": row_number,
                "current_price": current_price,
                "source_investment": investment,
                "source_latest_value": latest_value,
            }
        )

    if not lots:
        raise NormalizationError("workbook has no valid tax lots")
    if summary is None:
        raise NormalizationError("workbook has no TOTAL row")

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for lot in lots:
        grouped[(lot["exchange"], lot["symbol"])].append(lot)

    holdings: list[dict[str, Any]] = []
    for (_exchange, _symbol), group in sorted(grouped.items()):
        prices = {item["current_price"] for item in group}
        if len(prices) != 1:
            raise NormalizationError(
                f"{group[0]['symbol']}: lots contain conflicting latest prices"
            )
        quantity = sum(item["quantity"] for item in group)
        weighted_cost = sum(item["quantity"] * item["unit_cost"] for item in group)
        holdings.append(
            {
                "symbol": group[0]["symbol"],
                "name": group[0]["name"],
                "exchange": group[0]["exchange"],
                "analysis_symbol": group[0]["analysis_symbol"],
                "quantity": quantity,
                "average_cost": weighted_cost / quantity,
                "current_price": group[0]["current_price"],
            }
        )

    computed = {
        "quantity": sum(item["quantity"] for item in lots),
        "investment": sum(item["source_investment"] for item in lots),
        "gain": sum(
            item["source_latest_value"] - item["source_investment"] for item in lots
        ),
        "latest_value": sum(item["source_latest_value"] for item in lots),
    }
    if abs(computed["quantity"] - summary["quantity"]) > 1e-6:
        raise NormalizationError("TOTAL quantity does not reconcile")
    if abs(computed["latest_value"] - summary["latest_value"]) > 1:
        raise NormalizationError("TOTAL latest value does not reconcile within INR 1")
    if abs(computed["gain"] - summary["gain"]) > 1:
        raise NormalizationError("TOTAL gain does not reconcile within INR 1")
    investment_delta = computed["investment"] - summary["investment"]
    if abs(investment_delta) > max(5, len(lots) * 0.51):
        raise NormalizationError("TOTAL investment differs beyond row-rounding tolerance")
    if abs(investment_delta) > 1:
        warnings.append(
            f"source TOTAL investment differs from rounded lot sum by INR {investment_delta:.2f}"
        )

    # The final allocation-only row is the sheet total; preceding allocation rows
    # are group allocations. The export may omit very small positions.
    allocation_total = allocations[-1] if allocations else 0.0
    group_allocation_sum = sum(allocations[:-1]) if len(allocations) > 1 else 0.0
    if allocations and abs(allocation_total - group_allocation_sum) > 1e-6:
        raise NormalizationError("allocation summary does not match grouped allocations")
    if allocations and abs(allocation_total - 1.0) > 1e-6:
        warnings.append(
            f"source allocations sum to {allocation_total * 100:.4f}% rather than 100%"
        )

    public_lots = [
        {
            key: value
            for key, value in lot.items()
            if not key.startswith("source_") and key != "current_price"
        }
        for lot in lots
    ]
    return {
        "format": NORMALIZED_FORMAT,
        "portfolioName": portfolio_name,
        "baseCurrency": "INR",
        "source": {"filename": filename, "sha256": source_hash},
        "quality": {
            "status": "validated_with_warnings" if warnings else "validated",
            "lot_rows": len(lots),
            "holding_rows": len(holdings),
            "invalid_rows": 0,
            "duplicate_lots": 0,
            "computed_totals": computed,
            "source_totals": summary,
            "allocation_total": allocation_total,
            "warnings": warnings,
        },
        "holdings": holdings,
        "lots": public_lots,
    }


def normalize_qber_workbook(
    path: Path, *, portfolio_name: str = "D1 Portfolio"
) -> dict[str, Any]:
    content = path.read_bytes()
    frame = pd.read_excel(path, sheet_name="stocks")
    return normalize_qber_rows(
        frame,
        filename=path.name,
        source_hash=hashlib.sha256(content).hexdigest(),
        portfolio_name=portfolio_name,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize and reconcile a legacy PI portfolio workbook"
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--portfolio-name", default="D1 Portfolio")
    arguments = parser.parse_args()
    result = normalize_qber_workbook(
        arguments.workbook, portfolio_name=arguments.portfolio_name
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
