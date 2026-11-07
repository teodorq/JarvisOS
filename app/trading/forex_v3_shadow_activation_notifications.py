"""One-time owner milestone for activated V3 SHADOW PAPER simulation."""

from __future__ import annotations

import hashlib
import re
from typing import Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{1,95}$")
_SAFE_FALSE_FLAGS = (
    "paper_orders_sent",
    "broker_orders_sent",
    "live_orders_sent",
    "network_access",
    "real_money_access",
)


def v3_shadow_activation_milestone(
    payload: object,
    *,
    completed_fingerprint: object = "",
) -> tuple[str, dict[str, str] | None]:
    """Report only the first verified activation of isolated PAPER execution."""

    if not isinstance(payload, Mapping) or any(
        payload.get(field) is not False
        for field in ("broker_orders_sent", "live_orders_sent", "real_money_access")
    ):
        return "", None
    activation = payload.get("v3_shadow_activation")
    if not isinstance(activation, Mapping) or (
        activation.get("status") != "SIMULATION_ACTIVATED"
        or activation.get("mode") != "FOREX_V3_SHADOW_SIMULATION_CONTROL"
        or activation.get("simulation_activated") is not True
        or activation.get("shadow_simulation_enabled") is not True
        or activation.get("shadow_execution_enabled") is not True
        or any(activation.get(field) is not False for field in _SAFE_FALSE_FLAGS)
    ):
        return "", None
    review_fingerprint = str(activation.get("review_fingerprint_sha256", ""))
    candidate_id = str(activation.get("candidate_id", ""))
    if (
        not _SHA256.fullmatch(review_fingerprint)
        or not _CANDIDATE.fullmatch(candidate_id)
    ):
        return "", None
    identity = f"{candidate_id}|{review_fingerprint}|SIMULATION_ACTIVATED"
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    if fingerprint == str(completed_fingerprint):
        return fingerprint, None
    occurred_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
    return fingerprint, {
        "kind": "FOREX_V3_SHADOW_SIMULATION_ACTIVATED",
        "state": "important",
        "message": (
            "Forex V3 SHADOW: po zgodności dokładnego odcisku zatwierdzonej "
            "próbki planów uruchomiłem wyłącznie izolowaną symulację PAPER. "
            "Aktywacja nie otworzyła pozycji ani nie wysłała zlecenia; "
            "broker, LIVE, sieć wykonawcza i prawdziwe środki pozostają "
            "zablokowane."
        ),
        "occurred_at": occurred_at,
        "token": f"forex-v3-shadow-activated:{fingerprint}",
    }


__all__ = ["v3_shadow_activation_milestone"]
