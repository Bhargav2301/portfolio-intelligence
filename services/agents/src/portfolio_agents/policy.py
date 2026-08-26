from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


EXECUTION_PATTERNS = (
    re.compile(r"\b(place|submit|execute)\s+(an?\s+)?(order|trade)\b", re.IGNORECASE),
    re.compile(r"\btransfer\s+funds?\b", re.IGNORECASE),
    re.compile(r"\buse\s+(the\s+)?protected\s+(cash|reserve)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]


def evaluate_request(question: str, snapshot: dict[str, Any]) -> PolicyDecision:
    reasons: list[str] = []
    limitations: list[str] = []
    if any(pattern.search(question) for pattern in EXECUTION_PATTERNS):
        reasons.append("ORDER_EXECUTION_PROHIBITED")
    quality_state = snapshot.get("quality_state")
    if quality_state != "trusted":
        reasons.append("PORTFOLIO_DATA_NOT_TRUSTED")
        limitations.append(
            "Portfolio data is incomplete or unreconciled, so analysis is limited to setup and review."
        )
    rules = snapshot.get("rules") or {}
    if rules.get("equal_weighting_allowed") is False:
        limitations.append("Equal-weight scenarios are prohibited by the active portfolio rule.")
    protected = (rules.get("protected_cash") or {}).get("amount")
    if protected:
        limitations.append(f"Protected reserve of INR {protected} cannot be allocated.")
    if "ORDER_EXECUTION_PROHIBITED" in reasons:
        return PolicyDecision("suppress_execution", tuple(reasons), tuple(limitations))
    if "PORTFOLIO_DATA_NOT_TRUSTED" in reasons:
        return PolicyDecision("limited", tuple(reasons), tuple(limitations))
    return PolicyDecision("allow_analysis", tuple(reasons), tuple(limitations))


def safe_response_text(text: str) -> str:
    """Remove accidental imperative execution phrases from model output."""
    result = text
    replacements = {
        r"\byou should buy\b": "one scenario to examine is increasing exposure to",
        r"\byou should sell\b": "one scenario to examine is reducing exposure to",
        r"\bplace an order\b": "review the scenario outside this read-only tool",
        r"\bexecute the trade\b": "record a human decision after review",
    }
    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result

