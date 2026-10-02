"""Fail-closed readiness gate for a future local V3 shadow simulation."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Mapping

from app.trading.forex_v3_shadow import ForexV3ShadowReadiness
from app.trading.forex_v3_shadow_plan_journal import ForexV3ShadowPlanJournal


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_FLAGS = (
    "shadow_execution_enabled",
    "paper_orders_sent",
    "broker_orders_sent",
    "live_orders_sent",
    "network_access",
    "real_money_access",
)


class ForexV3ShadowSimulationReadiness:
    """Assess simulation readiness without creating or applying any position."""

    MODE = "FOREX_V3_SHADOW_SIMULATION_READINESS_ONLY"

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        shadow_readiness: Any | None = None,
        plan_journal: Any | None = None,
    ) -> None:
        self.shadow_readiness = shadow_readiness or ForexV3ShadowReadiness(
            project_root
        )
        self.plan_journal = plan_journal or ForexV3ShadowPlanJournal(
            project_root
        )

    def status(self) -> dict[str, Any]:
        try:
            shadow = self.shadow_readiness.status()
            plans = self.plan_journal.summary()
        except Exception:
            return self._result(
                "BLOCKED_SIMULATION_READINESS_INVALID",
                "READINESS_SOURCE_UNAVAILABLE",
            )
        if not isinstance(shadow, Mapping) or (
            shadow.get("mode") != "FOREX_V3_SHADOW_READINESS_ONLY"
            or any(shadow.get(field) is not False for field in _SAFE_FLAGS)
        ):
            return self._result(
                "BLOCKED_SIMULATION_READINESS_INVALID",
                "SHADOW_READINESS_INVALID",
            )
        if shadow.get("status") != "SHADOW_INITIALIZED_INACTIVE":
            return self._result(
                "BLOCKED_SHADOW_NOT_INITIALIZED",
                "SHADOW_LEDGER_NOT_INITIALIZED",
            )
        if not isinstance(plans, Mapping) or (
            plans.get("mode") != "FOREX_V3_SHADOW_PLAN_JOURNAL_ONLY"
            or plans.get("audit_chain_valid") is not True
            or any(plans.get(field) is not False for field in _SAFE_FLAGS)
            or plans.get("performance_validated") is not False
            or plans.get("simulation_activation_ready") is not False
        ):
            return self._result(
                "BLOCKED_SIMULATION_READINESS_INVALID",
                "SHADOW_PLAN_JOURNAL_INVALID",
            )
        facts = self._facts(plans)
        plan_status = str(plans.get("status", ""))
        if plan_status in {
            "WAITING_FOR_FIRST_SHADOW_PLAN",
            "COLLECTING_SHADOW_PLANS",
        }:
            return self._result(
                "WAITING_FOR_PLAN_SAMPLE",
                "SHADOW_PLAN_SAMPLE_INCOMPLETE",
                **facts,
            )
        if plan_status == "SHADOW_PLAN_SAMPLE_SIGNAL_SCARCE" and (
            plans.get("plan_sample_complete") is True
            and plans.get("signal_scarcity_detected") is True
            and plans.get("simulation_review_ready") is False
        ):
            return self._result(
                "BLOCKED_SIGNAL_SCARCITY",
                "INSUFFICIENT_ENTRY_PLAN_FREQUENCY",
                **facts,
            )
        review_fingerprint = str(
            plans.get("review_fingerprint_sha256", "")
        )
        if plan_status == "SHADOW_PLAN_SAMPLE_REVIEW_READY" and (
            plans.get("plan_sample_complete") is True
            and plans.get("signal_sample_sufficient") is True
            and plans.get("simulation_review_ready") is True
            and _SHA256.fullmatch(review_fingerprint)
        ):
            return self._result(
                "READY_FOR_MANUAL_SIMULATION_INITIALIZATION",
                "PLAN_SAMPLE_AND_SIGNAL_FREQUENCY_VERIFIED",
                review_fingerprint_sha256=review_fingerprint,
                **facts,
            )
        return self._result(
            "BLOCKED_SIMULATION_READINESS_INVALID",
            "SHADOW_PLAN_SAMPLE_CONTRACT_MISMATCH",
            **facts,
        )

    @staticmethod
    def _facts(plans: Mapping[str, Any]) -> dict[str, int]:
        fields = (
            "plan_count",
            "minimum_plan_count",
            "remaining_plan_count",
            "market_day_count",
            "minimum_market_day_count",
            "remaining_market_day_count",
            "entry_plan_count",
            "minimum_entry_plan_count",
            "remaining_entry_plan_count",
        )
        facts: dict[str, int] = {}
        for field in fields:
            value = plans.get(field)
            facts[field] = (
                value
                if type(value) is int and 0 <= value <= 1_000_000
                else 0
            )
        return facts

    @classmethod
    def _result(
        cls,
        status: str,
        reason: str,
        **facts: Any,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "mode": cls.MODE,
            "reason": str(reason)[:160],
            "review_fingerprint_sha256": str(
                facts.pop("review_fingerprint_sha256", "")
            )[:64],
            **facts,
            "simulation_review_ready": (
                status == "READY_FOR_MANUAL_SIMULATION_INITIALIZATION"
            ),
            "manual_simulation_initialization_required": (
                status == "READY_FOR_MANUAL_SIMULATION_INITIALIZATION"
            ),
            "simulation_initialized": False,
            "shadow_simulation_enabled": False,
            "shadow_execution_enabled": False,
            "performance_validated": False,
            "current_paper_strategy_changed": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }


__all__ = ["ForexV3ShadowSimulationReadiness"]
