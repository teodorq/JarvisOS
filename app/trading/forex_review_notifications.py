"""Combine durable, deduplicated Forex owner-review milestones."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.trading.forex_forward_notifications import (
    forward_review_milestone,
    v3_shadow_readiness_milestone,
)
from app.trading.forex_performance_notifications import (
    paper_performance_review_milestone,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT_FIELDS = (
    "forward_review_fingerprint",
    "v3_shadow_readiness_fingerprint",
    "performance_review_fingerprint",
)


def review_milestones(
    payload: object,
    state: Mapping[str, Any],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Build all new review events and the fingerprints that consumed them."""
    forward_fingerprint, forward = forward_review_milestone(
        payload,
        completed_fingerprint=state.get("forward_review_fingerprint", ""),
    )
    performance_fingerprint, performance = paper_performance_review_milestone(
        payload,
        completed_fingerprint=state.get("performance_review_fingerprint", ""),
    )
    v3_fingerprint, v3_shadow = v3_shadow_readiness_milestone(
        payload,
        completed_fingerprint=state.get(
            "v3_shadow_readiness_fingerprint",
            "",
        ),
    )
    fingerprints = {}
    if forward_fingerprint:
        fingerprints["forward_review_fingerprint"] = forward_fingerprint
    if performance_fingerprint:
        fingerprints["performance_review_fingerprint"] = performance_fingerprint
    if v3_fingerprint:
        fingerprints["v3_shadow_readiness_fingerprint"] = v3_fingerprint
    return fingerprints, [
        item for item in (forward, v3_shadow, performance) if item
    ]


def normalized_review_fingerprints(value: Mapping[str, Any]) -> dict[str, str]:
    """Keep only bounded SHA-256 milestone identities from persisted state."""
    result = {}
    for field in _FINGERPRINT_FIELDS:
        fingerprint = str(value.get(field, ""))
        result[field] = fingerprint if _SHA256.fullmatch(fingerprint) else ""
    return result


__all__ = ["normalized_review_fingerprints", "review_milestones"]
