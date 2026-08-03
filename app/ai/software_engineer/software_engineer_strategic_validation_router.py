from __future__ import annotations

from typing import Any

from .strategic_policy_validation_service import (
    bootstrap_strategic_policy_validation,
)
from .software_engineer_autonomy_governance_router import (
    SoftwareEngineerAutonomyGovernanceRouter,
)


_AUTONOMY_GOVERNANCE_ROUTER = SoftwareEngineerAutonomyGovernanceRouter()


class SoftwareEngineerStrategicValidationRouter:
    """Polish/English GUI routing for B61 validation and promotion."""

    READ_PHRASES = (
        "status walidacji polityki strategicznej",
        "pokaż status walidacji polityki strategicznej",
        "pokaz status walidacji polityki strategicznej",
        "historia walidacji polityki strategicznej",
        "eksperymenty polityki strategicznej",
        "pokaż eksperymenty polityki strategicznej",
        "pokaz eksperymenty polityki strategicznej",
        "status bezpiecznej promocji polityki",
        "status b61",
        "strategic policy validation status",
        "strategic policy validation history",
        "strategic policy experiments",
    )

    MUTATING_PHRASES = (
        "uruchom walidację polityki strategicznej",
        "uruchom walidacje polityki strategicznej",
        "zatrzymaj walidację polityki strategicznej",
        "zatrzymaj walidacje polityki strategicznej",
        "wstrzymaj walidację polityki strategicznej",
        "wstrzymaj walidacje polityki strategicznej",
        "wznów walidację polityki strategicznej",
        "wznow walidacje polityki strategicznej",
        "przeprowadź cykl walidacji polityki strategicznej",
        "przeprowadz cykl walidacji polityki strategicznej",
        "zwaliduj proponowaną politykę strategiczną",
        "zwaliduj proponowana polityke strategiczna",
        "promuj zwalidowaną politykę strategiczną",
        "promuj zwalidowana polityke strategiczna",
        "odrzuć proponowaną politykę strategiczną",
        "odrzuc proponowana polityke strategiczna",
        "ustaw politykę walidacji strategicznej",
        "ustaw polityke walidacji strategicznej",
        "start strategic policy validation",
        "stop strategic policy validation",
        "pause strategic policy validation",
        "resume strategic policy validation",
        "run strategic policy validation cycle",
        "validate strategic policy proposal",
        "promote validated strategic policy",
        "reject strategic policy proposal",
    )

    @classmethod
    def can_handle(cls, command: str) -> bool:
        normalized = " ".join(str(command).casefold().split())
        return (
            _AUTONOMY_GOVERNANCE_ROUTER.can_handle(normalized)
            or any(
                phrase in normalized
                for phrase in cls.READ_PHRASES + cls.MUTATING_PHRASES
            )
        )

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        governance = _AUTONOMY_GOVERNANCE_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )
        if governance is not None:
            return governance
        operation = str(
            context.get(
                "strategic_validation_action",
                context.get("operation", ""),
            )
        ).strip().casefold()
        normalized = controller._normalize(command)
        if not (
            operation in {
                "strategic_validation",
                "strategic_validation_status",
                "strategic_validation_history",
                "strategic_validation_experiments",
                "strategic_validation_cycle",
                "strategic_validation_validate",
                "strategic_validation_promote",
                "strategic_validation_reject",
                "strategic_validation_start",
                "strategic_validation_stop",
                "strategic_validation_pause",
                "strategic_validation_resume",
                "strategic_validation_policy",
            }
            or self.can_handle(normalized)
        ):
            return None
        service = bootstrap_strategic_policy_validation(controller)
        action = self._action(operation, normalized)
        if action == "status":
            return service.status()
        if action == "history":
            return service.history(limit=int(context.get("limit", 20)))
        if action == "experiments":
            return service.experiments(limit=int(context.get("limit", 50)))
        if action == "cycle":
            return service.run_cycle()
        if action == "validate":
            return service.validate(str(context.get("revision_id", "")))
        if action == "promote":
            return service.promote(str(context.get("experiment_id", "")))
        if action == "reject":
            return service.reject(str(context.get("revision_id", "")))
        if action == "start":
            return service.start_background()
        if action == "stop":
            return service.stop_background()
        if action == "pause":
            return service.pause()
        if action == "resume":
            return service.resume()
        if action == "policy":
            return service.update_policy(
                dict(context.get("strategic_validation_policy", {}) or {})
            )
        return service.status()

    @staticmethod
    def _action(operation: str, normalized: str) -> str:
        explicit_checks = (
            ("cycle", (
                "przeprowadź cykl walidacji polityki strategicznej",
                "przeprowadz cykl walidacji polityki strategicznej",
                "run strategic policy validation cycle",
            )),
            ("validate", (
                "zwaliduj proponowaną politykę strategiczną",
                "zwaliduj proponowana polityke strategiczna",
                "validate strategic policy proposal",
            )),
            ("promote", (
                "promuj zwalidowaną politykę strategiczną",
                "promuj zwalidowana polityke strategiczna",
                "promote validated strategic policy",
            )),
            ("reject", (
                "odrzuć proponowaną politykę strategiczną",
                "odrzuc proponowana polityke strategiczna",
                "reject strategic policy proposal",
            )),
            ("stop", (
                "zatrzymaj walidację polityki strategicznej",
                "zatrzymaj walidacje polityki strategicznej",
                "stop strategic policy validation",
            )),
            ("pause", (
                "wstrzymaj walidację polityki strategicznej",
                "wstrzymaj walidacje polityki strategicznej",
                "pause strategic policy validation",
            )),
            ("resume", (
                "wznów walidację polityki strategicznej",
                "wznow walidacje polityki strategicznej",
                "resume strategic policy validation",
            )),
            ("policy", (
                "ustaw politykę walidacji strategicznej",
                "ustaw polityke walidacji strategicznej",
            )),
            ("start", (
                "uruchom walidację polityki strategicznej",
                "uruchom walidacje polityki strategicznej",
                "start strategic policy validation",
            )),
            ("history", (
                "historia walidacji polityki strategicznej",
                "strategic policy validation history",
            )),
            ("experiments", (
                "eksperymenty polityki strategicznej",
                "pokaż eksperymenty polityki strategicznej",
                "pokaz eksperymenty polityki strategicznej",
                "strategic policy experiments",
            )),
            ("status", (
                "status walidacji polityki strategicznej",
                "pokaż status walidacji polityki strategicznej",
                "pokaz status walidacji polityki strategicznej",
                "status bezpiecznej promocji polityki",
                "status b61",
                "strategic policy validation status",
            )),
        )
        for action, phrases in explicit_checks:
            if any(phrase in normalized for phrase in phrases):
                return action
        mapping = {
            "strategic_validation_status": "status",
            "strategic_validation_history": "history",
            "strategic_validation_experiments": "experiments",
            "strategic_validation_cycle": "cycle",
            "strategic_validation_validate": "validate",
            "strategic_validation_promote": "promote",
            "strategic_validation_reject": "reject",
            "strategic_validation_start": "start",
            "strategic_validation_stop": "stop",
            "strategic_validation_pause": "pause",
            "strategic_validation_resume": "resume",
            "strategic_validation_policy": "policy",
        }
        return mapping.get(operation, "status")
