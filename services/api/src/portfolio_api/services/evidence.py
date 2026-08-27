from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d[\d,]*(?:\.\d+)?%?")
CITATION_PATTERN = re.compile(r"\[[^\]]+\]")


def _numeric_equal(token: str, value: str) -> bool:
    normalized_token = token.replace(",", "").removesuffix("%")
    normalized_value = value.replace(",", "").removesuffix("%")
    try:
        return Decimal(normalized_token) == Decimal(normalized_value)
    except InvalidOperation:
        return False


def numeric_citation_coverage(
    answer: str, citations: Sequence[Mapping[str, str]]
) -> tuple[Decimal, list[str]]:
    """Verify every released numeric token against a cited, validated claim.

    Evidence identifiers inside square brackets are excluded from token extraction. A number is
    covered only when an equal citation value exists and that citation's exact evidence identifier
    appears in the answer. Claim/value/unit/cutoff validation happens before this function.
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
    return Decimal(len(tokens) - len(missing)) / Decimal(len(tokens)), missing
