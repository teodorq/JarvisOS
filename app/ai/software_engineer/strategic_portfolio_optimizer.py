from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .strategic_portfolio_models import StrategicPortfolioEntry


_ACTIVE_EXECUTION_STATES = {
    "DISPATCHED",
    "QUEUED",
    "SCHEDULED",
    "WAITING_RESOURCES",
    "WAITING_APPROVAL",
    "RECOVERING",
    "RUNNING",
    "PAUSED",
}

_FAILED_EXECUTION_STATES = {
    "FAILED",
    "CANCELLED",
    "REJECTED",
}


class StrategicPortfolioOptimizer:
    """B59 outcome-aware goal ranking without direct code execution."""

    def build_entries(
        self,
        goals: list[dict[str, Any]],
        executions: list[dict[str, Any]],
        *,
        existing_by_goal_id: dict[str, dict[str, Any]] | None,
        policy: dict[str, Any],
        last_selected_subsystem: str = "",
        now: datetime | None = None,
    ) -> list[StrategicPortfolioEntry]:
        current_time = (now or datetime.now(timezone.utc)).astimezone(
            timezone.utc
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for execution in executions:
            if not isinstance(execution, dict):
                continue
            goal_id = str(execution.get("goal_id", "")).strip()
            if goal_id:
                grouped[goal_id].append(dict(execution))
        for values in grouped.values():
            values.sort(
                key=lambda item: str(
                    item.get("observed_at")
                    or item.get("updated_at")
                    or item.get("created_at")
                    or ""
                ),
                reverse=True,
            )

        existing = dict(existing_by_goal_id or {})
        entries: list[StrategicPortfolioEntry] = []
        for goal in goals:
            if not isinstance(goal, dict):
                continue
            goal_id = str(goal.get("goal_id", "")).strip()
            if not goal_id:
                continue
            previous = existing.get(goal_id, {})
            outcomes = grouped.get(goal_id, [])
            stats = self._stats(outcomes)
            cooldown_until, trigger_id = self._cooldown(
                previous,
                stats,
                policy,
                current_time,
            )
            status = self._status(
                goal,
                stats,
                cooldown_until,
                current_time,
            )
            subsystem = str(goal.get("subsystem", "")).strip()
            adaptive_score = self._score(
                goal,
                stats,
                policy,
                repeated_subsystem=(
                    bool(last_selected_subsystem)
                    and subsystem == last_selected_subsystem
                    and status == "READY"
                ),
            )
            metadata = dict(previous.get("metadata", {}) or {})
            metadata.update({
                "source": "B59StrategicPortfolio",
                "cooldown_trigger_execution_id": trigger_id,
                "goal_status": str(goal.get("status", "")),
            })
            entries.append(StrategicPortfolioEntry(
                goal_id=goal_id,
                subsystem=subsystem,
                issue_type=str(goal.get("issue_type", "")),
                title=str(goal.get("title", "")),
                status=status,
                base_priority_score=float(
                    goal.get("priority_score", 0.0) or 0.0
                ),
                adaptive_priority_score=adaptive_score,
                value_score=float(goal.get("value_score", 0.0) or 0.0),
                risk_score=float(goal.get("risk_score", 0.0) or 0.0),
                confidence=float(goal.get("confidence", 0.0) or 0.0),
                pending_count=max(
                    0,
                    int(goal.get("pending_count", 0) or 0),
                ),
                executions_total=stats["total"],
                active_count=stats["active"],
                completed_count=stats["completed"],
                failed_count=stats["failed"],
                deferred_count=stats["deferred"],
                waiting_approval_count=stats["waiting_approval"],
                consecutive_failures=stats["consecutive_failures"],
                consecutive_deferred=stats["consecutive_deferred"],
                success_rate=stats["success_rate"],
                last_execution_id=stats["last_execution_id"],
                last_outcome=stats["last_outcome"],
                cooldown_until=cooldown_until,
                created_at=str(previous.get("created_at", ""))
                or current_time.isoformat(),
                updated_at=current_time.isoformat(),
                metadata=metadata,
            ))
        entries.sort(
            key=lambda item: (
                item.status == "READY",
                item.adaptive_priority_score,
                item.confidence,
                -item.risk_score,
                item.pending_count,
                item.goal_id,
            ),
            reverse=True,
        )
        return entries

    def select_candidates(
        self,
        entries: list[dict[str, Any]],
        *,
        min_adaptive_score: float,
    ) -> list[dict[str, Any]]:
        candidates = [
            dict(item)
            for item in entries
            if isinstance(item, dict)
            and str(item.get("status", "")).upper() == "READY"
            and int(item.get("pending_count", 0) or 0) > 0
            and float(item.get("adaptive_priority_score", 0.0) or 0.0)
            >= float(min_adaptive_score)
        ]
        candidates.sort(
            key=lambda item: (
                float(item.get("adaptive_priority_score", 0.0) or 0.0),
                float(item.get("confidence", 0.0) or 0.0),
                -float(item.get("risk_score", 0.0) or 0.0),
                int(item.get("pending_count", 0) or 0),
            ),
            reverse=True,
        )
        return candidates

    @staticmethod
    def _stats(executions: list[dict[str, Any]]) -> dict[str, Any]:
        states = [
            str(item.get("status", "")).upper()
            for item in executions
        ]
        completed = states.count("COMPLETED")
        deferred = states.count("DEFERRED_CONSTRAINTS")
        failed = sum(state in _FAILED_EXECUTION_STATES for state in states)
        active = sum(state in _ACTIVE_EXECUTION_STATES for state in states)
        waiting_approval = states.count("WAITING_APPROVAL")
        decisive = completed + failed
        return {
            "total": len(states),
            "active": active,
            "completed": completed,
            "failed": failed,
            "deferred": deferred,
            "waiting_approval": waiting_approval,
            "consecutive_failures": StrategicPortfolioOptimizer._streak(
                states,
                _FAILED_EXECUTION_STATES,
            ),
            "consecutive_deferred": StrategicPortfolioOptimizer._streak(
                states,
                {"DEFERRED_CONSTRAINTS"},
            ),
            "success_rate": round(
                completed / decisive if decisive else 0.0,
                4,
            ),
            "last_execution_id": str(
                executions[0].get("execution_id", "")
                if executions
                else ""
            ),
            "last_outcome": states[0] if states else "",
        }

    @staticmethod
    def _streak(states: list[str], allowed: set[str]) -> int:
        count = 0
        for state in states:
            if state not in allowed:
                break
            count += 1
        return count

    @staticmethod
    def _cooldown(
        previous: dict[str, Any],
        stats: dict[str, Any],
        policy: dict[str, Any],
        now: datetime,
    ) -> tuple[str, str]:
        previous_until = StrategicPortfolioOptimizer._parse_time(
            previous.get("cooldown_until", "")
        )
        previous_metadata = dict(previous.get("metadata", {}) or {})
        previous_trigger = str(
            previous_metadata.get("cooldown_trigger_execution_id", "")
        )
        last_execution_id = str(stats.get("last_execution_id", ""))
        failure_limit = int(policy.get("failure_cooldown_threshold", 2))
        deferred_limit = int(policy.get("deferred_cooldown_threshold", 3))
        threshold_reached = bool(
            int(stats.get("consecutive_failures", 0)) >= failure_limit
            or int(stats.get("consecutive_deferred", 0)) >= deferred_limit
        )
        if (
            threshold_reached
            and last_execution_id
            and last_execution_id != previous_trigger
        ):
            until = now + timedelta(
                seconds=float(policy.get("cooldown_seconds", 900.0))
            )
            return until.isoformat(), last_execution_id
        if previous_until is not None and previous_until > now:
            return previous_until.isoformat(), previous_trigger
        return "", previous_trigger if threshold_reached else ""

    @staticmethod
    def _status(
        goal: dict[str, Any],
        stats: dict[str, Any],
        cooldown_until: str,
        now: datetime,
    ) -> str:
        goal_status = str(goal.get("status", "PENDING")).upper()
        if goal_status in {"BLOCKED", "REJECTED"}:
            return "BLOCKED"
        if goal_status == "COMPLETED" or int(
            goal.get("pending_count", 0) or 0
        ) <= 0:
            return "COMPLETED"
        if int(stats.get("waiting_approval", 0)) > 0:
            return "WAITING_APPROVAL"
        if int(stats.get("active", 0)) > 0 or goal_status == "ACTIVE":
            return "ACTIVE"
        cooldown = StrategicPortfolioOptimizer._parse_time(cooldown_until)
        if cooldown is not None and cooldown > now:
            return "COOLDOWN"
        return "READY"

    @staticmethod
    def _score(
        goal: dict[str, Any],
        stats: dict[str, Any],
        policy: dict[str, Any],
        *,
        repeated_subsystem: bool,
    ) -> float:
        score = float(goal.get("priority_score", 0.0) or 0.0)
        if int(stats.get("total", 0)) == 0:
            score += float(policy.get("exploration_bonus", 6.0))
        score += min(5, int(stats.get("completed", 0))) * float(
            policy.get("completion_bonus", 2.0)
        )
        score -= min(5, int(stats.get("failed", 0))) * float(
            policy.get("failure_penalty", 8.0)
        )
        score -= min(8, int(stats.get("deferred", 0))) * float(
            policy.get("deferred_penalty", 1.5)
        )
        if repeated_subsystem:
            score -= float(policy.get("diversity_penalty", 8.0))
        return round(min(100.0, max(-100.0, score)), 2)

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
