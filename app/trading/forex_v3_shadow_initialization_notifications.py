"""One-time owner milestone for a safely initialized V3 SHADOW ledger."""

from __future__ import annotations

import hashlib
from typing import Mapping

from app.trading.forex_forward_evidence import (
    verify_forex_v3_forward_evidence_report,
)


_SAFE_FLAGS = (
    "shadow_execution_enabled",
    "paper_orders_sent",
    "broker_orders_sent",
    "live_orders_sent",
    "network_access",
    "real_money_access",
)


def v3_shadow_initialization_milestone(
    payload: object,
    *,
    completed_fingerprint: object = "",
) -> tuple[str, dict[str, str] | None]:
    """Report only a newly created, empty and inactive SHADOW ledger."""

    if not isinstance(payload, Mapping) or any(
        payload.get(field) is not False
        for field in ("broker_orders_sent", "live_orders_sent", "real_money_access")
    ):
        return "", None
    initialization = payload.get("v3_shadow_initialization")
    if not isinstance(initialization, Mapping) or (
        initialization.get("status") != "INITIALIZED_SHADOW_INACTIVE"
        or initialization.get("shadow_ledger_created") is not True
        or any(initialization.get(field) is not False for field in _SAFE_FLAGS)
    ):
        return "", None
    report = payload.get("v3_forward_evidence")
    if not verify_forex_v3_forward_evidence_report(
        report,
        require_complete=True,
    ):
        return "", None
    selected = dict(report)  # type: ignore[arg-type]
    candidate_id = str(initialization.get("candidate_id", ""))
    if not candidate_id or candidate_id != str(selected["candidate_id"]):
        return "", None
    identity = "|".join((
        candidate_id,
        str(selected["content_sha256"]),
        str(selected["source_head_hash"]),
        str(selected["source_cutoff_sequence"]),
        "INITIALIZED_SHADOW_INACTIVE",
    ))
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    if fingerprint == str(completed_fingerprint):
        return fingerprint, None
    occurred_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
    return fingerprint, {
        "kind": "FOREX_V3_SHADOW_INITIALIZED",
        "state": "important",
        "message": (
            "Forex V3 SHADOW: utworzyłem pusty, audytowany i nieaktywny "
            "portfel symulacyjny po kompletnej zweryfikowanej próbce. Nie "
            "otworzyłem pozycji ani nie wysłałem zlecenia; broker, LIVE, "
            "sieć wykonawcza i prawdziwe środki pozostają zablokowane."
        ),
        "occurred_at": occurred_at,
        "token": f"forex-v3-shadow-initialized:{fingerprint}",
    }


__all__ = ["v3_shadow_initialization_milestone"]
