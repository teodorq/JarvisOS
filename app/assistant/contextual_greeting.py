from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


class ContextualGreetingService:
    """Turn a natural greeting into one useful, read-only daily answer."""

    def __init__(
        self,
        natural_actions: Any,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.natural_actions = natural_actions
        self.now_provider = now_provider or (lambda: datetime.now().astimezone())

    def reply(self) -> str:
        hour = self.now_provider().astimezone().hour
        if 5 <= hour < 11:
            greeting = "Dzień dobry."
            command = "Pokaż mój plan na dziś"
        elif 11 <= hour < 17:
            greeting = "Cześć."
            command = "Co jest teraz najważniejsze?"
        else:
            greeting = "Dobry wieczór."
            command = "Jak minął dzień?"
        answer = " ".join(str(self.natural_actions.handle(command) or "").split())
        if not answer:
            answer = "Jestem gotowy. Powiedz, czym mam się zająć."
        return f"{greeting} {answer}"


__all__ = ["ContextualGreetingService"]
