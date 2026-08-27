from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from portfolio_api.services.control_plane import canonical_hash

TEMPLATE_ID = "spi-ledger-csv/v1"
PARSER_NAME = "spi-certified-ledger-csv"
PARSER_VERSION = "1.0.0"
REQUIRED_COLUMNS = {
    "schema_version",
    "source_reference",
    "event_type",
    "trade_at",
    "account_reference",
    "currency",
    "cash_delta",
}
SECURITY_COLUMNS = {
    "instrument_id_type",
    "instrument_id",
    "exchange",
    "symbol",
    "quantity",
    "price",
}
OPTIONAL_COLUMNS = {"settlement_date", "fees", "taxes", "lot_reference", "description"}
ALLOWED_COLUMNS = REQUIRED_COLUMNS | SECURITY_COLUMNS | OPTIONAL_COLUMNS
EVENT_TYPES = {
    "buy",
    "sell",
    "cash_deposit",
    "cash_withdrawal",
    "dividend_cash",
    "fee",
    "transfer_in",
    "transfer_out",
}
SECURITY_EVENTS = {"buy", "sell", "transfer_in", "transfer_out"}
MONEY_TOLERANCE = Decimal("0.01")


class CertifiedCsvError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RecordIssue:
    source_row: int
    kind: str
    message: str
    field: str | None = None


@dataclass(frozen=True)
class ParsedRecord:
    source_row: int
    raw_hash: str
    data: dict[str, Any]


@dataclass(frozen=True)
class CertifiedCsvResult:
    content_hash: str
    headers: tuple[str, ...]
    records: tuple[ParsedRecord, ...]
    issues: tuple[RecordIssue, ...]


def _decimal(row: dict[str, str], field: str, *, required: bool = False) -> Decimal | None:
    value = (row.get(field) or "").strip()
    if not value:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field} must be a decimal string") from error
    if not parsed.is_finite():
        raise ValueError(f"{field} must be finite")
    return parsed


def _date(value: str, field: str, *, required: bool = False) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _safe_text(value: str, field: str, *, required: bool = False) -> str | None:
    normalized = value.strip()
    if not normalized:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if normalized[0] in {"=", "+", "-", "@"}:
        raise ValueError(f"{field} begins with an unsafe spreadsheet formula marker")
    if len(normalized) > 500:
        raise ValueError(f"{field} exceeds 500 characters")
    return normalized


def _normalize_row(row: dict[str, str], source_row: int) -> dict[str, Any]:
    schema_version = _safe_text(row.get("schema_version", ""), "schema_version", required=True)
    if schema_version != TEMPLATE_ID:
        raise ValueError(f"schema_version must be {TEMPLATE_ID}")
    event_type = str(_safe_text(row.get("event_type", ""), "event_type", required=True)).lower()
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type must be one of {', '.join(sorted(EVENT_TYPES))}")
    source_reference = _safe_text(
        row.get("source_reference", ""), "source_reference", required=True
    )
    account_reference = _safe_text(
        row.get("account_reference", ""), "account_reference", required=True
    )
    currency = str(_safe_text(row.get("currency", ""), "currency", required=True)).upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency must be a three-letter ISO-4217 code")
    trade_at = _date(row.get("trade_at", ""), "trade_at", required=True)
    settlement_date = _date(row.get("settlement_date", ""), "settlement_date")
    cash_delta = _decimal(row, "cash_delta", required=True)
    fees = _decimal(row, "fees") or Decimal("0")
    taxes = _decimal(row, "taxes") or Decimal("0")
    if fees < 0 or taxes < 0:
        raise ValueError("fees and taxes must be non-negative")

    quantity = _decimal(row, "quantity")
    price = _decimal(row, "price")
    instrument_id_type = _safe_text(row.get("instrument_id_type", ""), "instrument_id_type")
    instrument_id = _safe_text(row.get("instrument_id", ""), "instrument_id")
    exchange = _safe_text(row.get("exchange", ""), "exchange")
    symbol = _safe_text(row.get("symbol", ""), "symbol")

    if event_type in SECURITY_EVENTS:
        required_security = {
            "instrument_id_type": instrument_id_type,
            "instrument_id": instrument_id,
            "exchange": exchange,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
        }
        missing = [field for field, value in required_security.items() if value is None]
        if missing:
            raise ValueError("security event is missing: " + ", ".join(missing))
        if quantity is not None and quantity <= 0:
            raise ValueError("quantity must be positive")
        if price is not None and price <= 0:
            raise ValueError("price must be positive")
        if str(instrument_id_type).upper() not in {"ISIN", "TICKER", "UPSTOX_TOKEN"}:
            raise ValueError("instrument_id_type must be ISIN, TICKER, or UPSTOX_TOKEN")
        if str(exchange).upper() not in {"NSE", "BSE"}:
            raise ValueError("exchange must be NSE or BSE")
    elif any(
        value is not None
        for value in (quantity, price, instrument_id_type, instrument_id, exchange, symbol)
    ):
        raise ValueError("cash-only events cannot include security fields")

    assert cash_delta is not None
    if event_type == "buy":
        expected = -((quantity or Decimal("0")) * (price or Decimal("0")) + fees + taxes)
        if abs(cash_delta - expected) > MONEY_TOLERANCE:
            raise ValueError(
                "buy cash_delta does not reconcile to quantity, price, fees, and taxes"
            )
    elif event_type == "sell":
        expected = (quantity or Decimal("0")) * (price or Decimal("0")) - fees - taxes
        if abs(cash_delta - expected) > MONEY_TOLERANCE:
            raise ValueError(
                "sell cash_delta does not reconcile to quantity, price, fees, and taxes"
            )
    elif event_type in {"transfer_in", "transfer_out"} and cash_delta != 0:
        raise ValueError("security transfers must have cash_delta 0")
    elif event_type in {"cash_deposit", "dividend_cash"} and cash_delta <= 0:
        raise ValueError(f"{event_type} requires a positive cash_delta")
    elif event_type in {"cash_withdrawal", "fee"} and cash_delta >= 0:
        raise ValueError(f"{event_type} requires a negative cash_delta")

    normalized = {
        "schema_version": TEMPLATE_ID,
        "source_reference": source_reference,
        "event_type": event_type,
        "trade_at": trade_at.isoformat() if trade_at else None,
        "settlement_date": settlement_date.isoformat() if settlement_date else None,
        "account_reference": account_reference,
        "currency": currency,
        "cash_delta": format(cash_delta, "f"),
        "fees": format(fees, "f"),
        "taxes": format(taxes, "f"),
        "instrument_id_type": str(instrument_id_type).upper() if instrument_id_type else None,
        "instrument_id": str(instrument_id).upper() if instrument_id else None,
        "exchange": str(exchange).upper() if exchange else None,
        "symbol": str(symbol).upper() if symbol else None,
        "quantity": format(quantity, "f") if quantity is not None else None,
        "price": format(price, "f") if price is not None else None,
        "lot_reference": _safe_text(row.get("lot_reference", ""), "lot_reference"),
        "description": _safe_text(row.get("description", ""), "description"),
        "source_row": source_row,
    }
    return normalized


def parse_certified_csv(content: bytes) -> CertifiedCsvResult:
    if b"\x00" in content:
        raise CertifiedCsvError("CSV_BINARY_CONTENT", "The CSV contains binary null bytes.")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CertifiedCsvError("CSV_ENCODING_UNSUPPORTED", "Use UTF-8 CSV encoding.") from error
    reader = csv.DictReader(io.StringIO(decoded), dialect=csv.excel)
    if not reader.fieldnames:
        raise CertifiedCsvError("CSV_HEADER_REQUIRED", "The CSV header row is missing.")
    headers = tuple(field.strip() for field in reader.fieldnames if field is not None)
    if len(headers) != len(set(headers)):
        raise CertifiedCsvError("CSV_DUPLICATE_HEADER", "CSV column names must be unique.")
    missing_headers = sorted(REQUIRED_COLUMNS - set(headers))
    if missing_headers:
        raise CertifiedCsvError(
            "CSV_REQUIRED_COLUMNS_MISSING",
            "Missing required columns: " + ", ".join(missing_headers),
        )

    issues: list[RecordIssue] = []
    unknown_headers = sorted(set(headers) - ALLOWED_COLUMNS)
    for header in unknown_headers:
        issues.append(
            RecordIssue(
                source_row=1,
                kind="unmapped_column",
                field=header,
                message=f"Column {header} must be mapped or explicitly excluded.",
            )
        )

    records: list[ParsedRecord] = []
    source_references: set[str] = set()
    for source_row, raw in enumerate(reader, start=2):
        if not any((value or "").strip() for value in raw.values()):
            continue
        canonical_raw = {str(key).strip(): (value or "").strip() for key, value in raw.items()}
        try:
            normalized = _normalize_row(canonical_raw, source_row)
            source_reference = str(normalized["source_reference"])
            if source_reference in source_references:
                raise ValueError("source_reference is duplicated within the file")
            source_references.add(source_reference)
            records.append(
                ParsedRecord(
                    source_row=source_row,
                    raw_hash=canonical_hash(canonical_raw),
                    data=normalized,
                )
            )
        except ValueError as error:
            issues.append(
                RecordIssue(source_row=source_row, kind="record_validation", message=str(error))
            )
    if not records and not issues:
        raise CertifiedCsvError("CSV_DATA_REQUIRED", "The CSV contains no data rows.")
    return CertifiedCsvResult(
        content_hash=hashlib.sha256(content).hexdigest(),
        headers=headers,
        records=tuple(records),
        issues=tuple(issues),
    )


def normalize_record(data: dict[str, Any], source_row: int) -> dict[str, Any]:
    """Validate an edited record through the same contract used by file extraction."""
    row = {str(key): "" if value is None else str(value) for key, value in data.items()}
    return _normalize_row(row, source_row)
