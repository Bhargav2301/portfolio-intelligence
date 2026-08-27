from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

UPSTREAM_REPOSITORY = "TauricResearch/TradingAgents"
UPSTREAM_COMMIT = "a33fd4c0f134485a43553a2c23a63cb14adbd88f"
ADAPTER_VERSION = "spi-tradingagents-adapter/3.0.0"

Signal = Literal["BULLISH", "BEARISH", "NEUTRAL", "ABSTAIN"]
Confidence = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class TradingAgentsPrediction:
    signal: Signal
    confidence: Confidence
    horizon: str
    summary: str
    factors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "confidence": self.confidence,
            "horizon": self.horizon,
            "summary": self.summary,
            "factors": list(self.factors),
            "engine": ADAPTER_VERSION,
            "upstream_repository": UPSTREAM_REPOSITORY,
            "upstream_commit": UPSTREAM_COMMIT,
            "not_trade_instruction": True,
        }


def normalize_instrument(value: str) -> str:
    normalized = value.upper().replace(".NS", "").replace(".BO", "")
    return re.sub(r"[^A-Z0-9]", "", normalized)


def claim_matches_instrument(claim: dict[str, Any], instrument: str | None) -> bool:
    if not instrument:
        return False
    target = normalize_instrument(instrument)
    if not target:
        return False
    claim_key = normalize_instrument(str(claim.get("claim_key", "")))
    statement = normalize_instrument(str(claim.get("statement", "")))
    return target in claim_key or claim_key in target or target in statement


def _decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _factor_for_claim(claim: dict[str, Any]) -> tuple[int, str] | None:
    key = str(claim.get("claim_key", "")).lower()
    statement = str(claim.get("statement", "")).lower()
    value = _decimal(claim.get("numeric_value"))
    if key.endswith(".stock_score") or key.endswith(".score"):
        if value is None:
            return None
        if value >= Decimal(8):
            return 3, "positive publisher score"
        if value <= Decimal(3):
            return -3, "negative publisher score"
        return 0, "neutral publisher score"
    if key.endswith(".outlook"):
        if "positive" in statement:
            return 2, "positive published outlook"
        if "negative" in statement:
            return -2, "negative published outlook"
        if "neutral" in statement:
            return 0, "neutral published outlook"
    directional_metrics = (
        ".return_1_day",
        ".return_1_week",
        ".return_1_month",
        ".return_3_months",
        ".return_6_months",
        ".return_1_year",
        ".overall_gain_percent",
        ".upside_percent",
    )
    if key.endswith(directional_metrics) and value is not None:
        weight = (
            2 if key.endswith((".return_3_months", ".return_6_months", ".return_1_year")) else 1
        )
        if value > 0:
            return weight, "positive price or portfolio momentum"
        if value < 0:
            return -weight, "negative price or portfolio momentum"
        return 0, "flat price or portfolio momentum"
    return None


def derive_prediction(
    *,
    instrument: str | None,
    evidence: list[dict[str, Any]],
    analyst_reports: dict[str, str],
    perspectives: dict[str, str],
) -> TradingAgentsPrediction:
    """Produce the bounded final signal after the TradingAgents analyst/debate/risk shape.

    The upstream project ends with a portfolio-manager signal. This adapter keeps that ordering,
    but its demo signal is derived only from uploaded, cutoff-eligible claims. It never infers an
    order quantity, target price, expected return, or execution instruction.
    """

    if not instrument:
        return TradingAgentsPrediction(
            signal="ABSTAIN",
            confidence="low",
            horizon="unspecified",
            summary="Choose one security so the TradingAgents panel can resolve relevant evidence.",
            factors=(),
        )
    scored_factors: list[tuple[int, str]] = []
    supporting_items: set[str] = set()
    seen_claims: set[tuple[str, str]] = set()
    for item in evidence:
        for claim in item.get("claims") or []:
            if not claim_matches_instrument(claim, instrument):
                continue
            claim_key = str(claim.get("claim_key", ""))
            value = str(claim.get("numeric_value", ""))
            fingerprint = (claim_key, value)
            if fingerprint in seen_claims:
                continue
            seen_claims.add(fingerprint)
            factor = _factor_for_claim(claim)
            if factor is not None:
                scored_factors.append(factor)
                supporting_items.add(str(item.get("id", "unknown")))
    if not scored_factors:
        return TradingAgentsPrediction(
            signal="ABSTAIN",
            confidence="low",
            horizon="unspecified",
            summary="The panel found no directional, cutoff-eligible claims for this security.",
            factors=(),
        )
    score = sum(item[0] for item in scored_factors)
    if score >= 3:
        signal: Signal = "BULLISH"
        summary = "The evidence-weighted analyst consensus is bullish, subject to the risk panel."
    elif score <= -3:
        signal = "BEARISH"
        summary = "The evidence-weighted analyst consensus is bearish, subject to the risk panel."
    else:
        signal = "NEUTRAL"
        summary = "The analyst evidence is mixed and does not support a directional view."
    factor_labels = tuple(dict.fromkeys(label for _, label in scored_factors))
    magnitude = abs(score)
    if len(supporting_items) >= 2 and len(scored_factors) >= 5 and magnitude >= 6:
        confidence: Confidence = "high"
    elif len(scored_factors) >= 3 and magnitude >= 3:
        confidence = "medium"
    else:
        confidence = "low"
    if not analyst_reports or not perspectives:
        confidence = "low"
    return TradingAgentsPrediction(
        signal=signal,
        confidence=confidence,
        horizon="research_snapshot",
        summary=summary,
        factors=factor_labels,
    )
