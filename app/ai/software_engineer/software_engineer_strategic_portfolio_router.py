from __future__ import annotations

from typing import Any

from .strategic_portfolio_service import bootstrap_strategic_portfolio
from .software_engineer_strategic_policy_router import (
    SoftwareEngineerStrategicPolicyRouter,
)


_STRATEGIC_POLICY_ROUTER = SoftwareEngineerStrategicPolicyRouter()


class SoftwareEngineerStrategicPortfolioRouter:
    """Polish/English GUI routing for B59 adaptive portfolio."""

    READ_PHRASES = (
        "status portfolio strategicznego",
        "pokaż status portfolio strategicznego",
        "pokaz status portfolio strategicznego",
        "portfolio strategiczne",
        "pokaż portfolio strategiczne",
        "pokaz portfolio strategiczne",
        "historia portfolio strategicznego",
        "pokaż historię portfolio strategicznego",
        "pokaz historie portfolio strategicznego",
        "status adaptacji strategicznej",
        "status b59",
        "strategic portfolio status",
        "strategic portfolio history",
    )

    MUTATING_PHRASES = (
        "uruchom adaptację strategiczną",
        "uruchom adaptacje strategiczna",
        "zatrzymaj adaptację strategiczną",
        "zatrzymaj adaptacje strategiczna",
        "wstrzymaj adaptację strategiczną",
        "wstrzymaj adaptacje strategiczna",
        "wznów adaptację strategiczną",
        "wznow adaptacje strategiczna",
        "przelicz portfolio strategiczne",
        "zbalansuj portfolio strategiczne",
        "wybierz następny cel adaptacyjnie",
        "wybierz nastepny cel adaptacyjnie",
        "ustaw politykę portfolio strategicznego",
        "ustaw polityke portfolio strategicznego",
        "start strategic portfolio",
        "stop strategic portfolio",
        "pause strategic portfolio",
        "resume strategic portfolio",
        "rebalance strategic portfolio",
        "recommend strategic portfolio goal",
    )

    @classmethod
    def can_handle(cls, command: str) -> bool:
        normalized = " ".join(str(command).casefold().split())
        return (
            _STRATEGIC_POLICY_ROUTER.can_handle(normalized)
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
        evolved = _STRATEGIC_POLICY_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )
        if evolved is not None:
            return evolved
        operation = str(
            context.get(
                "strategic_portfolio_action",
                context.get("operation", ""),
            )
        ).strip().casefold()
        normalized = controller._normalize(command)
        if not (
            operation in {
                "strategic_portfolio",
                "strategic_portfolio_status",
                "strategic_portfolio_view",
                "strategic_portfolio_history",
                "strategic_portfolio_rebalance",
                "strategic_portfolio_recommend",
                "strategic_portfolio_start",
                "strategic_portfolio_stop",
                "strategic_portfolio_pause",
                "strategic_portfolio_resume",
                "strategic_portfolio_policy",
            }
            or self.can_handle(normalized)
        ):
            return None
        service = bootstrap_strategic_portfolio(controller)
        action = self._action(operation, normalized)
        if action == "status":
            return service.status()
        if action == "portfolio":
            return service.portfolio(limit=int(context.get("limit", 50)))
        if action == "history":
            return service.history(limit=int(context.get("limit", 20)))
        if action == "rebalance":
            return service.rebalance()
        if action == "recommend":
            return service.recommend_opportunity()
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
                dict(context.get("strategic_portfolio_policy", {}) or {})
            )
        return service.status()

    @staticmethod
    def _action(operation: str, normalized: str) -> str:
        explicit_checks = (
            ("rebalance", (
                "przelicz portfolio strategiczne",
                "zbalansuj portfolio strategiczne",
                "rebalance strategic portfolio",
            )),
            ("recommend", (
                "wybierz następny cel adaptacyjnie",
                "wybierz nastepny cel adaptacyjnie",
                "recommend strategic portfolio goal",
            )),
            ("stop", (
                "zatrzymaj adaptację strategiczną",
                "zatrzymaj adaptacje strategiczna",
                "stop strategic portfolio",
            )),
            ("pause", (
                "wstrzymaj adaptację strategiczną",
                "wstrzymaj adaptacje strategiczna",
                "pause strategic portfolio",
            )),
            ("resume", (
                "wznów adaptację strategiczną",
                "wznow adaptacje strategiczna",
                "resume strategic portfolio",
            )),
            ("policy", (
                "ustaw politykę portfolio strategicznego",
                "ustaw polityke portfolio strategicznego",
            )),
            ("start", (
                "uruchom adaptację strategiczną",
                "uruchom adaptacje strategiczna",
                "start strategic portfolio",
            )),
            ("history", (
                "historia portfolio strategicznego",
                "pokaż historię portfolio strategicznego",
                "pokaz historie portfolio strategicznego",
                "strategic portfolio history",
            )),
            ("status", (
                "status portfolio strategicznego",
                "pokaż status portfolio strategicznego",
                "pokaz status portfolio strategicznego",
                "status adaptacji strategicznej",
                "status b59",
                "strategic portfolio status",
            )),
            ("portfolio", (
                "pokaż portfolio strategiczne",
                "pokaz portfolio strategiczne",
                "portfolio strategiczne",
            )),
        )
        for action, phrases in explicit_checks:
            if any(phrase in normalized for phrase in phrases):
                return action
        mapping = {
            "strategic_portfolio_status": "status",
            "strategic_portfolio_view": "portfolio",
            "strategic_portfolio_history": "history",
            "strategic_portfolio_rebalance": "rebalance",
            "strategic_portfolio_recommend": "recommend",
            "strategic_portfolio_start": "start",
            "strategic_portfolio_stop": "stop",
            "strategic_portfolio_pause": "pause",
            "strategic_portfolio_resume": "resume",
            "strategic_portfolio_policy": "policy",
        }
        return mapping.get(operation, "status")
