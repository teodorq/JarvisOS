from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .multi_campaign_models import ManagedCampaign, MultiCampaignPortfolio
from .multi_campaign_planner import MultiCampaignPlanner
from .multi_campaign_store import MultiCampaignStore
from .autonomous_learning_store import AutonomousLearningStore


class PortfolioOptimizer:
    """Ranks campaigns using ROI, risk, time, confidence and history."""

    DEFAULT_WEIGHTS = {
        "roi": 0.28,
        "risk": 0.22,
        "time": 0.12,
        "history": 0.18,
        "priority": 0.10,
        "confidence": 0.10,
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: MultiCampaignStore | Any | None = None,
        history_limit: int = 30,
        learning_store: AutonomousLearningStore | Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.store = store or MultiCampaignStore(self.project_root)
        self.history_limit = min(100, max(1, int(history_limit)))
        self.learning_store = learning_store or AutonomousLearningStore(
            self.project_root
        )

    def optimize(
        self,
        portfolio: MultiCampaignPortfolio,
        *,
        constraints: dict[str, Any] | None = None,
        apply: bool = False,
    ) -> dict[str, Any]:
        merged_constraints, learning = self._merge_learning_constraints(
            constraints
        )
        policy = self._constraints(merged_constraints)
        history = self._history_index(exclude_portfolio_id=portfolio.portfolio_id)
        scores: dict[str, dict[str, Any]] = {}

        for item in portfolio.campaigns:
            scores[item.campaign_id] = self._score_campaign(
                item,
                history=history,
                weights=policy["weights"],
            )

        order = self._optimized_order(portfolio.campaigns, scores)
        selected, deferred = self._select_ready(
            portfolio,
            order=order,
            scores=scores,
            policy=policy,
        )
        selected_metrics = [scores[campaign_id] for campaign_id in selected]
        summary = {
            "portfolio_id": portfolio.portfolio_id,
            "campaign_scores": scores,
            "optimized_order": order,
            "selected_campaign_ids": selected,
            "deferred_campaigns": deferred,
            "constraints": {
                key: value
                for key, value in policy.items()
                if key != "weights"
            },
            "weights": dict(policy["weights"]),
            "selected_count": len(selected),
            "deferred_count": len(deferred),
            "estimated_minutes": round(
                sum(float(value["estimated_minutes"]) for value in selected_metrics),
                2,
            ),
            "average_risk": round(
                sum(float(value["estimated_risk"]) for value in selected_metrics)
                / max(1, len(selected_metrics)),
                2,
            ) if selected_metrics else 0.0,
            "average_score": round(
                sum(float(value["score"]) for value in selected_metrics)
                / max(1, len(selected_metrics)),
                2,
            ) if selected_metrics else 0.0,
            "expected_roi": round(
                sum(float(value["estimated_roi"]) for value in selected_metrics),
                2,
            ),
            "history_records": sum(
                int(value["history_observations"])
                for value in scores.values()
            ),
            "learning_profile": learning,
            "applied": bool(apply),
        }

        if apply:
            self._apply(portfolio, scores=scores, order=order, summary=summary)

        return summary

    def _score_campaign(
        self,
        item: ManagedCampaign,
        *,
        history: dict[str, list[dict[str, Any]]],
        weights: dict[str, float],
    ) -> dict[str, Any]:
        metadata = dict(item.metadata or {})
        roi = self._metric(
            metadata.get("estimated_roi", metadata.get("roi", 5.0)),
            default=5.0,
            minimum=0.0,
            maximum=10.0,
        )
        risk = self._metric(
            metadata.get("estimated_risk", metadata.get("risk", 5.0)),
            default=5.0,
            minimum=0.0,
            maximum=10.0,
        )
        minutes = self._metric(
            metadata.get(
                "estimated_minutes",
                metadata.get("time_minutes", max(10, len(item.stages) * 20)),
            ),
            default=max(10, len(item.stages) * 20),
            minimum=1.0,
            maximum=1440.0,
        )
        confidence = self._metric(
            metadata.get("confidence", 0.5),
            default=0.5,
            minimum=0.0,
            maximum=1.0,
        )
        base_priority = self._metric(
            metadata.get("base_priority_score", item.priority_score),
            default=float(item.priority_score),
            minimum=0.0,
            maximum=100.0,
        )
        records = self._matching_history(item, history)
        history_score, successes, failures, rollbacks = self._history_score(records)

        components = {
            "roi": roi * 10.0,
            "risk": (10.0 - risk) * 10.0,
            "time": max(0.0, 100.0 - min(minutes, 240.0) / 240.0 * 100.0),
            "history": history_score,
            "priority": base_priority,
            "confidence": confidence * 100.0,
        }
        score = round(
            max(
                0.0,
                min(
                    100.0,
                    sum(components[name] * weights[name] for name in weights),
                ),
            ),
            2,
        )
        reasons = [
            f"ROI {roi:.2f}/10",
            f"ryzyko {risk:.2f}/10",
            f"czas {minutes:.0f} min",
            f"historia {history_score:.1f}/100",
        ]
        if rollbacks:
            reasons.append(f"rollbacki historyczne: {rollbacks}")
        if failures:
            reasons.append(f"nieudane wykonania: {failures}")
        if successes:
            reasons.append(f"sukcesy historyczne: {successes}")

        return {
            "campaign_id": item.campaign_id,
            "score": score,
            "estimated_roi": round(roi, 2),
            "estimated_risk": round(risk, 2),
            "estimated_minutes": round(minutes, 2),
            "confidence": round(confidence, 3),
            "base_priority_score": round(base_priority, 2),
            "history_score": round(history_score, 2),
            "history_observations": len(records),
            "history_successes": successes,
            "history_failures": failures,
            "history_rollbacks": rollbacks,
            "components": {key: round(value, 2) for key, value in components.items()},
            "reasons": reasons,
        }

    def _select_ready(
        self,
        portfolio: MultiCampaignPortfolio,
        *,
        order: list[str],
        scores: dict[str, dict[str, Any]],
        policy: dict[str, Any],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        completed = set(portfolio.completed_campaign_ids)
        by_id = {item.campaign_id: item for item in portfolio.campaigns}
        selected: list[str] = []
        deferred: list[dict[str, Any]] = []
        spent_minutes = 0.0

        for campaign_id in order:
            item = by_id[campaign_id]
            if item.status not in {"PENDING", "PAUSED"}:
                continue
            missing_dependencies = [
                dependency
                for dependency in item.depends_on
                if dependency not in completed
            ]
            if missing_dependencies:
                deferred.append(
                    {
                        "campaign_id": campaign_id,
                        "reason": "DEPENDENCY_PENDING",
                        "dependencies": missing_dependencies,
                    }
                )
                continue

            metric = scores[campaign_id]
            reason = ""
            if metric["score"] < policy["min_score"]:
                reason = "SCORE_BELOW_MINIMUM"
            elif metric["estimated_risk"] > policy["max_risk"]:
                reason = "RISK_ABOVE_LIMIT"
            elif (
                policy["require_positive_roi"]
                and metric["estimated_roi"] <= 0
            ):
                reason = "NON_POSITIVE_ROI"
            elif len(selected) >= policy["max_campaigns"]:
                reason = "CAMPAIGN_LIMIT"
            elif (
                policy["max_total_minutes"] is not None
                and spent_minutes + metric["estimated_minutes"]
                > policy["max_total_minutes"]
            ):
                reason = "TIME_BUDGET_EXCEEDED"

            if reason:
                deferred.append(
                    {
                        "campaign_id": campaign_id,
                        "reason": reason,
                        "score": metric["score"],
                    }
                )
                continue

            selected.append(campaign_id)
            spent_minutes += float(metric["estimated_minutes"])

        return selected, deferred

    def _apply(
        self,
        portfolio: MultiCampaignPortfolio,
        *,
        scores: dict[str, dict[str, Any]],
        order: list[str],
        summary: dict[str, Any],
    ) -> None:
        for item in portfolio.campaigns:
            metric = scores[item.campaign_id]
            optimization = dict(metric)
            item.metadata.setdefault("base_priority_score", item.priority_score)
            item.metadata["optimization"] = optimization
            if item.status in {"PENDING", "PAUSED", "BLOCKED"}:
                item.priority_score = int(round(metric["score"]))
                item.priority = self._priority_name(item.priority_score)
        portfolio.execution_order = list(order)
        portfolio.metadata["optimization"] = {
            key: value
            for key, value in summary.items()
            if key != "campaign_scores"
        }
        portfolio.metadata["optimization"]["campaign_scores"] = {
            campaign_id: {
                "score": value["score"],
                "estimated_roi": value["estimated_roi"],
                "estimated_risk": value["estimated_risk"],
                "estimated_minutes": value["estimated_minutes"],
                "history_score": value["history_score"],
            }
            for campaign_id, value in scores.items()
        }
        portfolio.touch()

    def _optimized_order(
        self,
        campaigns: list[ManagedCampaign],
        scores: dict[str, dict[str, Any]],
    ) -> list[str]:
        original = {item.campaign_id: index for index, item in enumerate(campaigns)}
        dependencies = {
            item.campaign_id: set(item.depends_on)
            for item in campaigns
        }
        result: list[str] = []

        while dependencies:
            ready = [campaign_id for campaign_id, values in dependencies.items() if not values]
            ready.sort(
                key=lambda campaign_id: (
                    -float(scores[campaign_id]["score"]),
                    original[campaign_id],
                )
            )
            if not ready:
                raise ValueError("Wykryto cykl zależności podczas optymalizacji.")
            for campaign_id in ready:
                result.append(campaign_id)
                dependencies.pop(campaign_id)
            ready_set = set(ready)
            for values in dependencies.values():
                values.difference_update(ready_set)
        return result

    def _history_index(
        self,
        *,
        exclude_portfolio_id: str,
    ) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}
        try:
            portfolios = self.store.list_recent(limit=self.history_limit)
        except Exception:
            return index

        for portfolio in portfolios:
            if not isinstance(portfolio, dict):
                continue
            if str(portfolio.get("portfolio_id", "")) == exclude_portfolio_id:
                continue
            campaigns = portfolio.get("campaigns", [])
            if not isinstance(campaigns, list):
                continue
            for item in campaigns:
                if not isinstance(item, dict):
                    continue
                record = dict(item)
                for key in self._history_keys_from_dict(record):
                    index.setdefault(key, []).append(record)
        return index

    def _matching_history(
        self,
        item: ManagedCampaign,
        history: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[int] = set()
        for key in self._history_keys(item):
            for record in history.get(key, []):
                marker = id(record)
                if marker in seen:
                    continue
                seen.add(marker)
                result.append(record)
        return result

    @staticmethod
    def _history_score(
        records: Iterable[dict[str, Any]],
    ) -> tuple[float, int, int, int]:
        values = list(records)
        if not values:
            return 50.0, 0, 0, 0
        successes = 0
        failures = 0
        rollbacks = 0
        for record in values:
            status = str(record.get("status", "")).upper()
            result_status = str(
                dict(record.get("result", {}) or {}).get("status", "")
            ).upper()
            combined = f"{status} {result_status}"
            if "COMPLETED" in combined and "ROLLBACK" not in combined:
                successes += 1
            if any(word in combined for word in ("FAILED", "BLOCKED", "CANCELLED")):
                failures += 1
            if "ROLLBACK" in combined or status == "ROLLED_BACK":
                rollbacks += 1
        total = max(1, len(values))
        score = (
            successes / total * 100.0
            - failures / total * 30.0
            - rollbacks / total * 35.0
            + min(10.0, len(values) * 2.0)
        )
        return max(0.0, min(100.0, score)), successes, failures, rollbacks

    @classmethod
    def _history_keys(cls, item: ManagedCampaign) -> tuple[str, str]:
        return (
            f"id:{item.campaign_id.casefold()}",
            cls._signature(item.objective, item.targets),
        )

    @classmethod
    def _history_keys_from_dict(cls, item: dict[str, Any]) -> tuple[str, str]:
        return (
            f"id:{str(item.get('campaign_id', '')).casefold()}",
            cls._signature(
                str(item.get("objective", "")),
                [str(value) for value in item.get("targets", [])],
            ),
        )

    @staticmethod
    def _signature(objective: str, targets: Iterable[str]) -> str:
        normalized_objective = " ".join(str(objective).casefold().split())
        normalized_targets = "|".join(sorted(str(value).replace("\\", "/").casefold() for value in targets))
        return f"signature:{normalized_objective}|{normalized_targets}"

    def _merge_learning_constraints(
        self,
        value: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        source = dict(value or {})
        if source.pop("disable_learning_profile", False):
            return source, {
                "active": False,
                "reason": "DISABLED_BY_REQUEST",
            }

        try:
            profile = self.learning_store.get_profile()
        except Exception:
            return source, {
                "active": False,
                "reason": "PROFILE_UNAVAILABLE",
            }

        if (
            not bool(profile.get("active", False))
            or not self._learning_profile_is_approved(profile)
        ):
            return source, {
                "active": False,
                "confidence": float(
                    profile.get("confidence", 0.0) or 0.0
                ),
                "observations": int(
                    profile.get("observations", 0) or 0
                ),
                "reason": "PROFILE_NOT_SAFELY_DEPLOYED",
            }

        learned_constraints = dict(
            profile.get("optimizer_constraints", {})
            if isinstance(profile.get("optimizer_constraints"), dict)
            else {}
        )
        learned_weights = dict(
            profile.get("optimizer_weights", {})
            if isinstance(profile.get("optimizer_weights"), dict)
            else {}
        )
        merged = {
            **learned_constraints,
            **source,
        }
        if "weights" not in source and learned_weights:
            merged["weights"] = learned_weights

        return merged, {
            "active": True,
            "confidence": float(
                profile.get("confidence", 0.0) or 0.0
            ),
            "observations": int(
                profile.get("observations", 0) or 0
            ),
            "source_training_run_id": str(
                profile.get("source_training_run_id", "")
            ),
        }

    @staticmethod
    def _learning_profile_is_approved(
        profile: dict[str, Any],
    ) -> bool:
        version_id = str(
            profile.get("profile_version_id", "")
        ).strip()
        if not version_id:
            return True
        deployment = dict(
            profile.get("deployment", {})
            if isinstance(profile.get("deployment"), dict)
            else {}
        )
        if deployment.get("approved") is not True:
            return False
        decision = dict(
            deployment.get("decision", {})
            if isinstance(deployment.get("decision"), dict)
            else {}
        )
        minimum = float(
            decision.get("minimum_confidence", 0.0) or 0.0
        )
        confidence = float(
            profile.get("confidence", 0.0) or 0.0
        )
        return confidence >= minimum

    @classmethod
    def _constraints(cls, value: dict[str, Any] | None) -> dict[str, Any]:
        source = dict(value or {})
        weights = dict(cls.DEFAULT_WEIGHTS)
        custom_weights = source.get("weights", {})
        if isinstance(custom_weights, dict):
            for name in weights:
                if name in custom_weights:
                    weights[name] = max(0.0, float(custom_weights[name]))
        total = sum(weights.values())
        if total <= 0:
            weights = dict(cls.DEFAULT_WEIGHTS)
            total = sum(weights.values())
        weights = {name: value / total for name, value in weights.items()}

        max_minutes = source.get("max_total_minutes")
        if max_minutes is not None:
            max_minutes = cls._metric(
                max_minutes,
                default=1.0,
                minimum=1.0,
                maximum=100000.0,
            )
        return {
            "min_score": cls._metric(
                source.get("min_score", 0),
                default=0.0,
                minimum=0.0,
                maximum=100.0,
            ),
            "max_risk": cls._metric(
                source.get("max_risk", 10),
                default=10.0,
                minimum=0.0,
                maximum=10.0,
            ),
            "max_total_minutes": max_minutes,
            "max_campaigns": int(
                cls._metric(
                    source.get("max_campaigns", 30),
                    default=30,
                    minimum=1,
                    maximum=30,
                )
            ),
            "require_positive_roi": bool(source.get("require_positive_roi", False)),
            "weights": weights,
        }

    @staticmethod
    def _metric(
        value: Any,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = float(default)
        return max(minimum, min(maximum, number))

    @staticmethod
    def _priority_name(score: int) -> str:
        if score >= 90:
            return "CRITICAL"
        if score >= 65:
            return "HIGH"
        if score >= 35:
            return "NORMAL"
        return "LOW"
