"""Owner-visible events for isolated V3 SHADOW PAPER fills."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping


_FILL_ID = re.compile(r"^forex-v3-shadow-[0-9a-f]{32}$")
_PAIR = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")
_ACTIONS = frozenset({
    "OPEN_LONG",
    "OPEN_SHORT",
    "CLOSE_LONG",
    "CLOSE_SHORT",
})
_SIMULATION_SAFE_FALSE_FLAGS = (
    "broker_orders_sent",
    "live_orders_sent",
    "network_access",
    "real_money_access",
)


def _timestamp(value: object) -> str:
    selected = " ".join(str(value or "").split())[:64]
    try:
        parsed = datetime.fromisoformat(selected.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return ""
    return parsed.astimezone(timezone.utc).isoformat()


def _pnl(value: object) -> str:
    try:
        selected = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if not selected.is_finite() or abs(selected) > Decimal("1000000000000"):
        return ""
    return f"{selected:.2f}"


def _fill_spec(fill: Mapping[str, Any]) -> dict[str, str] | None:
    fill_id = str(fill.get("fill_id", "")).strip().lower()
    action = str(fill.get("action", "")).strip().upper()
    pair = str(fill.get("pair", "")).strip().upper()
    occurred_at = _timestamp(fill.get("filled_at"))
    if (
        not _FILL_ID.fullmatch(fill_id)
        or action not in _ACTIONS
        or not _PAIR.fullmatch(pair)
        or not occurred_at
    ):
        return None
    visible_pair = pair.replace("_", "/")
    side = action.split("_", 1)[1]
    if action.startswith("OPEN_"):
        kind = "FOREX_V3_SHADOW_POSITION_OPENED"
        message = (
            f"Forex V3 SHADOW PAPER: otworzyłem symulowaną pozycję {side} "
            f"na {visible_pair}. To wyłącznie izolowana symulacja; broker, "
            "LIVE, sieć wykonawcza i prawdziwe środki pozostają zablokowane."
        )
    else:
        realized = _pnl(fill.get("realized_pnl_pln"))
        if not realized:
            return None
        kind = "FOREX_V3_SHADOW_POSITION_CLOSED"
        message = (
            f"Forex V3 SHADOW PAPER: zamknąłem symulowaną pozycję {side} "
            f"na {visible_pair}; wynik {realized} PLN. To wyłącznie izolowana "
            "symulacja; broker, LIVE, sieć wykonawcza i prawdziwe środki "
            "pozostają zablokowane."
        )
    return {
        "kind": kind,
        "state": "important",
        "message": message,
        "occurred_at": occurred_at,
        "token": f"forex-v3-shadow-fill:{fill_id}",
    }


def v3_shadow_trade_specs(payload: object) -> list[dict[str, str]]:
    """Return strictly verified owner events for newly simulated V3 fills."""

    if not isinstance(payload, Mapping) or any(
        payload.get(field) is not False
        for field in ("broker_orders_sent", "live_orders_sent", "real_money_access")
    ):
        return []
    simulation = payload.get("v3_shadow_simulation")
    if not isinstance(simulation, Mapping) or (
        simulation.get("status") != "SHADOW_SIMULATION_CYCLE_COMPLETED"
        or simulation.get("mode") != "FOREX_V3_SHADOW_PAPER_ONLY"
        or simulation.get("shadow_execution_enabled") is not True
        or any(
            simulation.get(field) is not False
            for field in _SIMULATION_SAFE_FALSE_FLAGS
        )
    ):
        return []
    execution = simulation.get("execution")
    if not isinstance(execution, Mapping) or (
        execution.get("status") not in {"APPLIED", "NO_EXECUTION"}
        or execution.get("mode") != "FOREX_V3_SHADOW_PAPER_ONLY"
        or execution.get("live_orders_sent") is not False
        or execution.get("network_access") is not False
    ):
        return []
    raw_executions = execution.get("executions", [])
    if not isinstance(raw_executions, list) or len(raw_executions) > 7:
        return []
    specs: list[dict[str, str]] = []
    for raw in raw_executions:
        if not isinstance(raw, Mapping) or raw.get("status") != "EXECUTED":
            return []
        fill = raw.get("fill")
        if not isinstance(fill, Mapping):
            return []
        spec = _fill_spec(fill)
        if spec is None:
            return []
        specs.append(spec)
    if simulation.get("paper_orders_sent") is not bool(specs):
        return []
    return specs


__all__ = ["v3_shadow_trade_specs"]
