from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .autonomous_learning_store import AutonomousLearningStore


class AutonomyPolicyLearner:
    """Derives conservative optimizer and director policy from outcomes."""

    def __init__(
        self,
        *,
        minimum_observations: int = 5,
    ) -> None:
        self.minimum_observations = min(
            100,
            max(1, int(minimum_observations)),
        )

    def propose(
        self,
        analysis: dict[str, Any],
        *,
        current_profile: dict[str, Any] | None = None,
        apply_requested: bool = False,
    ) -> dict[str, Any]:
        base = {
            **AutonomousLearningStore.default_profile(),
            **dict(current_profile or {}),
        }
        observations = self._integer(
            analysis.get("observations", 0)
        )
        success_rate = self._number(
            analysis.get("success_rate", 0.0)
        )
        rollback_rate = self._number(
            analysis.get("rollback_rate", 0.0)
        )
        retry_rate = self._number(
            analysis.get("retry_rate", 0.0)
        )
        calibration = dict(
            analysis.get("calibration", {})
            if isinstance(analysis.get("calibration"), dict)
            else {}
        )
        confidence = self._confidence(
            observations=observations,
            success_rate=success_rate,
        )

        weights = self._weights(
            base.get("optimizer_weights", {}),
            success_rate=success_rate,
            rollback_rate=rollback_rate,
            risk_underestimation=self._number(
                calibration.get("risk_underestimation", 0.0)
            ),
            roi_overestimation=self._number(
                calibration.get("roi_overestimation", 0.0)
            ),
        )
        constraints = self._constraints(
            base.get("optimizer_constraints", {}),
            observations=observations,
            success_rate=success_rate,
            rollback_rate=rollback_rate,
            risk_underestimation=self._number(
                calibration.get("risk_underestimation", 0.0)
            ),
        )
        director_policy = self._director_policy(
            base.get("director_policy", {}),
            success_rate=success_rate,
            retry_rate=retry_rate,
            rollback_rate=rollback_rate,
        )
        enough_data = observations >= self.minimum_observations
        applied = bool(apply_requested and enough_data)
        recommendations = list(
            analysis.get("recommendations", [])
            if isinstance(analysis.get("recommendations"), list)
            else []
        )

        if apply_requested and not enough_data:
            recommendations.insert(
                0,
                (
                    "Profil nie został aktywowany: wymagane minimum "
                    f"{self.minimum_observations} obserwacji."
                ),
            )

        profile = {
            "version": 1,
            "active": applied,
            "learned_at": datetime.now(timezone.utc).isoformat(),
            "observations": observations,
            "confidence": confidence,
            "optimizer_weights": weights,
            "optimizer_constraints": constraints,
            "director_policy": director_policy,
            "calibration": calibration,
            "recommendations": recommendations[:30],
            "source_training_run_id": "",
            "safety": {
                "auto_approve": False,
                "auto_rollback": True,
                "final_validation": True,
                "code_writes": False,
            },
        }
        return {
            "success": True,
            "status": (
                "AUTONOMOUS_LEARNING_PROFILE_APPLIED"
                if applied
                else "AUTONOMOUS_LEARNING_PROFILE_PROPOSED"
                if enough_data
                else "AUTONOMOUS_LEARNING_INSUFFICIENT_DATA"
            ),
            "applied": applied,
            "enough_data": enough_data,
            "minimum_observations": self.minimum_observations,
            "profile": profile,
        }

    def _weights(
        self,
        current: Any,
        *,
        success_rate: float,
        rollback_rate: float,
        risk_underestimation: float,
        roi_overestimation: float,
    ) -> dict[str, float]:
        defaults = dict(
            AutonomousLearningStore.default_profile()[
                "optimizer_weights"
            ]
        )
        source = dict(current) if isinstance(current, dict) else {}
        weights = {
            name: max(
                0.01,
                self._number(source.get(name, value)),
            )
            for name, value in defaults.items()
        }

        if success_rate < 0.75:
            weights["risk"] += 0.08
            weights["history"] += 0.08
            weights["roi"] -= 0.05
            weights["confidence"] += 0.02

        if rollback_rate > 0.15:
            weights["risk"] += 0.07
            weights["history"] += 0.04
            weights["time"] -= 0.02

        if risk_underestimation > 1.5:
            weights["risk"] += min(
                0.10,
                risk_underestimation / 100.0,
            )

        if roi_overestimation > 1.5:
            weights["roi"] -= min(
                0.08,
                roi_overestimation / 100.0,
            )
            weights["history"] += min(
                0.08,
                roi_overestimation / 100.0,
            )

        if success_rate >= 0.90 and rollback_rate == 0.0:
            weights["roi"] += 0.04
            weights["confidence"] += 0.03
            weights["risk"] -= 0.03

        weights = {
            name: max(0.01, value)
            for name, value in weights.items()
        }
        total = sum(weights.values())
        return {
            name: round(value / total, 6)
            for name, value in weights.items()
        }

    def _constraints(
        self,
        current: Any,
        *,
        observations: int,
        success_rate: float,
        rollback_rate: float,
        risk_underestimation: float,
    ) -> dict[str, Any]:
        defaults = dict(
            AutonomousLearningStore.default_profile()[
                "optimizer_constraints"
            ]
        )
        source = dict(current) if isinstance(current, dict) else {}
        min_score = self._bounded(
            source.get("min_score", defaults["min_score"]),
            0.0,
            100.0,
        )
        max_risk = self._bounded(
            source.get("max_risk", defaults["max_risk"]),
            0.0,
            10.0,
        )
        max_campaigns = int(
            self._bounded(
                source.get("max_campaigns", defaults["max_campaigns"]),
                1,
                30,
            )
        )

        if observations >= self.minimum_observations:
            if success_rate < 0.60:
                min_score = max(min_score, 65.0)
                max_risk = min(max_risk, 5.0)
                max_campaigns = min(max_campaigns, 3)
            elif success_rate < 0.80:
                min_score = max(min_score, 50.0)
                max_risk = min(max_risk, 6.5)
                max_campaigns = min(max_campaigns, 8)
            elif success_rate >= 0.90 and rollback_rate < 0.05:
                min_score = max(min_score, 35.0)
                max_risk = min(max_risk, 8.0)
                max_campaigns = min(max_campaigns, 15)

        if rollback_rate > 0.15:
            max_risk = min(max_risk, 6.0)
        if risk_underestimation > 2.0:
            max_risk = min(max_risk, 5.5)

        return {
            "min_score": round(min_score, 3),
            "max_risk": round(max_risk, 3),
            "max_campaigns": max_campaigns,
            "require_positive_roi": bool(
                source.get(
                    "require_positive_roi",
                    defaults["require_positive_roi"],
                )
            ),
        }

    def _director_policy(
        self,
        current: Any,
        *,
        success_rate: float,
        retry_rate: float,
        rollback_rate: float,
    ) -> dict[str, Any]:
        defaults = dict(
            AutonomousLearningStore.default_profile()[
                "director_policy"
            ]
        )
        source = dict(current) if isinstance(current, dict) else {}
        retries = int(
            self._bounded(
                source.get(
                    "max_retries_per_campaign",
                    defaults["max_retries_per_campaign"],
                ),
                0,
                5,
            )
        )
        failures = int(
            self._bounded(
                source.get(
                    "max_failures",
                    defaults["max_failures"],
                ),
                1,
                30,
            )
        )

        if retry_rate > 0.30:
            retries = min(retries, 1)
        if success_rate < 0.70:
            failures = min(failures, 2)
        if rollback_rate > 0.20:
            failures = 1

        return {
            "max_retries_per_campaign": retries,
            "max_failures": failures,
            "rollback_on_stop": True,
        }

    @staticmethod
    def _confidence(
        *,
        observations: int,
        success_rate: float,
    ) -> float:
        sample_confidence = min(1.0, observations / 30.0)
        stability = 1.0 - abs(0.5 - success_rate) * 0.5
        return round(
            max(0.0, min(1.0, sample_confidence * stability)),
            4,
        )

    @staticmethod
    def _bounded(
        value: Any,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = minimum
        return max(minimum, min(maximum, number))

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
