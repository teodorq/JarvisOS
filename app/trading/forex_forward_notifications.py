"""Durable owner milestone for completed Forex V2 signal evidence."""

from __future__ import annotations

import hashlib
from typing import Mapping

from app.trading.forex_forward_review import (
    verify_forex_v2_owner_review_lineage,
)
from app.trading.forex_forward_evidence import (
    verify_forex_v3_forward_evidence_report,
)

_V3_PROGRESS_MARKERS = (5, 10, 15)


def v3_forward_progress_milestones(
    payload: object,
    *,
    completed_progress_fingerprint: object = "",
    completed_integrity_fingerprint: object = "",
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Return sparse, deduplicated progress and integrity events for V3R2."""

    if not isinstance(payload, Mapping) or any(
        payload.get(field) is not False
        for field in (
            "broker_orders_sent",
            "live_orders_sent",
            "real_money_access",
        )
    ):
        return {}, []
    report = payload.get("v3_forward_evidence")
    if not verify_forex_v3_forward_evidence_report(
        report,
        require_complete=False,
    ):
        return {}, []
    selected = dict(report)  # type: ignore[arg-type]
    candidate_id = str(selected["candidate_id"])
    policy_fingerprint = str(selected["policy_fingerprint_sha256"])
    implementation = str(selected["implementation_sha256"])
    occurred_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
    status = str(selected["status"])
    invalid_count = int(selected["invalid_cycle_count"])
    source_valid = selected["source_state_valid"] is True

    if invalid_count or not source_valid:
        invalid_issues = selected.get("invalid_issues")
        issue_names = sorted(
            str(name)
            for name in (
                invalid_issues.keys()
                if isinstance(invalid_issues, Mapping)
                else ()
            )
        )
        identity = "|".join((
            candidate_id,
            policy_fingerprint,
            implementation,
            "INTEGRITY_BLOCKED",
            status,
            ",".join(issue_names),
        ))
        fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if fingerprint == str(completed_integrity_fingerprint):
            return {
                "v3_forward_integrity_fingerprint": fingerprint,
            }, []
        message = (
            "Forex V3: wstrzymałem zaliczanie próbki, ponieważ źródło "
            "dowodów nie przeszło kontroli integralności."
            if not source_valid
            else (
                "Forex V3: wstrzymałem zaliczanie próbki po wykryciu "
                f"{invalid_count} niespójnych cykli."
            )
        )
        return {
            "v3_forward_integrity_fingerprint": fingerprint,
        }, [{
            "kind": "FOREX_V3_FORWARD_EVIDENCE_BLOCKED",
            "state": "important",
            "message": (
                message
                + " Strategia SHADOW i LIVE pozostają zablokowane; "
                "zdarzenie wymaga sprawdzenia w panelu właściciela."
            ),
            "occurred_at": occurred_at,
            "token": f"forex-v3-forward-integrity:{fingerprint}",
        }]

    if selected["observation_sample_complete"] is True:
        return {}, []
    cycles = int(selected["accepted_cycle_count"])
    reached = max(
        (marker for marker in _V3_PROGRESS_MARKERS if cycles >= marker),
        default=0,
    )
    if not reached:
        return {}, []
    identity = "|".join((
        candidate_id,
        policy_fingerprint,
        implementation,
        "PROGRESS",
        str(reached),
    ))
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    if fingerprint == str(completed_progress_fingerprint):
        return {
            "v3_forward_progress_fingerprint": fingerprint,
        }, []
    minimum_cycles = int(selected["minimum_accepted_cycle_count"])
    days = int(selected["accepted_market_day_count"])
    minimum_days = int(selected["minimum_market_day_count"])
    return {
        "v3_forward_progress_fingerprint": fingerprint,
    }, [{
        "kind": "FOREX_V3_FORWARD_PROGRESS",
        "state": "brief",
        "message": (
            f"Forex V3: zweryfikowana próbka osiągnęła {cycles}/"
            f"{minimum_cycles} cykli i {days}/{minimum_days} dni rynkowych. "
            "To tylko informacja o postępie — nie potwierdza zysku, nie "
            "uruchamia strategii SHADOW i nie włącza LIVE."
        ),
        "occurred_at": occurred_at,
        "token": f"forex-v3-forward-progress:{fingerprint}",
    }]


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
        else (
            " Tylko jeden sygnał — za mało do oceny działania filtra."
            if base == 1
            else " Te liczby nie oceniają skuteczności strategii."
        )
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


def v3_shadow_readiness_milestone(
    payload: object,
    *,
    completed_fingerprint: object = "",
) -> tuple[str, dict[str, str] | None]:
    """Return one review-only alert for complete verified V3 evidence."""

    if not isinstance(payload, Mapping) or any(
        payload.get(field) is not False
        for field in (
            "broker_orders_sent",
            "live_orders_sent",
            "real_money_access",
        )
    ):
        return "", None
    report = payload.get("v3_forward_evidence")
    if not verify_forex_v3_forward_evidence_report(
        report,
        require_complete=True,
    ):
        return "", None
    selected = dict(report)  # type: ignore[arg-type]
    signals = selected.get("signal_comparison")
    signals = dict(signals) if isinstance(signals, Mapping) else {}
    base = signals.get("base_entry_signal_count")
    retained = signals.get("retained_entry_signal_count")
    filtered = signals.get("filtered_entry_signal_count")
    if (
        any(type(value) is not int or value < 0 for value in (
            base,
            retained,
            filtered,
        ))
        or base != retained + filtered
    ):
        return "", None
    identity = "|".join((
        str(selected["candidate_id"]),
        str(selected["policy_fingerprint_sha256"]),
        str(selected["implementation_sha256"]),
    ))
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    if fingerprint == str(completed_fingerprint):
        return fingerprint, None
    cycles = int(selected["accepted_cycle_count"])
    days = int(selected["accepted_market_day_count"])
    signal_warning = (
        " Nie zarejestrowano sygnałów wejścia, więc filtr nie ma jeszcze "
        "materiału do oceny."
        if base == 0
        else " Te liczby nie oceniają rentowności strategii."
    )
    occurred_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
    return fingerprint, {
        "kind": "FOREX_V3_SHADOW_INITIALIZATION_READY",
        "state": "important",
        "message": (
            f"Forex V3: ścisła próbka osiągnęła {cycles} cykli i {days} dni "
            f"rynkowych. Bazowe sygnały wejścia: {base}; V3 zachował "
            f"{retained}, odfiltrował {filtered}.{signal_warning} Oddzielny "
            "portfel SHADOW jest gotowy wyłącznie do ręcznej inicjalizacji; "
            "nie potwierdza zysku, nie zmienia PAPER i nie włącza LIVE."
        ),
        "occurred_at": occurred_at,
        "token": f"forex-v3-shadow-ready:{fingerprint}",
    }


__all__ = [
    "forward_review_milestone",
    "v3_forward_progress_milestones",
    "v3_shadow_readiness_milestone",
]
