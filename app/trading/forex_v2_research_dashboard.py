"""Sanitized owner projection of verified Forex V2 forward evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root
from app.trading.forex_forward_evidence import (
    ForexV2ForwardEvidenceReport,
    verify_forex_v2_forward_evidence_report,
)
from app.trading.forex_forward_review import (
    ForexV2OwnerReviewPacket,
    verify_forex_v2_owner_review_lineage,
)


class ForexV2ResearchDashboard:
    """Expose bounded signal-sample facts without promotion authority."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        forward_evidence: Any | None = None,
        owner_review: Any | None = None,
    ) -> None:
        root = resolve_project_root(project_root)
        self.forward_evidence = (
            forward_evidence
            if forward_evidence is not None
            else ForexV2ForwardEvidenceReport(root)
        )
        self.owner_review = (
            owner_review
            if owner_review is not None
            else ForexV2OwnerReviewPacket(root)
        )

    def snapshot(self) -> dict[str, Any]:
        try:
            report = self.forward_evidence.review()
            packet = self.owner_review.review(report)
        except Exception:
            return self.blocked_snapshot()
        if not verify_forex_v2_forward_evidence_report(report):
            return self.blocked_snapshot()
        report = dict(report) if isinstance(report, dict) else {}
        packet = dict(packet) if isinstance(packet, dict) else {}
        status = str(packet.get("status", ""))
        frozen = bool(
            status == "READY_FOR_OWNER_REVIEW"
            and verify_forex_v2_owner_review_lineage(report, packet)
        )
        waiting = status == "WAITING_FOR_FORWARD_SAMPLE"
        pending = status == "READY_FOR_OWNER_REVIEW_NOT_PERSISTED"
        if not (frozen or waiting or pending):
            return self.blocked_snapshot()
        comparison = packet.get("signal_comparison")
        comparison = dict(comparison) if isinstance(comparison, dict) else {}
        base = self._count(comparison.get("base_entry_signal_count"))
        retained = self._count(comparison.get("retained_entry_signal_count"))
        filtered = self._count(comparison.get("filtered_entry_signal_count"))
        cycles = self._count(packet.get("accepted_cycle_count"))
        required_cycles = self._count(
            packet.get("minimum_accepted_cycle_count")
        )
        days = self._count(packet.get("accepted_market_day_count"))
        required_days = self._count(packet.get("minimum_market_day_count"))
        if (
            packet.get("source_report_valid") is not True
            or base != retained + filtered
            or required_cycles <= 0
            or required_days <= 0
            or (waiting and cycles >= required_cycles and days >= required_days)
            or ((frozen or pending) and (
                cycles < required_cycles or days < required_days
            ))
        ):
            return self.blocked_snapshot()
        return {
            "status": (
                "READY_FOR_OWNER_REVIEW"
                if frozen
                else "PENDING_IMMUTABLE_REVIEW_PACKET"
                if pending
                else "WAITING_FOR_FORWARD_SAMPLE"
            ),
            "source_valid": True,
            "accepted_cycle_count": cycles,
            "minimum_accepted_cycle_count": required_cycles,
            "accepted_market_day_count": days,
            "minimum_market_day_count": required_days,
            "base_entry_signal_count": base,
            "retained_entry_signal_count": retained,
            "filtered_entry_signal_count": filtered,
            "packet_persisted": packet.get("packet_persisted") is True,
            "review_snapshot_frozen": frozen,
            "signal_sample_only": True,
            "performance_validated": False,
            "automatic_strategy_change": False,
            "paper_activation_ready": False,
            "live_activation_ready": False,
            "real_money_access": False,
        }

    @staticmethod
    def blocked_snapshot() -> dict[str, Any]:
        return {
            "status": "BLOCKED_INVALID_FORWARD_EVIDENCE",
            "source_valid": False,
            "accepted_cycle_count": 0,
            "minimum_accepted_cycle_count": 0,
            "accepted_market_day_count": 0,
            "minimum_market_day_count": 0,
            "base_entry_signal_count": 0,
            "retained_entry_signal_count": 0,
            "filtered_entry_signal_count": 0,
            "packet_persisted": False,
            "review_snapshot_frozen": False,
            "signal_sample_only": True,
            "performance_validated": False,
            "automatic_strategy_change": False,
            "paper_activation_ready": False,
            "live_activation_ready": False,
            "real_money_access": False,
        }

    @staticmethod
    def _count(value: object) -> int:
        try:
            return max(0, min(int(value or 0), 1_000_000))
        except (TypeError, ValueError):
            return 0


__all__ = ["ForexV2ResearchDashboard"]
