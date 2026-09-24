"""Bounded, secret-free summary of the latest Forex PAPER runtime cycle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root


class ForexRuntimeCycleSummary:
    """Read only the latest decisions and safety flags needed by owner views."""

    MAX_RESULT_BYTES = 2_000_000

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.path = root / "data" / "trading" / "forex_paper_last.json"

    def snapshot(self) -> dict[str, Any]:
        try:
            if not self.path.is_file():
                return self.empty_snapshot()
            size = self.path.stat().st_size
            if size <= 0 or size > self.MAX_RESULT_BYTES:
                return self.empty_snapshot()
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {**self.empty_snapshot(), "status": "INVALID_RESULT"}
        if not isinstance(value, dict):
            return {**self.empty_snapshot(), "status": "INVALID_RESULT"}
        try:
            return self.project(value)
        except (TypeError, ValueError, OverflowError, RecursionError, MemoryError):
            return {**self.empty_snapshot(), "status": "INVALID_RESULT"}

    @classmethod
    def project(cls, payload: dict[str, Any]) -> dict[str, Any]:
        paper = payload.get("paper")
        paper = dict(paper) if isinstance(paper, dict) else {}
        observation = payload.get("observation")
        observation = dict(observation) if isinstance(observation, dict) else {}
        opening_blocks = observation.get("opening_blocks")
        high_impact_event_window = bool(
            observation.get("status") == "OBSERVATION_RECORDED"
            and observation.get("fully_cross_checked") is True
            and opening_blocks == ["HIGH_IMPACT_EVENT_WINDOW"]
        )
        raw_assessments = paper.get("assessments")
        raw_assessments = raw_assessments if isinstance(raw_assessments, list) else []
        assessments = [
            dict(item)
            for item in raw_assessments[:20]
            if isinstance(item, dict)
        ]
        execution = paper.get("execution")
        execution = dict(execution) if isinstance(execution, dict) else {}
        raw_executions = execution.get("executions")
        raw_executions = raw_executions if isinstance(raw_executions, list) else []
        executions = [
            dict(item)
            for item in raw_executions[:20]
            if isinstance(item, dict)
        ]
        reasons: dict[str, int] = {}
        top_reason = str(payload.get("reason", "")).strip().upper()[:80]
        if top_reason:
            reasons[top_reason] = 1
        for assessment in assessments:
            raw_reasons = assessment.get("reason_codes")
            raw_reasons = raw_reasons if isinstance(raw_reasons, list) else []
            for raw_code in raw_reasons[:8]:
                code = str(raw_code or "").strip().upper()[:80]
                if code:
                    reasons[code] = reasons.get(code, 0) + 1
        ready_count = sum(item.get("status") == "READY" for item in assessments)
        blocked_count = sum(
            item.get("status") == "BLOCKED" for item in assessments
        )
        outer_status = str(payload.get("status", ""))
        if executions:
            decision = "PAPER_EXECUTED"
        elif (
            outer_status != "PAPER_CYCLE_COMPLETED"
            or str(paper.get("status", "")) == "DATA_BLOCKED"
        ):
            decision = "DATA_BLOCKED"
        elif blocked_count and not ready_count:
            decision = "PAIR_DATA_BLOCKED"
        else:
            decision = "NO_ENTRY_SIGNAL"
        unsafe = any(
            payload.get(key) is not False
            for key in (
                "broker_orders_sent",
                "live_orders_sent",
                "real_money_access",
            )
        )
        return {
            "available": True,
            "status": "SAFETY_VIOLATION" if unsafe else outer_status,
            "observed_at": str(payload.get("observed_at", ""))[:64],
            "decision": decision,
            "ready_pair_count": ready_count,
            "blocked_pair_count": blocked_count,
            "execution_count": len(executions),
            "reason_codes": dict(
                sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
            ),
            "high_impact_event_window": high_impact_event_window,
            "broker_orders_sent": payload.get("broker_orders_sent") is True,
            "live_orders_sent": payload.get("live_orders_sent") is True,
            "real_money_access": payload.get("real_money_access") is True,
        }

    @staticmethod
    def empty_snapshot() -> dict[str, Any]:
        return {
            "available": False,
            "status": "NO_RESULT",
            "observed_at": "",
            "decision": "NO_RECORDED_CYCLE",
            "ready_pair_count": 0,
            "blocked_pair_count": 0,
            "execution_count": 0,
            "reason_codes": {},
            "high_impact_event_window": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }


__all__ = ["ForexRuntimeCycleSummary"]
