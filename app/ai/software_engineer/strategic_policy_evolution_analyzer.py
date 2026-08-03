from __future__ import annotations

from collections import Counter
from typing import Any

from .strategic_policy_evolution_models import (
    SAFE_PORTFOLIO_POLICY_FIELDS,
    StrategicLearningMetrics,
)
from .strategic_portfolio_models import StrategicPortfolioPolicy


_TERMINAL_STATUSES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "DEFERRED_CONSTRAINTS",
    "REJECTED",
    "WAITING_APPROVAL",
}


class StrategicPolicyEvolutionAnalyzer:
    """Learns conservative B59 policy changes from B58 outcomes."""

    def analyze(
        self,
        executions: list[dict[str, Any]],
        portfolio_entries: list[dict[str, Any]],
        *,
        current_policy: dict[str, Any],
        evolution_policy: dict[str, Any],
    ) -> dict[str, Any]:
        window = max(10, int(evolution_policy.get("observation_window", 200)))
        records = [
            dict(item)
            for item in executions
            if isinstance(item, dict)
            and str(item.get("status", "")).upper() in _TERMINAL_STATUSES
        ][:window]
        metrics = self._metrics(records, portfolio_entries)
        minimum = max(1, int(evolution_policy.get("min_observations", 3)))
        confidence = min(1.0, metrics.observations / float(minimum + 5))
        if metrics.observations < minimum:
            return {
                "decision": "HOLD",
                "reason": (
                    f"Za mało zakończonych obserwacji: "
                    f"{metrics.observations}/{minimum}."
                ),
                "metrics": metrics.to_dict(),
                "changes": {},
                "proposed_policy": self._safe_policy(current_policy),
                "confidence": confidence,
            }

        proposed = self._safe_policy(current_policy)
        changes: dict[str, Any] = {}
        reasons: list[str] = []
        score_step = float(evolution_policy.get("max_score_step", 1.0))
        penalty_step = float(evolution_policy.get("max_penalty_step", 1.0))
        bonus_step = float(evolution_policy.get("max_bonus_step", 0.75))
        cooldown_ratio = float(
            evolution_policy.get("max_cooldown_ratio_step", 0.15)
        )

        if metrics.failure_rate >= 0.25:
            self._change(
                proposed, changes, "failure_penalty",
                float(proposed.get("failure_penalty", 8.0)) + penalty_step,
            )
            self._change(
                proposed, changes, "min_adaptive_score",
                float(proposed.get("min_adaptive_score", 5.0)) + score_step,
            )
            self._change(
                proposed, changes, "failure_cooldown_threshold",
                max(1, int(proposed.get("failure_cooldown_threshold", 2)) - 1),
            )
            self._change(
                proposed, changes, "cooldown_seconds",
                float(proposed.get("cooldown_seconds", 900.0))
                * (1.0 + cooldown_ratio),
            )
            reasons.append("Podwyższono ochronę po rzeczywistych błędach.")

        if metrics.deferred_rate >= 0.40 and metrics.failure_rate < 0.25:
            self._change(
                proposed, changes, "deferred_penalty",
                float(proposed.get("deferred_penalty", 1.5)) + penalty_step / 2,
            )
            self._change(
                proposed, changes, "exploration_bonus",
                float(proposed.get("exploration_bonus", 6.0)) + bonus_step,
            )
            self._change(
                proposed, changes, "deferred_cooldown_threshold",
                max(1, int(proposed.get("deferred_cooldown_threshold", 3)) - 1),
            )
            reasons.append(
                "Zwiększono eksplorację po powtarzających się ograniczeniach."
            )

        if metrics.success_rate >= 0.60 and metrics.failure_rate <= 0.15:
            self._change(
                proposed, changes, "completion_bonus",
                float(proposed.get("completion_bonus", 2.0)) + bonus_step,
            )
            self._change(
                proposed, changes, "min_adaptive_score",
                float(proposed.get("min_adaptive_score", 5.0)) - score_step / 2,
            )
            self._change(
                proposed, changes, "cooldown_seconds",
                float(proposed.get("cooldown_seconds", 900.0))
                * (1.0 - cooldown_ratio / 2),
            )
            reasons.append("Wzmocniono politykę, która daje dobre wyniki.")

        if metrics.subsystem_concentration >= 0.65 and metrics.observations >= 3:
            self._change(
                proposed, changes, "diversity_penalty",
                float(proposed.get("diversity_penalty", 8.0)) + penalty_step,
            )
            reasons.append("Zwiększono karę za koncentrację na jednym podsystemie.")

        bounded = StrategicPortfolioPolicy.from_dict(proposed).to_dict()
        changes = {
            key: bounded[key]
            for key in changes
            if key in SAFE_PORTFOLIO_POLICY_FIELDS
            and bounded.get(key) != self._safe_policy(current_policy).get(key)
        }
        decision = "PROPOSE" if changes else "HOLD"
        return {
            "decision": decision,
            "reason": " ".join(reasons) or "Brak bezpiecznej zmiany polityki.",
            "metrics": metrics.to_dict(),
            "changes": changes,
            "proposed_policy": bounded,
            "confidence": confidence,
        }

    def _metrics(
        self,
        records: list[dict[str, Any]],
        portfolio_entries: list[dict[str, Any]],
    ) -> StrategicLearningMetrics:
        statuses = [str(item.get("status", "")).upper() for item in records]
        total = len(statuses)
        goal_to_subsystem = {
            str(item.get("goal_id", "")): str(item.get("subsystem", ""))
            for item in portfolio_entries
            if isinstance(item, dict)
        }
        subsystems = [
            goal_to_subsystem.get(str(item.get("goal_id", "")), "")
            or str(item.get("target", "")).split("/")[0]
            for item in records
        ]
        subsystems = [item for item in subsystems if item]
        counts = Counter(subsystems)
        concentration = max(counts.values(), default=0) / max(1, len(subsystems))
        adaptive_scores = [
            float(item.get("adaptive_priority_score", 0.0) or 0.0)
            for item in portfolio_entries
            if isinstance(item, dict)
        ]
        dates = [
            str(item.get("observed_at") or item.get("updated_at") or "")
            for item in records
        ]
        return StrategicLearningMetrics(
            observations=total,
            completed=statuses.count("COMPLETED"),
            failed=statuses.count("FAILED") + statuses.count("REJECTED"),
            deferred=statuses.count("DEFERRED_CONSTRAINTS"),
            waiting_approval=statuses.count("WAITING_APPROVAL"),
            cancelled=statuses.count("CANCELLED"),
            success_rate=statuses.count("COMPLETED") / max(1, total),
            failure_rate=(
                statuses.count("FAILED") + statuses.count("REJECTED")
            ) / max(1, total),
            deferred_rate=statuses.count("DEFERRED_CONSTRAINTS") / max(1, total),
            approval_rate=statuses.count("WAITING_APPROVAL") / max(1, total),
            subsystem_count=len(counts),
            subsystem_concentration=round(concentration, 4),
            portfolio_ready=sum(
                str(item.get("status", "")).upper() == "READY"
                for item in portfolio_entries
                if isinstance(item, dict)
            ),
            portfolio_cooldown=sum(
                str(item.get("status", "")).upper() == "COOLDOWN"
                for item in portfolio_entries
                if isinstance(item, dict)
            ),
            average_adaptive_score=(
                round(sum(adaptive_scores) / len(adaptive_scores), 4)
                if adaptive_scores else 0.0
            ),
            evidence_from=min(dates, default=""),
            evidence_to=max(dates, default=""),
        )

    @staticmethod
    def _change(
        proposed: dict[str, Any],
        changes: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        proposed[key] = value
        changes[key] = value

    @staticmethod
    def _safe_policy(value: dict[str, Any]) -> dict[str, Any]:
        policy = StrategicPortfolioPolicy.from_dict(value).to_dict()
        policy["max_active_goals"] = 1
        policy["auto_approve"] = False
        return policy
