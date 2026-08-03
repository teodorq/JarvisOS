from __future__ import annotations

import re
from typing import Any

from .strategic_development_service import (
    bootstrap_strategic_development,
)


class SoftwareEngineerStrategicDevelopmentRouter:
    """Polish/English GUI routing for B57 strategic development."""

    READ_PHRASES = (
        "status rozwoju strategicznego",
        "pokaż status rozwoju strategicznego",
        "pokaz status rozwoju strategicznego",
        "roadmapa rozwoju",
        "roadmapę rozwoju",
        "roadmape rozwoju",
        "pokaż roadmapę rozwoju",
        "pokaz roadmape rozwoju",
        "cele strategiczne jarvisa",
        "historia rozwoju strategicznego",
        "status b57",
        "strategic development status",
        "development roadmap",
    )

    MUTATING_PHRASES = (
        "uruchom rozwój strategiczny",
        "uruchom rozwoj strategiczny",
        "zatrzymaj rozwój strategiczny",
        "zatrzymaj rozwoj strategiczny",
        "wstrzymaj rozwój strategiczny",
        "wstrzymaj rozwoj strategiczny",
        "wznów rozwój strategiczny",
        "wznow rozwoj strategiczny",
        "odśwież roadmapę rozwoju",
        "odswiez roadmape rozwoju",
        "wykonaj cykl rozwoju strategicznego",
        "wybierz cel strategiczny",
        "ustaw politykę rozwoju strategicznego",
        "ustaw polityke rozwoju strategicznego",
        "start strategic development",
        "stop strategic development",
        "refresh development roadmap",
        "run strategic development cycle",
    )

    @classmethod
    def can_handle(cls, command: str) -> bool:
        normalized = " ".join(str(command).casefold().split())
        return any(
            phrase in normalized
            for phrase in cls.READ_PHRASES + cls.MUTATING_PHRASES
        )

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        operation = str(
            context.get(
                "strategic_development_action",
                context.get("operation", ""),
            )
        ).strip().casefold()
        normalized = controller._normalize(command)
        if not (
            operation in {
                "strategic_development",
                "strategic_development_status",
                "strategic_development_roadmap",
                "strategic_development_history",
                "strategic_development_refresh",
                "strategic_development_select",
                "strategic_development_cycle",
                "strategic_development_start",
                "strategic_development_stop",
                "strategic_development_pause",
                "strategic_development_resume",
                "strategic_development_policy",
            }
            or self.can_handle(normalized)
        ):
            return None
        service = bootstrap_strategic_development(controller)
        action = self._action(operation, normalized)
        if action == "status":
            return service.status()
        if action == "roadmap":
            return service.roadmap(limit=int(context.get("limit", 50)))
        if action == "history":
            return service.history(limit=int(context.get("limit", 20)))
        if action == "refresh":
            return service.refresh()
        if action == "select":
            return service.select_goal()
        if action == "cycle":
            return service.run_cycle()
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
                self._policy_from_context(context, command)
            )
        return service.status()

    @staticmethod
    def _action(operation: str, normalized: str) -> str:
        # The GUI confirmation flow can preserve an earlier read-only
        # classification such as ``strategic_development_roadmap``.
        # An explicit refresh command is authoritative and must override
        # that stale context after the user confirms the action.
        if any(
            phrase in normalized
            for phrase in (
                "odśwież roadmapę",
                "odswiez roadmape",
                "refresh development roadmap",
            )
        ):
            return "refresh"

        mapping = {
            "strategic_development_status": "status",
            "strategic_development_roadmap": "roadmap",
            "strategic_development_history": "history",
            "strategic_development_refresh": "refresh",
            "strategic_development_select": "select",
            "strategic_development_cycle": "cycle",
            "strategic_development_start": "start",
            "strategic_development_stop": "stop",
            "strategic_development_pause": "pause",
            "strategic_development_resume": "resume",
            "strategic_development_policy": "policy",
        }
        if operation in mapping:
            return mapping[operation]
        checks = (
            # Mutating refresh must win over the overlapping read-only
            # "roadmap" phrase (for example: "Odśwież roadmapę rozwoju").
            ("refresh", ("odśwież roadmapę", "odswiez roadmape", "refresh development")),
            ("history", ("historia rozwoju strategicznego",)),
            ("roadmap", ("roadmapa rozwoju", "roadmapę rozwoju", "roadmape rozwoju", "development roadmap")),
            ("select", ("wybierz cel strategiczny",)),
            ("cycle", ("cykl rozwoju strategicznego", "run strategic development")),
            ("stop", ("zatrzymaj rozwój strategiczny", "zatrzymaj rozwoj strategiczny", "stop strategic")),
            ("pause", ("wstrzymaj rozwój strategiczny", "wstrzymaj rozwoj strategiczny")),
            ("resume", ("wznów rozwój strategiczny", "wznow rozwoj strategiczny")),
            ("policy", ("politykę rozwoju strategicznego", "polityke rozwoju strategicznego")),
            ("start", ("uruchom rozwój strategiczny", "uruchom rozwoj strategiczny", "start strategic")),
            ("status", ("status rozwoju strategicznego", "status b57", "cele strategiczne jarvisa")),
        )
        for action, phrases in checks:
            if any(phrase in normalized for phrase in phrases):
                return action
        return "status"

    @staticmethod
    def _policy_from_context(
        context: dict[str, Any],
        command: str,
    ) -> dict[str, Any]:
        policy = dict(context.get("strategic_development_policy", {}) or {})
        normalized = str(command).casefold().replace(",", ".")
        patterns = {
            "refresh_interval_seconds": r"odśwież(?:aj)?\s*co\s*(\d+)\s*sekund",
            "min_goal_score": r"min(?:imum)?\s*(?:goal\s*)?score\s*(\d+(?:\.\d+)?)",
            "max_goal_risk": r"max(?:imum)?\s*(?:goal\s*)?risk\s*(\d+(?:\.\d+)?)",
            "min_goal_confidence": r"min(?:imum)?\s*confidence\s*(\d+(?:\.\d+)?)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, normalized)
            if match:
                policy[key] = float(match.group(1))
        policy["max_active_goals"] = 1
        policy["auto_approve"] = False
        return policy
