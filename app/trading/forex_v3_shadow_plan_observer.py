"""Safely compute and archive V3 shadow plans without executing them."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
)
from app.trading.forex_v3_shadow_plan_journal import (
    ForexV3ShadowPlanJournal,
)
from app.trading.forex_v3_shadow_planner import ForexV3ShadowPlanner


class ForexV3ShadowPlanObserver:
    """Archive a V3 decision only when its isolated ledger is initialized."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        planner: ForexV3ShadowPlanner | None = None,
        journal: ForexV3ShadowPlanJournal | None = None,
    ) -> None:
        self.planner = planner or ForexV3ShadowPlanner(project_root)
        self.journal = journal or ForexV3ShadowPlanJournal(project_root)

    def observe(
        self,
        *,
        quotes: Mapping[str, ForexQuote],
        bars: Mapping[str, Iterable[ForexBar]],
        contexts: Mapping[str, ForexSafetyContext],
        conversion_quotes: Iterable[ForexQuote],
        cycle_id: object,
        now: datetime,
    ) -> dict[str, Any]:
        plan = self.planner.plan(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            conversion_quotes=conversion_quotes,
            cycle_id=f"shadow-plan-{str(cycle_id or '').strip()}",
            now=now,
        )
        if plan.get("status") != "SHADOW_PLAN_COMPUTED":
            return self._result(
                "SHADOW_PLAN_OBSERVATION_WAITING",
                plan=plan,
                journal_status="NOT_WRITTEN",
            )
        recorded = self.journal.record(plan)
        journal_status = str(recorded.get("status", ""))
        if journal_status == "SHADOW_PLAN_RECORDED":
            status = "SHADOW_PLAN_OBSERVED"
        elif journal_status == "DUPLICATE_SHADOW_PLAN":
            status = "SHADOW_PLAN_ALREADY_OBSERVED"
        else:
            status = "SHADOW_PLAN_OBSERVATION_BLOCKED"
        return self._result(
            status,
            plan=plan,
            journal_status=journal_status,
        )

    def _result(
        self,
        status: str,
        *,
        plan: Mapping[str, Any],
        journal_status: str,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "mode": "FOREX_V3_SHADOW_PLAN_OBSERVATION_ONLY",
            "journal_status": journal_status,
            "journal_summary": self.journal.summary(),
            "plan": dict(plan),
            "shadow_execution_enabled": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }


__all__ = ["ForexV3ShadowPlanObserver"]
