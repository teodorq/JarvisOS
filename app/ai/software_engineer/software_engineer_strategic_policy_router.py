from __future__ import annotations

from typing import Any

from .strategic_policy_evolution_service import (
    bootstrap_strategic_policy_evolution,
)
from .software_engineer_strategic_validation_router import (
    SoftwareEngineerStrategicValidationRouter,
)


_STRATEGIC_VALIDATION_ROUTER = SoftwareEngineerStrategicValidationRouter()


class SoftwareEngineerStrategicPolicyRouter:
    """Polish/English GUI routing for B60 strategic policy evolution."""

    READ_PHRASES = (
        "status samouczenia strategicznego",
        "pokaż status samouczenia strategicznego",
        "pokaz status samouczenia strategicznego",
        "status ewolucji polityki strategicznej",
        "pokaż politykę ewolucji strategicznej",
        "pokaz polityke ewolucji strategicznej",
        "historia ewolucji polityki strategicznej",
        "pokaż historię ewolucji polityki strategicznej",
        "pokaz historie ewolucji polityki strategicznej",
        "wersje polityki strategicznej",
        "pokaż wersje polityki strategicznej",
        "pokaz wersje polityki strategicznej",
        "status b60",
        "strategic policy evolution status",
        "strategic policy evolution history",
        "strategic policy revisions",
    )

    MUTATING_PHRASES = (
        "uruchom samouczenie strategiczne",
        "zatrzymaj samouczenie strategiczne",
        "wstrzymaj samouczenie strategiczne",
        "wznów samouczenie strategiczne",
        "wznow samouczenie strategiczne",
        "wykonaj cykl samouczenia strategicznego",
        "przeprowadź cykl samouczenia strategicznego",
        "przeprowadz cykl samouczenia strategicznego",
        "przelicz ewolucję polityki strategicznej",
        "przelicz ewolucje polityki strategicznej",
        "zastosuj proponowaną politykę strategiczną",
        "zastosuj proponowana polityke strategiczna",
        "cofnij politykę strategiczną",
        "cofnij polityke strategiczna",
        "ustaw politykę samouczenia strategicznego",
        "ustaw polityke samouczenia strategicznego",
        "start strategic policy evolution",
        "stop strategic policy evolution",
        "pause strategic policy evolution",
        "resume strategic policy evolution",
        "run strategic policy learning cycle",
        "apply strategic policy proposal",
        "rollback strategic policy",
    )

    @classmethod
    def can_handle(cls, command: str) -> bool:
        normalized = " ".join(str(command).casefold().split())
        return (
            _STRATEGIC_VALIDATION_ROUTER.can_handle(normalized)
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
        validated = _STRATEGIC_VALIDATION_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )
        if validated is not None:
            return validated
        operation = str(
            context.get(
                "strategic_policy_action",
                context.get("operation", ""),
            )
        ).strip().casefold()
        normalized = controller._normalize(command)
        if not (
            operation in {
                "strategic_policy_evolution",
                "strategic_policy_status",
                "strategic_policy_history",
                "strategic_policy_revisions",
                "strategic_policy_learn",
                "strategic_policy_apply",
                "strategic_policy_rollback",
                "strategic_policy_start",
                "strategic_policy_stop",
                "strategic_policy_pause",
                "strategic_policy_resume",
                "strategic_policy_policy",
            }
            or self.can_handle(normalized)
        ):
            return None
        service = bootstrap_strategic_policy_evolution(controller)
        action = self._action(operation, normalized)
        if action == "status":
            return service.status()
        if action == "history":
            return service.history(limit=int(context.get("limit", 20)))
        if action == "revisions":
            return service.revisions(limit=int(context.get("limit", 50)))
        if action == "learn":
            return service.learn(apply_if_safe=context.get("apply_if_safe"))
        if action == "apply":
            return service.apply_proposal(str(context.get("revision_id", "")))
        if action == "rollback":
            return service.rollback()
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
                dict(context.get("strategic_policy_evolution_policy", {}) or {})
            )
        return service.status()

    @staticmethod
    def _action(operation: str, normalized: str) -> str:
        explicit_checks = (
            ("learn", (
                "wykonaj cykl samouczenia strategicznego",
                "przeprowadź cykl samouczenia strategicznego",
                "przeprowadz cykl samouczenia strategicznego",
                "przelicz ewolucję polityki strategicznej",
                "przelicz ewolucje polityki strategicznej",
                "run strategic policy learning cycle",
            )),
            ("apply", (
                "zastosuj proponowaną politykę strategiczną",
                "zastosuj proponowana polityke strategiczna",
                "apply strategic policy proposal",
            )),
            ("rollback", (
                "cofnij politykę strategiczną",
                "cofnij polityke strategiczna",
                "rollback strategic policy",
            )),
            ("stop", (
                "zatrzymaj samouczenie strategiczne",
                "stop strategic policy evolution",
            )),
            ("pause", (
                "wstrzymaj samouczenie strategiczne",
                "pause strategic policy evolution",
            )),
            ("resume", (
                "wznów samouczenie strategiczne",
                "wznow samouczenie strategiczne",
                "resume strategic policy evolution",
            )),
            ("policy", (
                "ustaw politykę samouczenia strategicznego",
                "ustaw polityke samouczenia strategicznego",
            )),
            ("start", (
                "uruchom samouczenie strategiczne",
                "start strategic policy evolution",
            )),
            ("history", (
                "historia ewolucji polityki strategicznej",
                "pokaż historię ewolucji polityki strategicznej",
                "pokaz historie ewolucji polityki strategicznej",
                "strategic policy evolution history",
            )),
            ("revisions", (
                "wersje polityki strategicznej",
                "pokaż wersje polityki strategicznej",
                "pokaz wersje polityki strategicznej",
                "strategic policy revisions",
            )),
            ("status", (
                "status samouczenia strategicznego",
                "pokaż status samouczenia strategicznego",
                "pokaz status samouczenia strategicznego",
                "status ewolucji polityki strategicznej",
                "status b60",
                "strategic policy evolution status",
            )),
        )
        for action, phrases in explicit_checks:
            if any(phrase in normalized for phrase in phrases):
                return action
        mapping = {
            "strategic_policy_status": "status",
            "strategic_policy_history": "history",
            "strategic_policy_revisions": "revisions",
            "strategic_policy_learn": "learn",
            "strategic_policy_apply": "apply",
            "strategic_policy_rollback": "rollback",
            "strategic_policy_start": "start",
            "strategic_policy_stop": "stop",
            "strategic_policy_pause": "pause",
            "strategic_policy_resume": "resume",
            "strategic_policy_policy": "policy",
        }
        return mapping.get(operation, "status")
