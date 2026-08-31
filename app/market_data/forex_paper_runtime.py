"""Compose read-only market data with local PAPER execution only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.market_data.forex_environment import ForexDataSettings
from app.market_data.forex_gateway import ForexReadOnlyDataGateway
from app.trading.forex_autopilot import ForexPaperAutopilot
from app.trading.forex_observation import (
    ForexObservationJournal,
    ForexObservationService,
)
from app.trading.models import TradingValidationError, aware_utc


class ForexDemoPaperRuntime:
    """Observe once and then apply the same inputs to the local PAPER ledger."""

    def __init__(
        self,
        project_root: str | Path | None,
        *,
        settings: ForexDataSettings,
        gateway: ForexReadOnlyDataGateway | None = None,
        journal: ForexObservationJournal | None = None,
        autopilot: ForexPaperAutopilot | None = None,
    ) -> None:
        self.project_root = project_root
        self.settings = settings
        self.gateway = gateway or ForexReadOnlyDataGateway(settings)
        self.journal = journal or ForexObservationJournal(project_root)
        self.autopilot = autopilot or ForexPaperAutopilot(project_root)

    def run_once(
        self,
        *,
        cycle_id: object,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        selected_id = str(cycle_id or "").strip()
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        if not self.settings.paper_autopilot_enabled:
            return self._blocked(selected_id, "PAPER_AUTOPILOT_NOT_ENABLED")
        if self.settings.primary_provider != "MT5_DEMO":
            return self._blocked(selected_id, "MT5_DEMO_PRIMARY_REQUIRED")
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
                )
            review = self.journal.review()
            if review.get("owner_review_ready") is not True:
                return self._blocked(
                    selected_id,
                    "OBSERVATION_REVIEW_GATE_NOT_READY",
                    observation=observation,
                )
            paper = self.autopilot.run_cycle(
                quotes=bundle.quotes,
                bars=bundle.bars,
                contexts=bundle.contexts,
                conversion_quotes=bundle.conversion_quotes,
                cycle_id=f"paper-cycle-{selected_id}",
                allow_new_entries=not close_only,
                now=selected_now,
            )
        except (OSError, RuntimeError, TradingValidationError) as error:
            return self._blocked(
                selected_id,
                str(error)[:160] or "PAPER_CYCLE_FAILED",
            )
        return {
            "status": "PAPER_CYCLE_COMPLETED",
            "mode": "AUTONOMOUS_LOCAL_FOREX_PAPER",
            "cycle_id": selected_id,
            "observed_at": selected_now.isoformat(),
            "primary_provider": "MT5_DEMO",
            "strategy": "PAPER_BASE_SCANNER_10_30",
            "unvalidated_strategy_demo_override": True,
            "observation": observation,
            "paper": paper,
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

    @staticmethod
    def _blocked(
        cycle_id: str,
        reason: str,
        *,
        observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "PAPER_CYCLE_BLOCKED",
            "mode": "AUTONOMOUS_LOCAL_FOREX_PAPER",
            "cycle_id": cycle_id,
            "reason": reason,
            "observation": observation or {},
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }


__all__ = ["ForexDemoPaperRuntime"]
