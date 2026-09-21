"""Durable owner milestone for completed Forex V2 signal evidence."""

from __future__ import annotations

import hashlib
from typing import Mapping

from app.trading.forex_forward_review import (
    verify_forex_v2_owner_review_lineage,
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
    review = payload.get("forward_review")
    if not verify_forex_v2_owner_review_lineage(report, review):
        return "", None
    selected_review = dict(review)
    identity = "|".join((
        str(selected_review["candidate_id"]),
        str(selected_review["policy_fingerprint_sha256"]),
        str(selected_review["implementation_sha256"]),
    ))
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    if fingerprint == str(completed_fingerprint):
        return fingerprint, None
    cycles = int(selected_review["accepted_cycle_count"])
    days = int(selected_review["accepted_market_day_count"])
    signals = selected_review["signal_comparison"]
    base = signals["base_entry_signal_count"]
    retained = signals["retained_entry_signal_count"]
    filtered = signals["filtered_entry_signal_count"]
    signal_warning = (
        " Brak sygnałów wejścia — wpływu filtra nie da się jeszcze ocenić."
        if base == 0
        else " Te liczby nie oceniają skuteczności strategii."
    )
    occurred_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
    return fingerprint, {
        "kind": "FOREX_V2_FORWARD_REVIEW_READY",
        "state": "important",
        "message": (
            f"Forex V2: próbka obserwacji osiągnęła {cycles} cykli i {days} dni "
            f"rynkowych. Bazowe sygnały wejścia: {base}; V2 zachował {retained}, "
            f"odfiltrował {filtered}.{signal_warning} Jest gotowa tylko do "
            "ręcznego przeglądu; nie potwierdza zysku, nie zmienia strategii "
            "PAPER i nie włącza LIVE."
        ),
        "occurred_at": occurred_at,
        "token": f"forex-v2-forward-review:{fingerprint}",
    }


__all__ = ["forward_review_milestone"]
