"""Durable owner milestone for completed Forex V2 signal evidence."""

from __future__ import annotations

import hashlib
from typing import Mapping

from app.trading.forex_forward_evidence import (
    verify_forex_v2_forward_evidence_report,
)


def forward_review_milestone(
    payload: object,
    *,
    completed_fingerprint: object = "",
) -> tuple[str, dict[str, str] | None]:
    """Return one safe notification spec for a newly completed candidate."""
    if not isinstance(payload, Mapping) or any(
        payload.get(field) is not False
        for field in ("broker_orders_sent", "live_orders_sent", "real_money_access")
    ):
        return "", None
    report = payload.get("forward_evidence")
    if not verify_forex_v2_forward_evidence_report(
        report,
        require_complete=True,
    ):
        return "", None
    selected = dict(report) if isinstance(report, Mapping) else {}
    identity = "|".join((
        str(selected.get("candidate_id", "")),
        str(selected.get("policy_fingerprint_sha256", "")),
        str(selected.get("implementation_sha256", "")),
    ))
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    if fingerprint == str(completed_fingerprint):
        return fingerprint, None
    cycles = int(selected["accepted_cycle_count"])
    days = int(selected["accepted_market_day_count"])
    occurred_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
    return fingerprint, {
        "kind": "FOREX_V2_FORWARD_REVIEW_READY",
        "state": "important",
        "message": (
            f"Forex V2: próbka sygnałowa osiągnęła {cycles} cykli i {days} dni "
            "rynkowych. Jest gotowa do ręcznego przeglądu, ale nie potwierdza "
            "zysku, nie zmienia strategii PAPER i nie włącza LIVE."
        ),
        "occurred_at": occurred_at,
        "token": f"forex-v2-forward-review:{fingerprint}",
    }


__all__ = ["forward_review_milestone"]
