from __future__ import annotations

import hashlib
from typing import Any

from .strategic_policy_evolution_models import SAFE_PORTFOLIO_POLICY_FIELDS
from .strategic_portfolio_models import StrategicPortfolioPolicy


class StrategicPolicyValidationAnalyzer:
    """Offline B61 replay of B59 ranking under champion/challenger policies."""

    def analyze(
        self,
        entries: list[dict[str, Any]],
        executions: list[dict[str, Any]],
        *,
        baseline_policy: dict[str, Any],
        candidate_policy: dict[str, Any],
        changes: dict[str, Any],
        validation_policy: dict[str, Any],
    ) -> dict[str, Any]:
        baseline = StrategicPortfolioPolicy.from_dict(baseline_policy).to_dict()
        candidate = StrategicPortfolioPolicy.from_dict(candidate_policy).to_dict()
        evidence = self._terminal_executions(executions)
        evidence_count = len(evidence)
        signature = self.evidence_signature(evidence)
        min_observations = int(validation_policy.get("min_observations", 3))
        allowed_changes = {
            key: value for key, value in dict(changes or {}).items()
            if key in SAFE_PORTFOLIO_POLICY_FIELDS
        }
        unsafe_fields = sorted(set(dict(changes or {})) - set(allowed_changes))
        changed_fields_ok = (
            len(allowed_changes)
            <= int(validation_policy.get("max_changed_fields", 6))
        )
        hard_safety = bool(
            not unsafe_fields
            and changed_fields_ok
            and candidate.get("max_active_goals") == 1
            and candidate.get("auto_approve") is False
        )
        if evidence_count < min_observations:
            return {
                "decision": "HOLD",
                "reason": (
                    f"Za mało dowodów B58: {evidence_count}/{min_observations}."
                ),
                "evidence_signature": signature,
                "evidence_count": evidence_count,
                "metrics": self._empty_metrics(evidence_count),
                "checks": {
                    "enough_evidence": False,
                    "hard_safety": hard_safety,
                    "unsafe_fields": unsafe_fields,
                    "changed_fields_ok": changed_fields_ok,
                },
            }

        baseline_rank = self._rank(entries, baseline)
        candidate_rank = self._rank(entries, candidate)
        top_k = max(1, int(validation_policy.get("top_k", 5)))
        baseline_top = baseline_rank[:top_k]
        candidate_top = candidate_rank[:top_k]
        baseline_ids = {str(item.get("goal_id", "")) for item in baseline_top}
        candidate_ids = {str(item.get("goal_id", "")) for item in candidate_top}
        union = baseline_ids | candidate_ids
        overlap = len(baseline_ids & candidate_ids) / len(union) if union else 1.0
        baseline_utility = self._portfolio_utility(baseline_top)
        candidate_utility = self._portfolio_utility(candidate_top)
        improvement = round(candidate_utility - baseline_utility, 4)
        baseline_failure = self._exposure(baseline_top, "failed_count")
        candidate_failure = self._exposure(candidate_top, "failed_count")
        baseline_deferred = self._exposure(baseline_top, "deferred_count")
        candidate_deferred = self._exposure(candidate_top, "deferred_count")
        failure_increase = round(candidate_failure - baseline_failure, 4)
        deferred_increase = round(candidate_deferred - baseline_deferred, 4)

        checks = {
            "enough_evidence": True,
            "hard_safety": hard_safety,
            "unsafe_fields": unsafe_fields,
            "changed_fields_ok": changed_fields_ok,
            "utility_non_regression": improvement >= float(
                validation_policy.get("min_utility_improvement", 0.0)
            ),
            "failure_exposure_safe": failure_increase <= float(
                validation_policy.get("max_failure_exposure_increase", 0.0)
            ),
            "deferred_exposure_safe": deferred_increase <= float(
                validation_policy.get("max_deferred_exposure_increase", 0.20)
            ),
            "ranking_stability": overlap >= float(
                validation_policy.get("min_top_k_overlap", 0.20)
            ),
        }
        passed = all(
            bool(checks[key])
            for key in (
                "hard_safety",
                "utility_non_regression",
                "failure_exposure_safe",
                "deferred_exposure_safe",
                "ranking_stability",
            )
        )
        metrics = {
            "observations": evidence_count,
            "baseline_utility": baseline_utility,
            "candidate_utility": candidate_utility,
            "utility_improvement": improvement,
            "baseline_failure_exposure": baseline_failure,
            "candidate_failure_exposure": candidate_failure,
            "failure_exposure_increase": failure_increase,
            "baseline_deferred_exposure": baseline_deferred,
            "candidate_deferred_exposure": candidate_deferred,
            "deferred_exposure_increase": deferred_increase,
            "top_k_overlap": round(overlap, 4),
            "baseline_top_goal_ids": sorted(baseline_ids),
            "candidate_top_goal_ids": sorted(candidate_ids),
        }
        failed_checks = [
            key for key, value in checks.items()
            if key not in {"unsafe_fields"} and value is False
        ]
        return {
            "decision": "PASS" if passed else "REJECT",
            "reason": (
                "Polityka challenger przeszła replay B61 bez regresji bezpieczeństwa."
                if passed else
                "Polityka challenger nie przeszła: " + ", ".join(failed_checks)
            ),
            "evidence_signature": signature,
            "evidence_count": evidence_count,
            "metrics": metrics,
            "checks": checks,
        }

    @staticmethod
    def evidence_signature(executions: list[dict[str, Any]]) -> str:
        values = [
            f"{item.get('execution_id', '')}:{item.get('status', '')}:"
            f"{item.get('observed_at') or item.get('updated_at') or ''}"
            for item in executions
            if isinstance(item, dict)
            and str(item.get("execution_id", "")).strip()
        ]
        if not values:
            return ""
        return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()

    @staticmethod
    def _terminal_executions(
        executions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        terminal = {
            "COMPLETED", "FAILED", "CANCELLED", "REJECTED",
            "DEFERRED_CONSTRAINTS", "WAITING_APPROVAL",
        }
        return [
            dict(item) for item in executions
            if isinstance(item, dict)
            and str(item.get("status", "")).upper() in terminal
        ]

    def _rank(
        self,
        entries: list[dict[str, Any]],
        policy: dict[str, Any],
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            if str(item.get("status", "READY")).upper() != "READY":
                continue
            if int(item.get("pending_count", 0) or 0) <= 0:
                continue
            score = self._score(item, policy)
            item["shadow_score"] = score
            if score >= float(policy.get("min_adaptive_score", 5.0)):
                ranked.append(item)
        ranked.sort(
            key=lambda item: (
                float(item.get("shadow_score", 0.0)),
                float(item.get("confidence", 0.0)),
                -float(item.get("risk_score", 0.0)),
                str(item.get("goal_id", "")),
            ),
            reverse=True,
        )
        return ranked

    @staticmethod
    def _score(entry: dict[str, Any], policy: dict[str, Any]) -> float:
        score = float(
            entry.get("base_priority_score", entry.get("adaptive_priority_score", 0.0))
            or 0.0
        )
        total = int(entry.get("executions_total", 0) or 0)
        if total == 0:
            score += float(policy.get("exploration_bonus", 6.0))
        score += min(5, int(entry.get("completed_count", 0) or 0)) * float(
            policy.get("completion_bonus", 2.0)
        )
        score -= min(5, int(entry.get("failed_count", 0) or 0)) * float(
            policy.get("failure_penalty", 8.0)
        )
        score -= min(8, int(entry.get("deferred_count", 0) or 0)) * float(
            policy.get("deferred_penalty", 1.5)
        )
        return round(min(100.0, max(-100.0, score)), 2)

    @staticmethod
    def _portfolio_utility(entries: list[dict[str, Any]]) -> float:
        if not entries:
            return 0.0
        values: list[float] = []
        for item in entries:
            completed = int(item.get("completed_count", 0) or 0)
            failed = int(item.get("failed_count", 0) or 0)
            deferred = int(item.get("deferred_count", 0) or 0)
            decisive = completed + failed
            success_rate = completed / decisive if decisive else 0.0
            value = (
                float(item.get("value_score", 0.0) or 0.0) * 0.20
                + float(item.get("confidence", 0.0) or 0.0) * 10.0
                + success_rate * 20.0
                - failed * 8.0
                - deferred * 1.5
                - float(item.get("risk_score", 0.0) or 0.0) * 0.05
            )
            values.append(value)
        return round(sum(values) / len(values), 4)

    @staticmethod
    def _exposure(entries: list[dict[str, Any]], field: str) -> float:
        total = sum(int(item.get("executions_total", 0) or 0) for item in entries)
        events = sum(int(item.get(field, 0) or 0) for item in entries)
        return round(events / total if total else 0.0, 4)

    @staticmethod
    def _empty_metrics(evidence_count: int) -> dict[str, Any]:
        return {
            "observations": evidence_count,
            "baseline_utility": 0.0,
            "candidate_utility": 0.0,
            "utility_improvement": 0.0,
            "failure_exposure_increase": 0.0,
            "deferred_exposure_increase": 0.0,
            "top_k_overlap": 1.0,
        }
