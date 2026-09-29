"""Fail-closed readiness gate for an isolated Forex V3 shadow portfolio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root
from app.trading.forex_forward_evidence import (
    ForexV3ForwardEvidenceReport,
    verify_forex_v3_forward_evidence_report,
)


class ForexV3ShadowReadiness:
    """Expose readiness facts without creating a ledger or executing a trade."""

    LEDGER_RELATIVE_PATH = Path(
        "data/trading/research/forex_v3_shadow_ledger.json"
    )

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        forward_evidence: Any | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.forward_evidence = (
            forward_evidence
            if forward_evidence is not None
            else ForexV3ForwardEvidenceReport(self.project_root)
        )
        self.ledger_path = self.project_root / self.LEDGER_RELATIVE_PATH

    def status(self) -> dict[str, Any]:
        try:
            report = self.forward_evidence.review()
        except Exception:
            return self.blocked_status("FORWARD_EVIDENCE_UNAVAILABLE")
        if not verify_forex_v3_forward_evidence_report(report):
            return self.blocked_status("FORWARD_EVIDENCE_INVALID")
        if report.get("source_state_valid") is not True:
            return self.blocked_status("FORWARD_EVIDENCE_SOURCE_INVALID")
        if self.ledger_path.exists():
            return self.blocked_status("UNEXPECTED_SHADOW_LEDGER_PRESENT")
        comparison = dict(report.get("signal_comparison", {}) or {})
        base = self._count(comparison.get("base_entry_signal_count"))
        retained = self._count(comparison.get("retained_entry_signal_count"))
        filtered = self._count(comparison.get("filtered_entry_signal_count"))
        cycles = self._count(report.get("accepted_cycle_count"))
        required_cycles = self._count(
            report.get("minimum_accepted_cycle_count")
        )
        days = self._count(report.get("accepted_market_day_count"))
        required_days = self._count(report.get("minimum_market_day_count"))
        complete = verify_forex_v3_forward_evidence_report(
            report,
            require_complete=True,
        )
        if (
            base != retained + filtered
            or required_cycles <= 0
            or required_days <= 0
            or complete is not (
                cycles >= required_cycles and days >= required_days
            )
        ):
            return self.blocked_status("FORWARD_EVIDENCE_CONTRACT_MISMATCH")
        return {
            "status": (
                "READY_FOR_MANUAL_SHADOW_INITIALIZATION"
                if complete
                else "WAITING_FOR_FORWARD_SAMPLE"
            ),
            "mode": "FOREX_V3_SHADOW_READINESS_ONLY",
            "candidate_id": str(report.get("candidate_id", "")),
            "accepted_cycle_count": cycles,
            "minimum_accepted_cycle_count": required_cycles,
            "remaining_accepted_cycles": max(0, required_cycles - cycles),
            "accepted_market_day_count": days,
            "minimum_market_day_count": required_days,
            "remaining_market_days": max(0, required_days - days),
            "base_entry_signal_count": base,
            "retained_entry_signal_count": retained,
            "filtered_entry_signal_count": filtered,
            "forward_sample_complete": complete,
            "manual_initialization_required": True,
            "shadow_initialization_ready": complete,
            "shadow_ledger_initialized": False,
            "shadow_execution_enabled": False,
            "current_paper_strategy_changed": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }

    @staticmethod
    def blocked_status(reason: str) -> dict[str, Any]:
        return {
            "status": "BLOCKED_INVALID_FORWARD_EVIDENCE",
            "mode": "FOREX_V3_SHADOW_READINESS_ONLY",
            "reason": str(reason)[:160],
            "candidate_id": "FOREX_STRENGTH_V3_20260929",
            "accepted_cycle_count": 0,
            "minimum_accepted_cycle_count": 20,
            "remaining_accepted_cycles": 20,
            "accepted_market_day_count": 0,
            "minimum_market_day_count": 3,
            "remaining_market_days": 3,
            "base_entry_signal_count": 0,
            "retained_entry_signal_count": 0,
            "filtered_entry_signal_count": 0,
            "forward_sample_complete": False,
            "manual_initialization_required": True,
            "shadow_initialization_ready": False,
            "shadow_ledger_initialized": False,
            "shadow_execution_enabled": False,
            "current_paper_strategy_changed": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }

    @staticmethod
    def _count(value: object) -> int:
        if type(value) is not int:
            return 0
        return max(0, min(value, 1_000_000))


__all__ = ["ForexV3ShadowReadiness"]
