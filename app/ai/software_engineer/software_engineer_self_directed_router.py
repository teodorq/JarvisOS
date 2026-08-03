from __future__ import annotations

import re
from typing import Any

from .self_directed_development_service import (
    bootstrap_self_directed_development,
)


class SoftwareEngineerSelfDirectedRouter:
    """GUI routing for B56 self-directed development supervision."""

    READ_PHRASES = (
        "status samodzielnego rozwoju",
        "pokaż status samodzielnego rozwoju",
        "pokaz status samodzielnego rozwoju",
        "historia samodzielnego rozwoju",
        "pokaż historię samodzielnego rozwoju",
        "pokaz historie samodzielnego rozwoju",
        "status b56",
        "self directed development status",
        "self-directed development status",
    )

    MUTATING_PHRASES = (
        "uruchom samodzielny rozwój",
        "uruchom samodzielny rozwoj",
        "uruchom samodzielny rozwój jarvisa",
        "uruchom samodzielny rozwój projektu",
        "zatrzymaj samodzielny rozwój",
        "zatrzymaj samodzielny rozwoj",
        "wstrzymaj samodzielny rozwój",
        "wstrzymaj samodzielny rozwoj",
        "wznów samodzielny rozwój",
        "wznow samodzielny rozwoj",
        "wykonaj cykl samodzielnego rozwoju",
        "ustaw politykę samodzielnego rozwoju",
        "ustaw polityke samodzielnego rozwoju",
        "start self directed development",
        "start self-directed development",
        "stop self directed development",
        "run self directed development cycle",
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
                "self_directed_action",
                context.get("operation", ""),
            )
        ).strip().casefold()
        normalized = controller._normalize(command)
        if not (
            operation in {
                "self_directed_development",
                "self_directed_status",
                "self_directed_start",
                "self_directed_stop",
                "self_directed_pause",
                "self_directed_resume",
                "self_directed_cycle",
                "self_directed_history",
                "self_directed_policy",
            }
            or any(
                phrase in normalized
                for phrase in self.READ_PHRASES + self.MUTATING_PHRASES
            )
        ):
            return None
        service = bootstrap_self_directed_development(controller)
        action = self._action(operation, normalized)
        if action == "status":
            return service.status()
        if action == "history":
            return service.history(limit=int(context.get("limit", 20)))
        if action == "start":
            return service.start_background()
        if action == "stop":
            return service.stop_background()
        if action == "pause":
            return service.pause()
        if action == "resume":
            return service.resume()
        if action == "cycle":
            return service.run_cycle(
                force_dispatch=bool(context.get("force_dispatch", False))
            )
        if action == "policy":
            return service.update_policy(
                self._policy_from_context(context, command)
            )
        return service.status()

    @staticmethod
    def _action(operation: str, normalized: str) -> str:
        mapping = {
            "self_directed_status": "status",
            "self_directed_start": "start",
            "self_directed_stop": "stop",
            "self_directed_pause": "pause",
            "self_directed_resume": "resume",
            "self_directed_cycle": "cycle",
            "self_directed_history": "history",
            "self_directed_policy": "policy",
        }
        if operation in mapping:
            return mapping[operation]
        checks = (
            ("history", ("historia samodzielnego",)),
            ("cycle", ("cykl samodzielnego", "run self directed")),
            ("stop", ("zatrzymaj samodzielny", "stop self directed")),
            ("pause", ("wstrzymaj samodzielny",)),
            ("resume", ("wznów samodzielny", "wznow samodzielny")),
            ("policy", ("politykę samodzielnego", "polityke samodzielnego")),
            ("start", ("uruchom samodzielny", "start self directed")),
            ("status", ("status samodzielnego", "status b56")),
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
        policy = dict(context.get("self_directed_policy", {}) or {})
        normalized = str(command).casefold().replace(",", ".")
        patterns = {
            "interval_seconds": r"cykl\s*co\s*(\d+)\s*sekund",
            "scan_interval_seconds": r"skan\s*co\s*(\d+)\s*sekund",
            "max_dispatches_per_day": r"dzienn(?:ie|y\s*limit)\s*(\d+)",
            "max_consecutive_failures": r"(?:błędów|bledow)\s*(\d+)",
            "max_active_jobs": r"aktywn(?:e|ych)\s*(\d+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, normalized)
            if match:
                policy[key] = float(match.group(1))
        policy["auto_approve"] = False
        return policy
