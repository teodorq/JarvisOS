"""Compose read-only market data with local PAPER execution only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.market_data.forex_environment import ForexDataSettings
from app.market_data.forex_gateway import ForexReadOnlyDataGateway
from app.market_data.forex_models import ForexDataBundle
from app.trading.forex_autopilot import ForexPaperAutopilot
from app.trading.forex_forward_evidence import (
    ForexV2ForwardEvidenceReport,
    ForexV3ForwardEvidenceReport,
)
from app.trading.forex_forward_review import ForexV2OwnerReviewPacket
from app.trading.forex_observation import (
    ForexObservationJournal,
    ForexObservationService,
)
from app.trading.forex_performance_review import (
    ForexPaperPerformanceReviewPacket,
)
from app.trading.forex_risk import ForexRateBook
from app.trading.forex_v3_shadow_plan_observer import (
    ForexV3ShadowPlanObserver,
)
from app.trading.forex_v3_shadow_simulation import (
    ForexV3ShadowSimulationActivator,
    ForexV3ShadowSimulationEngine,
)
from app.trading.models import TradingValidationError, aware_utc


class ForexDemoPaperRuntime:
    """Observe once and apply the same inputs to a PAPER-only ledger."""

    def __init__(
        self,
        project_root: str | Path | None,
        *,
        settings: ForexDataSettings,
        gateway: ForexReadOnlyDataGateway | None = None,
        journal: ForexObservationJournal | None = None,
        autopilot: ForexPaperAutopilot | None = None,
        forward_evidence: ForexV2ForwardEvidenceReport | None = None,
        v3_forward_evidence: ForexV3ForwardEvidenceReport | None = None,
        forward_review: ForexV2OwnerReviewPacket | None = None,
        performance_review: ForexPaperPerformanceReviewPacket | None = None,
        v3_shadow_observer: ForexV3ShadowPlanObserver | None = None,
        v3_shadow_activator: ForexV3ShadowSimulationActivator | None = None,
        v3_shadow_executor: ForexV3ShadowSimulationEngine | None = None,
    ) -> None:
        self.project_root = project_root
        self.settings = settings
        self.gateway = gateway or ForexReadOnlyDataGateway(settings)
        self.journal = journal or ForexObservationJournal(project_root)
        self.autopilot = autopilot or ForexPaperAutopilot(project_root)
        self.forward_evidence = forward_evidence or ForexV2ForwardEvidenceReport(
            project_root
        )
        self.v3_forward_evidence = (
            v3_forward_evidence
            or ForexV3ForwardEvidenceReport(project_root)
        )
        self.forward_review = forward_review or ForexV2OwnerReviewPacket(project_root)
        self.performance_review = (
            performance_review
            or ForexPaperPerformanceReviewPacket(project_root)
        )
        self.v3_shadow_observer = (
            v3_shadow_observer
            or ForexV3ShadowPlanObserver(project_root)
        )
        self.v3_shadow_executor = (
            v3_shadow_executor
            or ForexV3ShadowSimulationEngine(project_root)
        )
        self.v3_shadow_activator = (
            v3_shadow_activator
            or ForexV3ShadowSimulationActivator(project_root)
        )

    def run_once(
        self,
        *,
        cycle_id: object,
        now: datetime | None = None,
        capture_origin: object = "MANUAL",
        capture_attestation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected_id = str(cycle_id or "").strip()
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        if not self.settings.paper_autopilot_enabled:
            return self._blocked(selected_id, "PAPER_AUTOPILOT_NOT_ENABLED")
        if self.settings.primary_provider not in {
            "MT5_DEMO",
            "TWELVE_DATA_CLOUD",
        }:
            return self._blocked(selected_id, "PAPER_PRIMARY_NOT_APPROVED")
        try:
            bundle = self.gateway.collect(now=selected_now)
            observation = ForexObservationService(
                self.project_root,
                gateway=self.gateway,
                journal=self.journal,
            ).observe_once(
                observation_id=f"paper-observation-{selected_id}",
                now=selected_now,
                bundle=bundle,
                capture_origin=capture_origin,
                capture_attestation=capture_attestation,
            )
            forward_evidence = self._refresh_forward_evidence(selected_now)
            v3_forward_evidence = self._refresh_v3_forward_evidence(selected_now)
            forward_review = self._refresh_forward_review(
                forward_evidence,
                selected_now,
            )
            close_only = self._verified_close_only(observation)
            scoped_entries = self._verified_scoped_entries(observation)
            opening_blocked = bool(observation.get("opening_blocks"))
            if (
                observation.get("status") != "OBSERVATION_RECORDED"
                or observation.get("fully_cross_checked") is not True
                or (opening_blocked and not (close_only or scoped_entries))
                or observation.get("positions_unchanged") is not True
            ):
                return self._blocked(
                    selected_id,
                    "CURRENT_OBSERVATION_BLOCKED",
                    observation=observation,
                    forward_evidence=forward_evidence,
                    v3_forward_evidence=v3_forward_evidence,
                    forward_review=forward_review,
                )
            review = self.journal.review()
            if review.get("owner_review_ready") is not True:
                return self._blocked(
                    selected_id,
                    "OBSERVATION_REVIEW_GATE_NOT_READY",
                    observation=observation,
                    forward_evidence=forward_evidence,
                    v3_forward_evidence=v3_forward_evidence,
                    forward_review=forward_review,
                )
            v3_shadow_activation = self._activate_v3_shadow_simulation()
            v3_shadow_plan = self._observe_v3_shadow_plan(
                bundle=bundle,
                cycle_id=selected_id,
                now=selected_now,
            )
            v3_shadow_simulation = self._execute_v3_shadow_plan(
                bundle=bundle,
                observation=v3_shadow_plan,
                now=selected_now,
            )
            paper = self.autopilot.run_cycle(
                quotes=bundle.quotes,
                bars=bundle.bars,
                contexts=bundle.contexts,
                conversion_quotes=bundle.conversion_quotes,
                cycle_id=f"paper-cycle-{selected_id}",
                allow_new_entries=(
                    self.settings.base_new_entries_enabled
                    and not close_only
                ),
                now=selected_now,
            )
            performance_review = self._refresh_performance_review(
                paper,
                selected_now,
            )
        except (OSError, RuntimeError, TradingValidationError) as error:
            return self._blocked(
                selected_id,
                str(error)[:160] or "PAPER_CYCLE_FAILED",
            )
        return {
            "status": "PAPER_CYCLE_COMPLETED",
            "mode": self._runtime_mode(),
            "cycle_id": selected_id,
            "observed_at": selected_now.isoformat(),
            "primary_provider": self.settings.primary_provider,
            "strategy": "PAPER_BASE_SCANNER_10_30",
            "unvalidated_strategy_demo_override": (
                self.settings.base_new_entries_enabled
            ),
            "base_new_entries_enabled": (
                self.settings.base_new_entries_enabled
            ),
            "observation": observation,
            "forward_evidence": forward_evidence,
            "v3_forward_evidence": v3_forward_evidence,
            "forward_review": forward_review,
            "v3_shadow_plan_observation": v3_shadow_plan,
            "v3_shadow_activation": v3_shadow_activation,
            "v3_shadow_simulation": v3_shadow_simulation,
            "paper": paper,
            "performance_review": performance_review,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    def _activate_v3_shadow_simulation(self) -> dict[str, Any]:
        if not self.settings.v3_shadow_simulation_enabled:
            return self._v3_simulation_result(
                "SHADOW_SIMULATION_DISABLED",
                "CONFIGURATION_DISABLED",
            )
        try:
            existing = self.v3_shadow_activator.activate(confirmation="")
            if existing.get("status") == "ALREADY_ACTIVE":
                return existing
            gate = self.v3_shadow_activator.readiness.status()
            fingerprint = str(gate.get("review_fingerprint_sha256", ""))
            if (
                not self.settings.v3_shadow_review_fingerprint
                or fingerprint
                != self.settings.v3_shadow_review_fingerprint
            ):
                return self._v3_simulation_result(
                    "SHADOW_SIMULATION_ACTIVATION_BLOCKED",
                    "REVIEW_FINGERPRINT_MISMATCH",
                )
            confirmation = (
                self.v3_shadow_activator.confirmation_for(fingerprint)
                if gate.get("status")
                == "READY_FOR_MANUAL_SIMULATION_INITIALIZATION"
                else ""
            )
            return self.v3_shadow_activator.activate(
                confirmation=confirmation,
            )
        except (
            OSError,
            RuntimeError,
            TradingValidationError,
            TypeError,
            ValueError,
        ) as error:
            return self._v3_simulation_result(
                "SHADOW_SIMULATION_ACTIVATION_BLOCKED",
                str(error)[:160] or "ACTIVATION_FAILED",
            )

    def _execute_v3_shadow_plan(
        self,
        *,
        bundle: ForexDataBundle,
        observation: Mapping[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        if not self.settings.v3_shadow_simulation_enabled:
            return self._v3_simulation_result(
                "SHADOW_SIMULATION_DISABLED",
                "CONFIGURATION_DISABLED",
            )
        plan = observation.get("plan")
        if not isinstance(plan, Mapping) or observation.get("status") not in {
            "SHADOW_PLAN_OBSERVED",
            "SHADOW_PLAN_ALREADY_OBSERVED",
        }:
            return self._v3_simulation_result(
                "SHADOW_SIMULATION_WAITING",
                str(observation.get("status", "PLAN_UNAVAILABLE")),
            )
        try:
            all_quotes = [
                *bundle.quotes.values(),
                *bundle.conversion_quotes,
            ]
            rates = ForexRateBook(
                all_quotes,
                now=now,
                max_age_seconds=(
                    self.v3_shadow_executor.policy.max_conversion_age_seconds
                ),
            )
            execution = self.v3_shadow_executor.apply_plan(
                plan,
                quotes=bundle.quotes,
                rates=rates,
                cycle_id=str(plan.get("cycle_id", "")),
                now=now,
            )
            account = self.v3_shadow_executor.status(
                quotes=bundle.quotes,
                rates=rates,
                now=now,
            )
            return {
                "status": "SHADOW_SIMULATION_CYCLE_COMPLETED",
                "mode": "FOREX_V3_SHADOW_PAPER_ONLY",
                "execution": execution,
                "account": account,
                "shadow_execution_enabled": True,
                "paper_orders_sent": bool(execution.get("executions")),
                "broker_orders_sent": False,
                "live_orders_sent": False,
                "network_access": False,
                "real_money_access": False,
            }
        except (
            OSError,
            RuntimeError,
            TradingValidationError,
            TypeError,
            ValueError,
        ) as error:
            return self._v3_simulation_result(
                "SHADOW_SIMULATION_BLOCKED",
                str(error)[:160] or "SIMULATION_FAILED",
            )

    @staticmethod
    def _v3_simulation_result(status: str, reason: str) -> dict[str, Any]:
        return {
            "status": status,
            "mode": "FOREX_V3_SHADOW_PAPER_ONLY",
            "reason": str(reason)[:160],
            "executions": [],
            "shadow_execution_enabled": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }

    def _observe_v3_shadow_plan(
        self,
        *,
        bundle: ForexDataBundle,
        cycle_id: str,
        now: datetime,
    ) -> dict[str, Any]:
        try:
            return self.v3_shadow_observer.observe(
                quotes=bundle.quotes,
                bars=bundle.bars,
                contexts=bundle.contexts,
                conversion_quotes=bundle.conversion_quotes,
                cycle_id=cycle_id,
                now=now,
            )
        except (
            OSError,
            RuntimeError,
            TradingValidationError,
            TypeError,
            ValueError,
        ):
            return {
                "status": "SHADOW_PLAN_OBSERVER_FAILED",
                "mode": "FOREX_V3_SHADOW_PLAN_OBSERVATION_ONLY",
                "plan": {},
                "shadow_execution_enabled": False,
                "paper_orders_sent": False,
                "broker_orders_sent": False,
                "live_orders_sent": False,
                "network_access": False,
                "real_money_access": False,
            }

    @staticmethod
    def _report_write_failed(
        mode: str = "FOREX_V2_FORWARD_SIGNAL_EVIDENCE_ONLY",
    ) -> dict[str, Any]:
        return {
            "status": "REPORT_WRITE_FAILED",
            "mode": mode,
            "source_state_valid": False,
            "strategy_performance_validated": False,
            "automatic_paper_promotion": False,
            "automatic_live_promotion": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    def _refresh_forward_evidence(self, now: datetime) -> dict[str, Any]:
        try:
            return self.forward_evidence.refresh(generated_at=now)
        except (OSError, RuntimeError, TradingValidationError):
            return self._report_write_failed()

    def _refresh_v3_forward_evidence(self, now: datetime) -> dict[str, Any]:
        try:
            return self.v3_forward_evidence.refresh(generated_at=now)
        except (OSError, RuntimeError, TradingValidationError):
            return self._report_write_failed(
                "FOREX_V3_FORWARD_SIGNAL_EVIDENCE_ONLY"
            )

    def _refresh_forward_review(
        self,
        forward_evidence: Mapping[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        try:
            return self.forward_review.refresh(
                forward_evidence,
                generated_at=now,
            )
        except (OSError, RuntimeError, TradingValidationError):
            return {
                "status": "REVIEW_PACKET_WRITE_FAILED",
                "mode": "FOREX_V2_OWNER_REVIEW_READ_ONLY",
                "performance_validated": False,
                "profitability_validated": False,
                "paper_activation_ready": False,
                "live_activation_ready": False,
                "paper_orders_sent": False,
                "live_orders_sent": False,
                "real_money_access": False,
            }

    def _refresh_performance_review(
        self,
        paper: Mapping[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        try:
            return self.performance_review.refresh(
                paper.get("account"),
                generated_at=now,
            )
        except (OSError, RuntimeError, TradingValidationError):
            return {
                "status": "PERFORMANCE_REVIEW_PACKET_WRITE_FAILED",
                "mode": "FOREX_PAPER_PERFORMANCE_OWNER_REVIEW_READ_ONLY",
                "performance_validated": False,
                "profitability_validated": False,
                "paper_strategy_change_ready": False,
                "live_activation_ready": False,
                "broker_orders_sent": False,
                "live_orders_sent": False,
                "real_money_access": False,
            }

    @staticmethod
    def _verified_close_only(observation: dict[str, Any]) -> bool:
        plan = observation.get("proposed_plan")
        if not isinstance(plan, dict):
            return False
        instructions = plan.get("instructions")
        return bool(
            plan.get("mode") == "FOREX_PAPER_ONLY"
            and plan.get("live_orders_sent") is False
            and plan.get("network_access") is False
            and isinstance(instructions, list)
            and instructions
            and all(
                isinstance(item, dict)
                and item.get("action") == "CLOSE_POSITION"
                and item.get("mode") == "FOREX_PAPER_ONLY"
                for item in instructions
            )
        )

    @staticmethod
    def _verified_scoped_entries(observation: dict[str, Any]) -> bool:
        plan = observation.get("proposed_plan")
        assessments = observation.get("assessments")
        if not isinstance(plan, dict) or not isinstance(assessments, list):
            return False
        instructions = plan.get("instructions")
        if not (
            plan.get("mode") == "FOREX_PAPER_ONLY"
            and plan.get("live_orders_sent") is False
            and plan.get("network_access") is False
            and isinstance(instructions, list)
            and instructions
        ):
            return False
        ready = {
            (item.get("pair"), item.get("action"))
            for item in assessments
            if isinstance(item, dict) and item.get("status") == "READY"
        }
        return all(
            isinstance(item, dict)
            and item.get("action") in {"OPEN_LONG", "OPEN_SHORT"}
            and item.get("mode") == "FOREX_PAPER_ONLY"
            and (item.get("pair"), item.get("action")) in ready
            for item in instructions
        )

    def _blocked(
        self,
        cycle_id: str,
        reason: str,
        *,
        observation: dict[str, Any] | None = None,
        forward_evidence: dict[str, Any] | None = None,
        v3_forward_evidence: dict[str, Any] | None = None,
        forward_review: dict[str, Any] | None = None,
        v3_shadow_plan_observation: dict[str, Any] | None = None,
        v3_shadow_activation: dict[str, Any] | None = None,
        v3_shadow_simulation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "PAPER_CYCLE_BLOCKED",
            "mode": self._runtime_mode(),
            "cycle_id": cycle_id,
            "reason": reason,
            "observation": observation or {},
            "forward_evidence": forward_evidence or {},
            "v3_forward_evidence": v3_forward_evidence or {},
            "forward_review": forward_review or {},
            "v3_shadow_plan_observation": (
                v3_shadow_plan_observation or {}
            ),
            "v3_shadow_activation": v3_shadow_activation or {},
            "v3_shadow_simulation": v3_shadow_simulation or {},
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    def _runtime_mode(self) -> str:
        if self.settings.primary_provider == "TWELVE_DATA_CLOUD":
            return "AUTONOMOUS_AZURE_FOREX_PAPER"
        return "AUTONOMOUS_LOCAL_FOREX_PAPER"


__all__ = ["ForexDemoPaperRuntime"]
