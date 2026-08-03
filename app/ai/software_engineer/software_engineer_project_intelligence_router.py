from __future__ import annotations

import re
from typing import Any

from .project_intelligence_service import (
    bootstrap_project_intelligence,
)


class SoftwareEngineerProjectIntelligenceRouter:
    """Polish/English GUI routing for B55 project intelligence."""

    READ_PHRASES = (
        "status inteligencji projektu",
        "pokaż status inteligencji projektu",
        "pokaz status inteligencji projektu",
        "backlog rozwoju",
        "pokaż backlog rozwoju",
        "pokaz backlog rozwoju",
        "historia inteligencji projektu",
        "historia rozwoju autonomicznego",
        "status zadania rozwoju",
        "project intelligence status",
        "development backlog",
        "opportunity-",
    )

    MUTATING_PHRASES = (
        "skanuj projekt i zbuduj backlog",
        "przeskanuj projekt i zbuduj backlog",
        "wykonaj cykl inteligencji projektu",
        "uruchom autonomiczny rozwój projektu",
        "zatrzymaj autonomiczny rozwój projektu",
        "wstrzymaj autonomiczny rozwój projektu",
        "wznów autonomiczny rozwój projektu",
        "uruchom najlepsze zadanie rozwoju",
        "wykonaj najlepsze zadanie rozwoju",
        "odrzuć zadanie rozwoju",
        "odrzuc zadanie rozwoju",
        "ustaw politykę inteligencji projektu",
        "ustaw polityke inteligencji projektu",
        "scan project backlog",
        "start project intelligence",
        "stop project intelligence",
        "dispatch best opportunity",
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
                "project_intelligence_action",
                context.get("operation", ""),
            )
        ).strip().casefold()
        normalized = controller._normalize(command)
        if not (
            operation in {
                "project_intelligence",
                "project_intelligence_status",
                "project_intelligence_scan",
                "project_intelligence_cycle",
                "project_intelligence_dispatch",
                "project_intelligence_start",
                "project_intelligence_stop",
                "project_intelligence_pause",
                "project_intelligence_resume",
                "project_intelligence_backlog",
                "project_intelligence_history",
                "project_intelligence_opportunity",
                "project_intelligence_reject",
                "project_intelligence_policy",
            }
            or any(
                phrase in normalized
                for phrase in self.READ_PHRASES + self.MUTATING_PHRASES
            )
        ):
            return None
        service = bootstrap_project_intelligence(controller)
        action = self._action(operation, normalized)
        opportunity_id = self._opportunity_id(command, context)

        if action == "status":
            return service.status()
        if action == "backlog":
            return service.backlog(limit=int(context.get("limit", 50)))
        if action == "history":
            return service.history(limit=int(context.get("limit", 20)))
        if action == "opportunity":
            return service.opportunity(opportunity_id)
        if action == "scan":
            return service.scan_project()
        if action == "cycle":
            return service.run_cycle(
                dispatch=bool(context.get("dispatch", False))
            )
        if action == "dispatch":
            return service.dispatch_best(force=True)
        if action == "start":
            return service.start_background()
        if action == "stop":
            return service.stop_background()
        if action == "pause":
            return service.pause()
        if action == "resume":
            return service.resume()
        if action == "reject":
            return service.reject(opportunity_id)
        if action == "policy":
            return service.update_policy(
                self._policy_from_context(context, command)
            )
        return service.status()

    @staticmethod
    def _action(operation: str, normalized: str) -> str:
        mapping = {
            "project_intelligence_status": "status",
            "project_intelligence_scan": "scan",
            "project_intelligence_cycle": "cycle",
            "project_intelligence_dispatch": "dispatch",
            "project_intelligence_start": "start",
            "project_intelligence_stop": "stop",
            "project_intelligence_pause": "pause",
            "project_intelligence_resume": "resume",
            "project_intelligence_backlog": "backlog",
            "project_intelligence_history": "history",
            "project_intelligence_opportunity": "opportunity",
            "project_intelligence_reject": "reject",
            "project_intelligence_policy": "policy",
        }
        if operation in mapping:
            return mapping[operation]
        checks = (
            ("history", ("historia inteligencji", "historia rozwoju")),
            ("opportunity", ("status zadania rozwoju", "opportunity-")),
            ("backlog", ("backlog rozwoju", "development backlog")),
            ("scan", ("skanuj projekt", "przeskanuj projekt", "scan project")),
            ("cycle", ("cykl inteligencji",)),
            ("dispatch", ("najlepsze zadanie rozwoju", "dispatch best")),
            ("start", ("uruchom autonomiczny rozwój", "start project intelligence")),
            ("stop", ("zatrzymaj autonomiczny rozwój", "stop project intelligence")),
            ("pause", ("wstrzymaj autonomiczny rozwój",)),
            ("resume", ("wznów autonomiczny rozwój", "wznow autonomiczny rozwoj")),
            ("reject", ("odrzuć zadanie rozwoju", "odrzuc zadanie rozwoju")),
            ("policy", ("ustaw politykę inteligencji", "ustaw polityke inteligencji")),
            ("status", ("status inteligencji projektu",)),
        )
        for action, phrases in checks:
            if any(phrase in normalized for phrase in phrases):
                return action
        return "status"

    @staticmethod
    def _opportunity_id(
        command: str,
        context: dict[str, Any],
    ) -> str:
        provided = str(
            context.get(
                "opportunity_id",
                context.get("task_id", ""),
            )
        ).strip()
        if provided:
            return provided
        match = re.search(
            r"\bopportunity-[a-f0-9]{16,64}\b",
            str(command),
            flags=re.IGNORECASE,
        )
        return match.group(0) if match else ""

    @staticmethod
    def _policy_from_context(
        context: dict[str, Any],
        command: str,
    ) -> dict[str, Any]:
        policy = dict(
            context.get("project_intelligence_policy", {})
            or {}
        )
        normalized = str(command).casefold().replace(",", ".")
        patterns = {
            "min_score": r"min(?:imum)?\s*score\s*(\d+(?:\.\d+)?)",
            "max_risk": r"max(?:imum)?\s*risk\s*(\d+(?:\.\d+)?)",
            "max_active_jobs": r"aktywn(?:e|ych)\s*(\d+)",
            "scan_interval_seconds": r"co\s*(\d+)\s*sekund",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, normalized)
            if match:
                policy[key] = float(match.group(1))
        if "auto dispatch on" in normalized or "automatyczne uruchamianie wlaczone" in normalized:
            policy["auto_dispatch"] = True
        if "auto dispatch off" in normalized or "automatyczne uruchamianie wylaczone" in normalized:
            policy["auto_dispatch"] = False
        policy["auto_approve"] = False
        return policy
