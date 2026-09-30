"""Fail-closed readiness gate for an isolated Forex V3 shadow portfolio."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root
from app.trading.forex_forward_evidence import (
    ForexV3ForwardEvidenceReport,
    verify_forex_v3_forward_evidence_report,
)
from app.trading.forex_v3_shadow_ledger import ForexV3ShadowLedger


class ForexV3ShadowReadiness:
    """Expose readiness facts without creating a ledger or executing a trade."""

    LEDGER_RELATIVE_PATH = ForexV3ShadowLedger.RELATIVE_PATH

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
        ledger_state: dict[str, Any] | None = None
        if self.ledger_path.exists():
            try:
                ledger_state = ForexV3ShadowLedger(
                    self.project_root
                ).snapshot()
            except Exception:
                return self.blocked_status("SHADOW_LEDGER_INVALID")
            initialization = dict(
                ledger_state.get("initialization", {}) or {}
            )
            if (
                ledger_state.get("mode")
                != "FOREX_V3_SHADOW_PAPER_ONLY"
                or initialization.get("status")
                != "INITIALIZED_SHADOW_INACTIVE"
                or initialization.get("execution_enabled") is not False
            ):
                return self.blocked_status(
                    "UNEXPECTED_SHADOW_LEDGER_PRESENT"
                )
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
        if ledger_state is not None and not complete:
            return self.blocked_status(
                "SHADOW_LEDGER_BEFORE_FORWARD_SAMPLE_COMPLETE"
            )
        initialized = ledger_state is not None
        return {
            "status": (
                "SHADOW_INITIALIZED_INACTIVE"
                if initialized
                else (
                    "READY_FOR_MANUAL_SHADOW_INITIALIZATION"
                    if complete
                    else "WAITING_FOR_FORWARD_SAMPLE"
                )
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
            "manual_initialization_required": not initialized,
            "shadow_initialization_ready": complete and not initialized,
            "shadow_ledger_initialized": initialized,
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


class ForexV3ShadowInitializer:
    """Create the inactive V3 state only from complete verified evidence."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        forward_evidence: Any | None = None,
    ) -> None:
        self.readiness = ForexV3ShadowReadiness(
            project_root,
            forward_evidence=forward_evidence,
        )
        self.project_root = self.readiness.project_root
        self.forward_evidence = self.readiness.forward_evidence
        self.ledger_path = self.readiness.ledger_path

    def initialize(self, *, now: datetime | None = None) -> dict[str, Any]:
        if self.ledger_path.exists():
            status = self.readiness.status()
            return {
                "status": (
                    "ALREADY_INITIALIZED_SHADOW_INACTIVE"
                    if status.get("status") == "SHADOW_INITIALIZED_INACTIVE"
                    else "BLOCKED_EXISTING_SHADOW_LEDGER"
                ),
                "reason": str(status.get("reason", "")),
                "shadow_ledger_created": False,
                "shadow_execution_enabled": False,
                "paper_orders_sent": False,
                "broker_orders_sent": False,
                "live_orders_sent": False,
                "network_access": False,
                "real_money_access": False,
            }
        try:
            report = self.forward_evidence.review()
        except Exception:
            return self._blocked("FORWARD_EVIDENCE_UNAVAILABLE")
        if not verify_forex_v3_forward_evidence_report(report):
            return self._blocked("FORWARD_EVIDENCE_INVALID")
        if not verify_forex_v3_forward_evidence_report(
            report,
            require_complete=True,
        ):
            return {
                **self._blocked("FORWARD_SAMPLE_INCOMPLETE"),
                "remaining_accepted_cycles": max(
                    0,
                    int(report.get("remaining_accepted_cycles", 0) or 0),
                ),
                "remaining_market_days": max(
                    0,
                    int(report.get("remaining_market_days", 0) or 0),
                ),
            }
        selected_now = now or datetime.now(timezone.utc)
        if selected_now.tzinfo is None:
            return self._blocked("INITIALIZATION_TIME_NOT_UTC_AWARE")
        selected_now = selected_now.astimezone(timezone.utc)
        ledger = ForexV3ShadowLedger(self.project_root)

        def operation(state: dict[str, Any]) -> None:
            if (
                state.get("mode") != "FOREX_V3_SHADOW_PAPER_ONLY"
                or state.get("positions")
                or state.get("fills")
            ):
                raise RuntimeError("forex_v3_shadow: nonempty_initial_state")
            state["initialization"] = {
                "status": "INITIALIZED_SHADOW_INACTIVE",
                "initialized_at": selected_now.isoformat(),
                "forward_evidence_content_sha256": str(
                    report["content_sha256"]
                ),
                "source_head_hash": str(report["source_head_hash"]),
                "source_cutoff_sequence": int(
                    report["source_cutoff_sequence"]
                ),
                "execution_enabled": False,
            }
            ledger.append_event(
                state,
                "V3_SHADOW_INITIALIZED_INACTIVE",
                {
                    "candidate_id": str(report["candidate_id"]),
                    "forward_evidence_content_sha256": str(
                        report["content_sha256"]
                    ),
                    "source_head_hash": str(report["source_head_hash"]),
                    "source_cutoff_sequence": int(
                        report["source_cutoff_sequence"]
                    ),
                    "sample_contract_id": str(
                        ledger.sample_contract["contract_id"]
                    ),
                    "execution_enabled": False,
                },
                created_at=selected_now,
            )

        try:
            ledger.transaction(operation)
        except Exception:
            return self._blocked("SHADOW_INITIALIZATION_FAILED")
        state = ledger.snapshot()
        if (
            state.get("mode") != "FOREX_V3_SHADOW_PAPER_ONLY"
            or not ForexV3ShadowLedger.verify_audit(state)
        ):
            return self._blocked("SHADOW_LEDGER_POSTCHECK_FAILED")
        return {
            "status": "INITIALIZED_SHADOW_INACTIVE",
            "candidate_id": str(report["candidate_id"]),
            "shadow_ledger_created": True,
            "shadow_execution_enabled": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }

    @staticmethod
    def _blocked(reason: str) -> dict[str, Any]:
        return {
            "status": "BLOCKED_SHADOW_INITIALIZATION",
            "reason": str(reason)[:160],
            "shadow_ledger_created": False,
            "shadow_execution_enabled": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }


__all__ = ["ForexV3ShadowInitializer", "ForexV3ShadowReadiness"]
