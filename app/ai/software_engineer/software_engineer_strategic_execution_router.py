from __future__ import annotations

from typing import Any

from .strategic_execution_service import bootstrap_strategic_execution
from .software_engineer_strategic_portfolio_router import (
    SoftwareEngineerStrategicPortfolioRouter,
)


_STRATEGIC_PORTFOLIO_ROUTER = SoftwareEngineerStrategicPortfolioRouter()


class SoftwareEngineerStrategicExecutionRouter:
    """Polish/English GUI routing for B58 strategic execution."""

    READ_PHRASES = (
        "status wykonania strategicznego",
        "pokaż status wykonania strategicznego",
        "pokaz status wykonania strategicznego",
        "historia wykonania strategicznego",
        "pokaż historię wykonania strategicznego",
        "pokaz historie wykonania strategicznego",
        "status b58",
        "strategic execution status",
        "strategic execution history",
    )

    MUTATING_PHRASES = (
        "uruchom wykonanie strategiczne",
        "zatrzymaj wykonanie strategiczne",
        "wstrzymaj wykonanie strategiczne",
        "wznów wykonanie strategiczne",
        "wznow wykonanie strategiczne",
        "synchronizuj wykonanie strategiczne",
        "zsynchronizuj wykonanie strategiczne",
        "wykonaj następne zadanie strategiczne",
        "wykonaj nastepne zadanie strategiczne",
        "ustaw politykę wykonania strategicznego",
        "ustaw polityke wykonania strategicznego",
        "start strategic execution",
        "stop strategic execution",
        "pause strategic execution",
        "resume strategic execution",
        "sync strategic execution",
        "dispatch strategic execution",
    )

    @classmethod
    def can_handle(cls, command: str) -> bool:
        normalized = " ".join(str(command).casefold().split())
        return (
            _STRATEGIC_PORTFOLIO_ROUTER.can_handle(normalized)
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
        portfolio = _STRATEGIC_PORTFOLIO_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )
        if portfolio is not None:
            return portfolio
        operation = str(
            context.get(
                "strategic_execution_action",
                context.get("operation", ""),
            )
        ).strip().casefold()
        normalized = controller._normalize(command)
        if not (
            operation in {
                "strategic_execution",
                "strategic_execution_status",
                "strategic_execution_history",
                "strategic_execution_sync",
                "strategic_execution_dispatch",
                "strategic_execution_start",
                "strategic_execution_stop",
                "strategic_execution_pause",
                "strategic_execution_resume",
                "strategic_execution_policy",
            }
            or self.can_handle(normalized)
        ):
            return None
        service = bootstrap_strategic_execution(controller)
        action = self._action(operation, normalized)
        if action == "status":
            return service.status()
        if action == "history":
            return service.history(limit=int(context.get("limit", 20)))
        if action == "sync":
            return service.reconcile()
        if action == "dispatch":
            return service.dispatch_next()
        if action == "start":
            return service.start()
        if action == "stop":
            return service.stop()
        if action == "pause":
            return service.pause()
        if action == "resume":
            return service.resume()
        if action == "policy":
            return service.update_policy(
                dict(context.get("strategic_execution_policy", {}) or {})
            )
        return service.status()

    @staticmethod
    def _action(operation: str, normalized: str) -> str:
        # The GUI confirmation flow may preserve an earlier read-only
        # operation in context. An explicit command is authoritative and
        # must override that stale context after the user confirms with TAK.
        explicit_checks = (
            ("dispatch", (
                "wykonaj następne zadanie strategiczne",
                "wykonaj nastepne zadanie strategiczne",
                "dispatch strategic execution",
            )),
            ("sync", (
                "synchronizuj wykonanie strategiczne",
                "zsynchronizuj wykonanie strategiczne",
                "sync strategic execution",
            )),
            ("stop", (
                "zatrzymaj wykonanie strategiczne",
                "stop strategic execution",
            )),
            ("pause", (
                "wstrzymaj wykonanie strategiczne",
                "pause strategic execution",
            )),
            ("resume", (
                "wznów wykonanie strategiczne",
                "wznow wykonanie strategiczne",
                "resume strategic execution",
            )),
            ("policy", (
                "ustaw politykę wykonania strategicznego",
                "ustaw polityke wykonania strategicznego",
            )),
            ("start", (
                "uruchom wykonanie strategiczne",
                "start strategic execution",
            )),
            ("history", (
                "historia wykonania strategicznego",
                "pokaż historię wykonania strategicznego",
                "pokaz historie wykonania strategicznego",
                "strategic execution history",
            )),
            ("status", (
                "pokaż status wykonania strategicznego",
                "pokaz status wykonania strategicznego",
                "status wykonania strategicznego",
                "status b58",
                "strategic execution status",
            )),
        )
        for action, phrases in explicit_checks:
            if any(phrase in normalized for phrase in phrases):
                return action

        mapping = {
            "strategic_execution_status": "status",
            "strategic_execution_history": "history",
            "strategic_execution_sync": "sync",
            "strategic_execution_dispatch": "dispatch",
            "strategic_execution_start": "start",
            "strategic_execution_stop": "stop",
            "strategic_execution_pause": "pause",
            "strategic_execution_resume": "resume",
            "strategic_execution_policy": "policy",
        }
        if operation in mapping:
            return mapping[operation]
        checks = (
            ("history", ("historia wykonania strategicznego", "strategic execution history")),
            ("sync", ("synchronizuj wykonanie", "zsynchronizuj wykonanie", "sync strategic execution")),
            ("dispatch", ("następne zadanie strategiczne", "nastepne zadanie strategiczne", "dispatch strategic execution")),
            ("stop", ("zatrzymaj wykonanie strategiczne", "stop strategic execution")),
            ("pause", ("wstrzymaj wykonanie strategiczne", "pause strategic execution")),
            ("resume", ("wznów wykonanie strategiczne", "wznow wykonanie strategiczne", "resume strategic execution")),
            ("policy", ("politykę wykonania strategicznego", "polityke wykonania strategicznego")),
            ("start", ("uruchom wykonanie strategiczne", "start strategic execution")),
            ("status", ("status wykonania strategicznego", "status b58", "strategic execution status")),
        )
        for action, phrases in checks:
            if any(phrase in normalized for phrase in phrases):
                return action
        return "status"
