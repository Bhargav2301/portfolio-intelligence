from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d[\d,]*(?:\.\d+)?%?")
CITATION_PATTERN = re.compile(r"\[[^\]]+\]")


def claim_for(
    evidence: list[dict[str, Any]], evidence_id: str, claim_key: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    item = next((row for row in evidence if str(row.get("id")) == evidence_id), None)
    if item is None:
        return None
    claim = next(
        (row for row in item.get("claims") or [] if row.get("claim_key") == claim_key),
        None,
    )
    return (item, claim) if claim is not None else None


def first_claim(
    evidence: list[dict[str, Any]], source_type: str, claim_key: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for item in evidence:
        if item.get("source_type") != source_type:
            continue
        claim = next(
            (row for row in item.get("claims") or [] if row.get("claim_key") == claim_key),
            None,
        )
        if claim is not None:
            return item, claim
    return None


def numeric_citation(item: dict[str, Any], claim: dict[str, Any]) -> dict[str, str] | None:
    value = claim.get("numeric_value")
    unit = claim.get("unit")
    if value is None or not unit:
        return None
    evidence_id = str(item.get("id"))
    locator = str(item.get("uri") or item.get("locator") or "registered-evidence")
    return {
        "claim_key": str(claim["claim_key"]),
        "evidence_id": evidence_id,
        "value": str(value),
        "unit": str(unit),
        "as_of": str(item.get("as_of") or item.get("known_at")),
        "locator": locator,
    }


def merge_citations(
    current: list[dict[str, str]], *items: dict[str, str] | None
) -> list[dict[str, str]]:
    merged = list(current)
    seen = {(item["evidence_id"], item["claim_key"], item["value"]) for item in merged}
    for item in items:
        if item is None:
            continue
        key = (item["evidence_id"], item["claim_key"], item["value"])
        if key not in seen:
            merged.append(item)
            seen.add(key)
    return merged


def _numeric_equal(token: str, value: str) -> bool:
    normalized_token = token.replace(",", "").removesuffix("%")
    normalized_value = value.replace(",", "").removesuffix("%")
    try:
        return Decimal(normalized_token) == Decimal(normalized_value)
    except InvalidOperation:
        return False


def numeric_citation_coverage(
    answer: str, citations: list[dict[str, str]]
) -> tuple[Decimal, list[str]]:
    """Return exact coverage after ignoring bracketed evidence identifiers.

    This structural gate is intentionally conservative. It does not judge whether prose is true;
    it only prevents an answer containing an uncited numeric token from being released.
    """

    text_without_ids = CITATION_PATTERN.sub("", answer)
    tokens = NUMBER_PATTERN.findall(text_without_ids)
    if not tokens:
        return Decimal(1), []
    missing: list[str] = []
    for token in tokens:
        matched = any(
            _numeric_equal(token, item["value"]) and f"[{item['evidence_id']}]" in answer
            for item in citations
        )
        if not matched:
            missing.append(token)
    return (Decimal(len(tokens) - len(missing)) / Decimal(len(tokens)), missing)
