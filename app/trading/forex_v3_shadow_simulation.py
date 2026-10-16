"""Fail-closed readiness gate for a future local V3 shadow simulation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping

from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_risk import ForexPaperPolicy
from app.trading.forex_sample_contract import (
    build_forex_v3_shadow_sample_contract,
    verify_forex_v3_shadow_sample_contract,
)
from app.trading.forex_v3_shadow import ForexV3ShadowReadiness
from app.trading.forex_v3_shadow_ledger import ForexV3ShadowLedger
from app.trading.forex_v3_shadow_plan_journal import ForexV3ShadowPlanJournal
from app.trading.forex_v3_shadow_planner import verify_forex_v3_shadow_plan
from app.trading.models import TradingValidationError, aware_utc
from app.trading.paper_broker import LiveTradingBlockedError


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


class ForexV3ShadowSimulationActivator:
    """Activate only the isolated V3 PAPER simulation after exact review."""

    CONFIRMATION_PREFIX = "ACTIVATE V3 SHADOW "

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        readiness: ForexV3ShadowSimulationReadiness | None = None,
        ledger: ForexV3ShadowLedger | None = None,
    ) -> None:
        self.readiness = readiness or ForexV3ShadowSimulationReadiness(
            project_root
        )
        self.ledger = ledger or ForexV3ShadowLedger(project_root)

    @classmethod
    def confirmation_for(cls, fingerprint: object) -> str:
        return cls.CONFIRMATION_PREFIX + str(fingerprint or "").strip()

    def activate(
        self,
        *,
        confirmation: object,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self.ledger.snapshot()
        initialization = dict(current.get("initialization", {}) or {})
        if (
            current.get("mode") == "FOREX_V3_SHADOW_PAPER_ONLY"
            and initialization.get("status")
            == "INITIALIZED_SHADOW_SIMULATION_ACTIVE"
            and initialization.get("execution_enabled") is True
            and self.ledger.verify_audit(current)
        ):
            return self._result("ALREADY_ACTIVE", activated=False)
        gate = self.readiness.status()
        fingerprint = str(gate.get("review_fingerprint_sha256", ""))
        if (
            gate.get("status")
            != "READY_FOR_MANUAL_SIMULATION_INITIALIZATION"
            or not _SHA256.fullmatch(fingerprint)
        ):
            return self._result(
                "BLOCKED_SIMULATION_ACTIVATION",
                reason=str(gate.get("reason", gate.get("status", ""))),
            )
        expected_confirmation = self.confirmation_for(fingerprint)
        if str(confirmation or "").strip() != expected_confirmation:
            return self._result(
                "BLOCKED_SIMULATION_ACTIVATION",
                reason="CONFIRMATION_MISMATCH",
            )
        selected_now = aware_utc(
            now or datetime.now(timezone.utc),
            "simulation_activated_at",
        )

        def operation(state: dict[str, Any]) -> None:
            selected_initialization = dict(
                state.get("initialization", {}) or {}
            )
            if (
                state.get("mode") != "FOREX_V3_SHADOW_PAPER_ONLY"
                or selected_initialization.get("status")
                != "INITIALIZED_SHADOW_INACTIVE"
                or selected_initialization.get("execution_enabled") is not False
                or state.get("positions")
                or state.get("fills")
                or not self.ledger.verify_audit(state)
            ):
                raise TradingValidationError(
                    "forex_v3_shadow_simulation: invalid_inactive_state"
                )
            selected_initialization.update({
                "status": "INITIALIZED_SHADOW_SIMULATION_ACTIVE",
                "simulation_activated_at": selected_now.isoformat(),
                "simulation_review_fingerprint_sha256": fingerprint,
                "execution_enabled": True,
            })
            state["initialization"] = selected_initialization
            self.ledger.append_event(
                state,
                "V3_SHADOW_SIMULATION_ACTIVATED",
                {
                    "review_fingerprint_sha256": fingerprint,
                    "candidate_id": str(state.get("candidate_id", "")),
                    "paper_only": True,
                    "broker_access": False,
                    "real_money_access": False,
                },
                created_at=selected_now,
            )

        try:
            self.ledger.transaction(operation)
            state = self.ledger.snapshot()
        except (OSError, RuntimeError, TradingValidationError, ValueError):
            return self._result(
                "BLOCKED_SIMULATION_ACTIVATION",
                reason="ACTIVATION_TRANSACTION_FAILED",
            )
        active = dict(state.get("initialization", {}) or {})
        if (
            state.get("mode") != "FOREX_V3_SHADOW_PAPER_ONLY"
            or active.get("status")
            != "INITIALIZED_SHADOW_SIMULATION_ACTIVE"
            or active.get("execution_enabled") is not True
            or not self.ledger.verify_audit(state)
        ):
            return self._result(
                "BLOCKED_SIMULATION_ACTIVATION",
                reason="ACTIVATION_POSTCHECK_FAILED",
            )
        return self._result("SIMULATION_ACTIVATED", activated=True)

    @staticmethod
    def _result(
        status: str,
        *,
        activated: bool = False,
        reason: str = "",
    ) -> dict[str, Any]:
        return {
            "status": status,
            "mode": "FOREX_V3_SHADOW_SIMULATION_CONTROL",
            "reason": str(reason)[:160],
            "simulation_activated": activated,
            "shadow_simulation_enabled": status in {
                "SIMULATION_ACTIVATED",
                "ALREADY_ACTIVE",
            },
            "shadow_execution_enabled": status in {
                "SIMULATION_ACTIVATED",
                "ALREADY_ACTIVE",
            },
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }


class ForexV3ShadowSimulationEngine(ForexPaperExecutionEngine):
    """Execute verified V3 plans only inside the isolated PAPER ledger."""

    LEDGER_MODE = "FOREX_V3_SHADOW_PAPER_ONLY"
    PLAN_MODE = "FOREX_V3_SHADOW_PLAN_ONLY"
    EXECUTION_EVENT = "FOREX_V3_SHADOW_SIMULATION_CYCLE"
    FILL_PREFIX = "forex-v3-shadow"
    MODE_ERROR_CODE = "V3_SHADOW_SIMULATION_NOT_ACTIVE"

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: ForexPaperPolicy | None = None,
        ledger: ForexV3ShadowLedger | None = None,
    ) -> None:
        selected_policy = policy or ForexPaperPolicy()
        sample_contract = build_forex_v3_shadow_sample_contract(
            paper_policy=selected_policy
        )
        super().__init__(
            project_root,
            policy=selected_policy,
            ledger=ledger or ForexV3ShadowLedger(
                project_root,
                sample_contract=sample_contract,
            ),
            sample_contract=sample_contract,
        )

    @staticmethod
    def _verify_sample_contract(value: object) -> bool:
        return verify_forex_v3_shadow_sample_contract(value)

    @staticmethod
    def _sample_contracts_match(left: object, right: object) -> bool:
        return bool(
            verify_forex_v3_shadow_sample_contract(left)
            and verify_forex_v3_shadow_sample_contract(right)
            and dict(left) == dict(right)  # type: ignore[arg-type]
        )

    def _validate_plan(self, plan: Mapping[str, Any]) -> None:
        if not verify_forex_v3_shadow_plan(plan):
            raise TradingValidationError(
                "forex_v3_shadow_simulation: invalid_plan"
            )

    def _state_allows_execution(self, state: Mapping[str, Any]) -> bool:
        initialization = dict(state.get("initialization", {}) or {})
        return bool(
            state.get("mode") == self.LEDGER_MODE
            and initialization.get("status")
            == "INITIALIZED_SHADOW_SIMULATION_ACTIVE"
            and initialization.get("execution_enabled") is True
        )

    def _plan_matches_state(
        self,
        plan: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> bool:
        audit = list(state.get("audit", []) or [])
        current_head = str(audit[-1].get("event_hash", "")) if audit else ""
        return str(plan.get("shadow_ledger_audit_head", "")) == current_head

    def apply_plan(
        self,
        plan: Mapping[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        if str(kwargs.get("cycle_id", "")) != str(plan.get("cycle_id", "")):
            raise TradingValidationError(
                "forex_v3_shadow_simulation: cycle_mismatch"
            )
        return super().apply_plan(plan, **kwargs)

    @staticmethod
    def submit_live_order(*_args: object, **_kwargs: object) -> None:
        raise LiveTradingBlockedError(
            "LIVE_TRADING_BLOCKED: V3 działa wyłącznie w symulacji PAPER."
        )


__all__ = [
    "ForexV3ShadowSimulationActivator",
    "ForexV3ShadowSimulationEngine",
    "ForexV3ShadowSimulationReadiness",
]
