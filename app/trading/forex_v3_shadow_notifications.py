"""Durable owner milestones for the non-executing Forex V3 plan sample."""

from __future__ import annotations

import re
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_FLAGS = (
    "shadow_execution_enabled",
    "paper_orders_sent",
    "broker_orders_sent",
    "live_orders_sent",
    "network_access",
    "real_money_access",
)


def v3_shadow_plan_milestones(
    payload: object,
    *,
    completed_first_fingerprint: object = "",
    completed_sample_fingerprint: object = "",
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Return one-time, review-only milestones from a verified journal summary."""

    if not isinstance(payload, Mapping) or any(
        payload.get(field) is not False
        for field in ("broker_orders_sent", "live_orders_sent", "real_money_access")
    ):
        return {}, []
    observation = payload.get("v3_shadow_plan_observation")
    if not isinstance(observation, Mapping) or (
        observation.get("mode")
        != "FOREX_V3_SHADOW_PLAN_OBSERVATION_ONLY"
        or any(observation.get(field) is not False for field in _SAFE_FLAGS)
    ):
        return {}, []
    summary = observation.get("journal_summary")
    if not isinstance(summary, Mapping) or (
        summary.get("mode") != "FOREX_V3_SHADOW_PLAN_JOURNAL_ONLY"
        or summary.get("audit_chain_valid") is not True
        or any(summary.get(field) is not False for field in _SAFE_FLAGS)
        or summary.get("performance_validated") is not False
        or summary.get("simulation_activation_ready") is not False
    ):
        return {}, []
    integer_fields = (
        "plan_count",
        "minimum_plan_count",
        "remaining_plan_count",
        "market_day_count",
        "minimum_market_day_count",
        "remaining_market_day_count",
        "entry_plan_count",
        "close_plan_count",
        "no_action_plan_count",
        "instruction_count",
        "sample_cutoff_plan_count",
    )
    if any(
        type(summary.get(field)) is not int
        or not 0 <= int(summary[field]) <= 1_000_000
        for field in integer_fields
    ):
        return {}, []
    plan_count = int(summary["plan_count"])
    days = int(summary["market_day_count"])
    if (
        summary.get("status")
        not in {"COLLECTING_SHADOW_PLANS", "SHADOW_PLAN_SAMPLE_COMPLETE"}
        or summary["minimum_plan_count"] != 20
        or summary["minimum_market_day_count"] != 3
        or summary["remaining_plan_count"] != max(0, 20 - plan_count)
        or summary["remaining_market_day_count"] != max(0, 3 - days)
        or summary["entry_plan_count"]
        + summary["close_plan_count"]
        + summary["no_action_plan_count"]
        != plan_count
    ):
        return {}, []
    first_fingerprint = str(summary.get("first_plan_sha256", ""))
    if plan_count <= 0 or not _SHA256.fullmatch(first_fingerprint):
        return {}, []
    occurred_at = " ".join(
        str(summary.get("latest_assessed_at", payload.get("observed_at", ""))).split()
    )[:64]
    fingerprints: dict[str, str] = {}
    milestones: list[dict[str, str]] = []
    if first_fingerprint != str(completed_first_fingerprint):
        fingerprints["v3_shadow_first_plan_fingerprint"] = first_fingerprint
        milestones.append({
            "kind": "FOREX_V3_SHADOW_FIRST_PLAN_RECORDED",
            "state": "brief",
            "message": (
                "Forex V3 SHADOW: zapisałem pierwszy audytowany, niewykonywalny "
                f"plan ({summary.get('latest_decision_status', 'NO_ACTION')}). "
                "Nie utworzyłem pozycji, nie wysłałem zlecenia i nadal zbieram "
                "próbkę planów."
            ),
            "occurred_at": occurred_at,
            "token": f"forex-v3-shadow-first-plan:{first_fingerprint}",
        })
    sample_fingerprint = str(summary.get("sample_fingerprint_sha256", ""))
    sample_complete = bool(
        summary.get("status") == "SHADOW_PLAN_SAMPLE_COMPLETE"
        and summary.get("plan_sample_complete") is True
        and summary["remaining_plan_count"] == 0
        and summary["remaining_market_day_count"] == 0
        and 20 <= summary["sample_cutoff_plan_count"] <= plan_count
        and _SHA256.fullmatch(sample_fingerprint)
    )
    if sample_complete and sample_fingerprint != str(completed_sample_fingerprint):
        fingerprints["v3_shadow_plan_sample_fingerprint"] = sample_fingerprint
        milestones.append({
            "kind": "FOREX_V3_SHADOW_PLAN_SAMPLE_READY",
            "state": "important",
            "message": (
                f"Forex V3 SHADOW: próbka planów osiągnęła {plan_count}/20 "
                f"planów i {days}/3 dni rynkowych. Plany wejścia: "
                f"{summary['entry_plan_count']}; zamknięcia: "
                f"{summary['close_plan_count']}; bez działania: "
                f"{summary['no_action_plan_count']}. To nie jest wynik "
                "finansowy; symulacja pozycji, zmiana PAPER i LIVE pozostają "
                "wyłączone."
            ),
            "occurred_at": occurred_at,
            "token": f"forex-v3-shadow-plan-sample:{sample_fingerprint}",
        })
    return fingerprints, milestones


__all__ = ["v3_shadow_plan_milestones"]
