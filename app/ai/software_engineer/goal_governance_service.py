from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .autonomy_governance_store import AutonomyGovernanceStore


_PROTECTED_STATES = {"ACTIVE", "WAITING_APPROVAL", "WAITING_RESOURCES", "COMPLETED"}


class GoalGovernanceService:
    """B63 deduplication, staleness governance and subsystem quotas."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        strategic_development: Any,
        strategic_portfolio: Any,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.strategic_development = strategic_development
        self.strategic_portfolio = strategic_portfolio

    def run_cycle(self) -> dict[str, Any]:
        policy = self.store.policy("B63")
        if not bool(policy.get("enabled", True)):
            return self._finish(
                "GOAL_GOVERNANCE_DISABLED",
                success=True,
                phase="DISABLED",
                actions=[],
            )
        goals = self.strategic_development.store.list_goals(limit=1000)
        actions: list[dict[str, Any]] = []
        fingerprints: dict[str, str] = {}
        subsystem_ready: dict[str, list[dict[str, Any]]] = {}

        for goal in sorted(
            goals,
            key=lambda item: (
                float(item.get("priority_score", 0.0) or 0.0),
                float(item.get("confidence", 0.0) or 0.0),
            ),
            reverse=True,
        ):
            goal_id = str(goal.get("goal_id", ""))
            status = str(goal.get("status", "PENDING")).upper()
            subsystem = str(goal.get("subsystem", "unknown")) or "unknown"
            fingerprint = str(goal.get("fingerprint", "")).casefold().strip()
            if not fingerprint:
                fingerprint = "|".join((
                    subsystem.casefold(),
                    str(goal.get("issue_type", "")).casefold(),
                    str(goal.get("title", "")).casefold().strip(),
                ))
            if (
                bool(policy.get("deduplicate", True))
                and fingerprint in fingerprints
                and status not in _PROTECTED_STATES
            ):
                actions.append(self._reject(
                    goal,
                    reason="DUPLICATE",
                    related_goal_id=fingerprints[fingerprint],
                ))
                continue
            fingerprints[fingerprint] = goal_id
            if status in {"PENDING", "READY", "BLOCKED"}:
                subsystem_ready.setdefault(subsystem, []).append(goal)

        quota = int(policy.get("max_ready_goals_per_subsystem", 5))
        for subsystem, values in subsystem_ready.items():
            for goal in values[quota:]:
                if str(goal.get("status", "")).upper() in _PROTECTED_STATES:
                    continue
                actions.append(self._reject(
                    goal,
                    reason="SUBSYSTEM_QUOTA",
                    related_goal_id="",
                ))

        if bool(policy.get("archive_stale_blocked", True)):
            max_age = int(policy.get("max_blocked_age_days", 30))
            for goal in goals:
                if str(goal.get("status", "")).upper() != "BLOCKED":
                    continue
                ages = [
                    self._age_days(str(goal.get("updated_at", ""))),
                    self._age_days(str(goal.get("created_at", ""))),
                ]
                age = max((item for item in ages if item is not None), default=None)
                if age is not None and age > max_age:
                    actions.append(self._reject(
                        goal,
                        reason="STALE_BLOCKED",
                        related_goal_id="",
                    ))

        unique: dict[str, dict[str, Any]] = {}
        for action in actions:
            unique[str(action.get("goal_id", ""))] = action
        actions = list(unique.values())
        if actions:
            self.strategic_portfolio.rebalance(
                refresh_roadmap=False,
                reconcile_execution=False,
            )
        for action in actions:
            self.store.append_record("B63", action)
        return self._finish(
            "GOAL_GOVERNANCE_COMPLETED",
            success=True,
            phase="READY",
            actions=actions,
            scanned=len(goals),
            rejected=len(actions),
        )

    def status(self) -> dict[str, Any]:
        return self._response(
            "GOAL_GOVERNANCE_STATUS",
            success=True,
            actions=self.store.list_records("B63", limit=20),
            strategic_summary=self.strategic_development.store.summary(),
            portfolio_summary=self.strategic_portfolio.store.summary(),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "GOAL_GOVERNANCE_HISTORY",
            success=True,
            actions=self.store.list_records("B63", limit=limit),
            history=self.store.history(stage="B63", limit=limit),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy("B63", {
            **dict(updates),
            "auto_approve": False,
        })
        return self._response(
            "GOAL_GOVERNANCE_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def _reject(
        self,
        goal: dict[str, Any],
        *,
        reason: str,
        related_goal_id: str,
    ) -> dict[str, Any]:
        item = dict(goal)
        item["status"] = "REJECTED"
        item["metadata"] = {
            **dict(item.get("metadata", {}) or {}),
            "governed_by": "B63",
            "governance_reason": reason,
            "related_goal_id": related_goal_id,
        }
        saved = self.strategic_development.store.save_goal(item)
        return {
            "action_id": f"goal-action-{saved.get('goal_id', '')}-{reason.lower()}",
            "goal_id": str(saved.get("goal_id", "")),
            "status": "REJECTED",
            "reason": reason,
            "related_goal_id": related_goal_id,
            "subsystem": str(saved.get("subsystem", "")),
            "created_at": self._now(),
        }

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        actions: list[dict[str, Any]],
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B63")
        runtime = self.store.update_runtime("B63", {
            "enabled": bool(self.store.policy("B63").get("enabled", True)),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_cycle_at": self._now(),
            "last_status": status,
            "last_decision": "APPLY" if actions else "HOLD",
            "last_record_id": str(actions[-1].get("action_id", "")) if actions else "",
            "last_result": {
                "status": status,
                "success": success,
                "actions": len(actions),
            },
            "last_error": "",
        })
        response = self._response(
            status,
            success=success,
            runtime=runtime,
            actions=actions,
            **extra,
        )
        self.store.record_history("B63", {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": "APPLY" if actions else "HOLD",
            "reason": f"Działania zarządzania celami: {len(actions)}",
        })
        return response

    def _response(
        self,
        status: str,
        *,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "autonomy_governance_suite",
            "stage": "B63",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B63"))),
            "policy": dict(extra.pop("policy", self.store.policy("B63"))),
            "summary": self.store.summary("B63"),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    @staticmethod
    def _age_days(value: str) -> int | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0, (datetime.now(timezone.utc) - parsed).days)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
