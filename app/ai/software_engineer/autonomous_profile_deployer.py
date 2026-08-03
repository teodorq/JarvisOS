from __future__ import annotations

from typing import Any


class AutonomousProfileDeployer:
    """Promotes learned profiles only after conservative safety checks."""

    def __init__(
        self,
        *,
        minimum_observations: int = 5,
        minimum_confidence: float = 0.10,
        maximum_confidence_drop: float = 0.15,
    ) -> None:
        self.minimum_observations = min(
            1000,
            max(1, int(minimum_observations)),
        )
        self.minimum_confidence = self._bounded(
            minimum_confidence,
            0.0,
            1.0,
        )
        self.maximum_confidence_drop = self._bounded(
            maximum_confidence_drop,
            0.0,
            1.0,
        )

    def evaluate(
        self,
        candidate: dict[str, Any],
        *,
        current_profile: dict[str, Any] | None = None,
        minimum_confidence: float | None = None,
    ) -> dict[str, Any]:
        profile = dict(candidate or {})
        current = dict(current_profile or {})
        observations = self._integer(profile.get("observations", 0))
        confidence = self._bounded(
            profile.get("confidence", 0.0),
            0.0,
            1.0,
        )
        confidence_floor = self._bounded(
            self.minimum_confidence
            if minimum_confidence is None
            else minimum_confidence,
            0.0,
            1.0,
        )
        reasons: list[str] = []
        hard_errors = self._safety_errors(profile)

        if observations < self.minimum_observations:
            reasons.append(
                "Za mało obserwacji do aktywacji profilu."
            )
        if confidence < confidence_floor:
            reasons.append(
                "Pewność profilu jest niższa od progu wdrożenia."
            )

        if bool(current.get("active", False)):
            current_confidence = self._bounded(
                current.get("confidence", 0.0),
                0.0,
                1.0,
            )
            if (
                current_confidence - confidence
                > self.maximum_confidence_drop
            ):
                reasons.append(
                    "Nowy profil ma zbyt duży spadek pewności."
                )

        if hard_errors:
            return {
                "success": False,
                "status": "AUTONOMOUS_PROFILE_REJECTED",
                "eligible": False,
                "hard_rejection": True,
                "observations": observations,
                "confidence": confidence,
                "minimum_confidence": confidence_floor,
                "reasons": hard_errors + reasons,
                "errors": hard_errors,
            }

        eligible = not reasons
        return {
            "success": True,
            "status": (
                "AUTONOMOUS_PROFILE_APPROVED"
                if eligible
                else "AUTONOMOUS_PROFILE_STAGED"
            ),
            "eligible": eligible,
            "hard_rejection": False,
            "observations": observations,
            "confidence": confidence,
            "minimum_confidence": confidence_floor,
            "reasons": reasons,
            "errors": [],
        }

    def deploy(
        self,
        store: Any,
        version_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        version = store.get_profile_version(version_id)
        if version is None:
            return {
                "success": False,
                "status": "AUTONOMOUS_PROFILE_VERSION_NOT_FOUND",
                "version_id": str(version_id),
                "errors": ["Nie znaleziono wersji profilu."],
            }

        state = store.get_training_state()
        evaluation = self.evaluate(
            dict(version.get("profile", {}) or {}),
            current_profile=store.get_profile(),
            minimum_confidence=float(
                state.get("minimum_confidence", self.minimum_confidence)
                or self.minimum_confidence
            ),
        )
        eligible = bool(evaluation.get("eligible", False))
        if force and not bool(evaluation.get("hard_rejection", False)):
            eligible = True

        if not eligible:
            status = (
                "REJECTED"
                if evaluation.get("hard_rejection")
                else "STAGED"
            )
            stored = store.update_profile_version(
                version_id,
                {
                    "deployment_status": status,
                    "deployment_decision": dict(evaluation),
                },
            )
            return {
                "success": not bool(evaluation.get("hard_rejection")),
                "status": (
                    "AUTONOMOUS_PROFILE_REJECTED"
                    if status == "REJECTED"
                    else "AUTONOMOUS_PROFILE_STAGED"
                ),
                "applied": False,
                "version": stored,
                "evaluation": evaluation,
                "errors": list(evaluation.get("errors", [])),
            }

        activated = store.activate_profile_version(
            version_id,
            decision=evaluation,
        )
        return {
            "success": True,
            "status": "AUTONOMOUS_PROFILE_DEPLOYED",
            "applied": True,
            "version": activated,
            "profile": store.get_profile(),
            "evaluation": evaluation,
            "errors": [],
        }

    @classmethod
    def _safety_errors(
        cls,
        profile: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        safety = dict(
            profile.get("safety", {})
            if isinstance(profile.get("safety"), dict)
            else {}
        )
        constraints = dict(
            profile.get("optimizer_constraints", {})
            if isinstance(profile.get("optimizer_constraints"), dict)
            else {}
        )
        policy = dict(
            profile.get("director_policy", {})
            if isinstance(profile.get("director_policy"), dict)
            else {}
        )
        weights = dict(
            profile.get("optimizer_weights", {})
            if isinstance(profile.get("optimizer_weights"), dict)
            else {}
        )

        if safety.get("auto_approve") is True:
            errors.append("Profil nie może włączać auto_approve.")
        if safety.get("auto_rollback", True) is not True:
            errors.append("Profil musi zachować auto_rollback.")
        if safety.get("final_validation", True) is not True:
            errors.append("Profil musi zachować final_validation.")
        if safety.get("code_writes", False) is True:
            errors.append("Profil uczenia nie może sam pisać kodu.")

        max_risk = cls._bounded(
            constraints.get("max_risk", 10.0),
            0.0,
            100.0,
        )
        max_campaigns = cls._integer(
            constraints.get("max_campaigns", 30)
        )
        retries = cls._integer(
            policy.get("max_retries_per_campaign", 1)
        )
        failures = cls._integer(policy.get("max_failures", 3))

        if max_risk > 9.0:
            errors.append("Wyuczony max_risk przekracza bezpieczny limit 9.")
        if max_campaigns > 20:
            errors.append(
                "Wyuczony max_campaigns przekracza bezpieczny limit 20."
            )
        if retries > 2:
            errors.append("Wyuczony limit retry przekracza 2.")
        if failures > 3:
            errors.append("Wyuczony limit awarii przekracza 3.")

        numeric_weights = []
        for value in weights.values():
            try:
                numeric_weights.append(float(value))
            except (TypeError, ValueError):
                errors.append("Wagi optymalizatora muszą być liczbami.")
                break
        if numeric_weights:
            if any(value < 0.0 for value in numeric_weights):
                errors.append("Wagi optymalizatora nie mogą być ujemne.")
            total = sum(numeric_weights)
            if abs(total - 1.0) > 0.02:
                errors.append("Wagi optymalizatora muszą sumować się do 1.")

        return errors

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
    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
