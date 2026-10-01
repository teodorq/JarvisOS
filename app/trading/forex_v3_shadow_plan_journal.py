"""Bounded, tamper-evident archive of non-executable Forex V3 plans."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Mapping

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.trading.forex_v3_shadow_planner import (
    verify_forex_v3_shadow_plan,
)


_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _shared_lock(path: Path) -> threading.RLock:
    key = str(path).casefold()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


class ForexV3ShadowPlanJournal:
    """Archive plans only; never persist positions, fills or permissions."""

    RELATIVE_PATH = Path(
        "data/trading/research/forex_v3_shadow_plans.json"
    )
    MODE = "FOREX_V3_SHADOW_PLAN_JOURNAL_ONLY"
    MAX_PLANS = 500
    MAX_BYTES = 20_000_000
    MINIMUM_PLAN_COUNT = 20
    MINIMUM_MARKET_DAY_COUNT = 3
    MINIMUM_ENTRY_PLAN_COUNT = 3

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.path = root / self.RELATIVE_PATH
        self.store = JsonStore(self.path, self._default)
        self._lock = _shared_lock(self.path)

    @classmethod
    def _default(cls) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mode": cls.MODE,
            "next_sequence": 1,
            "head_hash": "",
            "plans": [],
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._load())

    def summary(self) -> dict[str, Any]:
        state = self.snapshot()
        valid = self.verify(state)
        plans = list(state.get("plans", []) or []) if valid else []
        decisions = {
            "ENTRIES_READY": 0,
            "CLOSES_READY": 0,
            "NO_ACTION": 0,
        }
        instruction_count = 0
        market_days: set[str] = set()
        sample_cutoff_plan_count = 0
        sample_fingerprint_sha256 = ""
        review_cutoff_plan_count = 0
        review_fingerprint_sha256 = ""
        entry_plan_seen = 0
        for entry in plans:
            decision = str(entry.get("decision_status", ""))
            if decision in decisions:
                decisions[decision] += 1
            if decision == "ENTRIES_READY":
                entry_plan_seen += 1
            count = entry.get("instruction_count")
            if type(count) is int and count >= 0:
                instruction_count += count
            try:
                assessed_at = datetime.fromisoformat(
                    str(entry.get("assessed_at", ""))
                )
                if assessed_at.tzinfo is not None:
                    market_days.add(assessed_at.date().isoformat())
            except (TypeError, ValueError, OverflowError):
                pass
            if (
                not sample_cutoff_plan_count
                and len(market_days) >= self.MINIMUM_MARKET_DAY_COUNT
                and int(entry.get("sequence", 0)) >= self.MINIMUM_PLAN_COUNT
            ):
                sample_cutoff_plan_count = int(entry["sequence"])
                identity = {
                    "mode": self.MODE,
                    "cutoff_plan_count": sample_cutoff_plan_count,
                    "plan_sha256": [
                        str(item.get("plan_sha256", ""))
                        for item in plans[:sample_cutoff_plan_count]
                    ],
                }
                encoded = json.dumps(
                    identity,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                sample_fingerprint_sha256 = hashlib.sha256(encoded).hexdigest()
            if (
                not review_cutoff_plan_count
                and len(market_days) >= self.MINIMUM_MARKET_DAY_COUNT
                and int(entry.get("sequence", 0)) >= self.MINIMUM_PLAN_COUNT
                and entry_plan_seen >= self.MINIMUM_ENTRY_PLAN_COUNT
            ):
                review_cutoff_plan_count = int(entry["sequence"])
                identity = {
                    "mode": self.MODE,
                    "purpose": "V3_SHADOW_SIMULATION_REVIEW",
                    "cutoff_plan_count": review_cutoff_plan_count,
                    "plan_sha256": [
                        str(item.get("plan_sha256", ""))
                        for item in plans[:review_cutoff_plan_count]
                    ],
                }
                encoded = json.dumps(
                    identity,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                review_fingerprint_sha256 = hashlib.sha256(encoded).hexdigest()
        latest = dict(plans[-1]) if plans else {}
        first = dict(plans[0]) if plans else {}
        plan_sample_complete = bool(sample_cutoff_plan_count)
        simulation_review_ready = bool(review_cutoff_plan_count)
        return {
            "status": (
                "BLOCKED_SHADOW_PLAN_JOURNAL_INVALID"
                if not valid
                else "SHADOW_PLAN_SAMPLE_REVIEW_READY"
                if simulation_review_ready
                else "SHADOW_PLAN_SAMPLE_SIGNAL_SCARCE"
                if plan_sample_complete
                else "COLLECTING_SHADOW_PLANS"
                if plans
                else "WAITING_FOR_FIRST_SHADOW_PLAN"
            ),
            "mode": self.MODE,
            "journal_initialized": self.path.exists(),
            "audit_chain_valid": valid,
            "plan_count": len(plans),
            "minimum_plan_count": self.MINIMUM_PLAN_COUNT,
            "remaining_plan_count": max(
                0,
                self.MINIMUM_PLAN_COUNT - len(plans),
            ),
            "market_day_count": len(market_days),
            "minimum_market_day_count": self.MINIMUM_MARKET_DAY_COUNT,
            "remaining_market_day_count": max(
                0,
                self.MINIMUM_MARKET_DAY_COUNT - len(market_days),
            ),
            "plan_sample_complete": plan_sample_complete,
            "sample_cutoff_plan_count": sample_cutoff_plan_count,
            "sample_fingerprint_sha256": sample_fingerprint_sha256,
            "first_plan_sha256": str(first.get("plan_sha256", "")),
            "minimum_entry_plan_count": self.MINIMUM_ENTRY_PLAN_COUNT,
            "remaining_entry_plan_count": max(
                0,
                self.MINIMUM_ENTRY_PLAN_COUNT - decisions["ENTRIES_READY"],
            ),
            "signal_sample_sufficient": (
                decisions["ENTRIES_READY"] >= self.MINIMUM_ENTRY_PLAN_COUNT
            ),
            "signal_scarcity_detected": bool(
                plan_sample_complete
                and decisions["ENTRIES_READY"] < self.MINIMUM_ENTRY_PLAN_COUNT
            ),
            "review_cutoff_plan_count": review_cutoff_plan_count,
            "review_fingerprint_sha256": review_fingerprint_sha256,
            "performance_validated": False,
            "simulation_review_ready": simulation_review_ready,
            "simulation_activation_ready": False,
            "instruction_count": instruction_count,
            "entry_plan_count": decisions["ENTRIES_READY"],
            "close_plan_count": decisions["CLOSES_READY"],
            "no_action_plan_count": decisions["NO_ACTION"],
            "latest_cycle_id": str(latest.get("cycle_id", "")),
            "latest_assessed_at": str(latest.get("assessed_at", "")),
            "latest_decision_status": str(
                latest.get("decision_status", "")
            ),
            "shadow_execution_enabled": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }

    def record(self, plan: object) -> dict[str, Any]:
        if not verify_forex_v3_shadow_plan(plan):
            return {"status": "INVALID_SHADOW_PLAN", "plans_recorded": 0}
        selected = deepcopy(dict(plan))  # type: ignore[arg-type]
        cycle_id = str(selected["cycle_id"])
        plan_sha256 = str(selected["plan_sha256"])
        with self._lock:
            state = self._load()
            if state.get("mode") != self.MODE or not self.verify(state):
                return {
                    "status": "BLOCKED_SHADOW_PLAN_JOURNAL_INVALID",
                    "plans_recorded": 0,
                }
            for entry in state["plans"]:
                if entry.get("cycle_id") != cycle_id:
                    continue
                return {
                    "status": (
                        "DUPLICATE_SHADOW_PLAN"
                        if entry.get("plan_sha256") == plan_sha256
                        else "BLOCKED_SHADOW_PLAN_CYCLE_CONFLICT"
                    ),
                    "plans_recorded": 0,
                }
            if len(state["plans"]) >= self.MAX_PLANS:
                return {
                    "status": "BLOCKED_SHADOW_PLAN_JOURNAL_FULL",
                    "plans_recorded": 0,
                }
            entry = {
                "sequence": state["next_sequence"],
                "cycle_id": cycle_id,
                "assessed_at": str(selected["assessed_at"]),
                "decision_status": str(selected["decision_status"]),
                "instruction_count": len(selected["instructions"]),
                "shadow_ledger_audit_head": str(
                    selected["shadow_ledger_audit_head"]
                ),
                "plan_sha256": plan_sha256,
                "plan": selected,
                "previous_hash": str(state["head_hash"]),
            }
            entry["entry_hash"] = self._entry_hash(entry)
            state["plans"].append(entry)
            state["next_sequence"] += 1
            state["head_hash"] = entry["entry_hash"]
            self.store.save(state)
        return {"status": "SHADOW_PLAN_RECORDED", "plans_recorded": 1}

    @classmethod
    def verify(cls, state: object) -> bool:
        if not isinstance(state, Mapping):
            return False
        value = dict(state)
        plans = value.get("plans")
        if (
            value.get("schema_version") != 1
            or value.get("mode") != cls.MODE
            or not isinstance(plans, list)
            or len(plans) > cls.MAX_PLANS
            or type(value.get("next_sequence")) is not int
            or value.get("next_sequence") != len(plans) + 1
        ):
            return False
        previous_hash = ""
        cycles: set[str] = set()
        for sequence, raw in enumerate(plans, 1):
            if not isinstance(raw, Mapping):
                return False
            entry = dict(raw)
            cycle_id = str(entry.get("cycle_id", ""))
            plan = entry.get("plan")
            selected_plan = dict(plan) if isinstance(plan, Mapping) else {}
            if (
                entry.get("sequence") != sequence
                or cycle_id in cycles
                or entry.get("previous_hash") != previous_hash
                or not verify_forex_v3_shadow_plan(plan)
                or entry.get("plan_sha256")
                != selected_plan.get("plan_sha256")
                or cycle_id != selected_plan.get("cycle_id")
                or entry.get("assessed_at") != selected_plan.get("assessed_at")
                or entry.get("decision_status")
                != selected_plan.get("decision_status")
                or entry.get("instruction_count")
                != len(list(selected_plan.get("instructions", []) or []))
                or entry.get("shadow_ledger_audit_head")
                != selected_plan.get("shadow_ledger_audit_head")
                or entry.get("entry_hash") != cls._entry_hash(entry)
            ):
                return False
            cycles.add(cycle_id)
            previous_hash = str(entry["entry_hash"])
        return value.get("head_hash") == previous_hash

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            if not 0 < self.path.stat().st_size <= self.MAX_BYTES:
                return {**self._default(), "mode": "INVALID"}
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {**self._default(), "mode": "INVALID"}
        return self._normalized(raw)

    def _normalized(self, value: object) -> dict[str, Any]:
        state = self._default()
        if isinstance(value, Mapping):
            for key in state:
                if key in value:
                    state[key] = deepcopy(value[key])
        if not self.verify(state):
            state["mode"] = "INVALID"
        return state

    @staticmethod
    def _entry_hash(entry: Mapping[str, Any]) -> str:
        payload = {
            key: entry.get(key)
            for key in (
                "sequence",
                "cycle_id",
                "assessed_at",
                "decision_status",
                "instruction_count",
                "shadow_ledger_audit_head",
                "plan_sha256",
                "previous_hash",
            )
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = ["ForexV3ShadowPlanJournal"]
