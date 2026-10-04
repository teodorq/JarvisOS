from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ClientContextSuggestion:
    label: str
    command: str


def context_suggestions(
    moment: datetime | None = None,
) -> tuple[str, tuple[ClientContextSuggestion, ...]]:
    local = moment or datetime.now().astimezone()
    hour = local.hour
    if 5 <= hour < 11:
        return "PORANEK", (
            ClientContextSuggestion("PLAN DNIA", "Pokaż mój plan na dziś"),
            ClientContextSuggestion("KALENDARZ", "Co mam dziś w kalendarzu?"),
            ClientContextSuggestion("POGODA", "Jaka jest pogoda?"),
        )
    if 11 <= hour < 17:
        return "DZIEŃ", (
            ClientContextSuggestion(
                "NAJWAŻNIEJSZE", "Co jest teraz najważniejsze?"
            ),
            ClientContextSuggestion(
                "WAŻNA POCZTA", "Znajdź ważne wiadomości Gmail"
            ),
            ClientContextSuggestion(
                "PRZYPOMNIENIA", "Pokaż najbliższe przypomnienia"
            ),
        )
    return "WIECZÓR", (
        ClientContextSuggestion("PODSUMUJ DZIEŃ", "Jak minął dzień?"),
        ClientContextSuggestion("UPORZĄDKUJ JUTRO", "Uporządkuj mi jutro"),
        ClientContextSuggestion(
            "PRZYPOMNIENIA", "Pokaż najbliższe przypomnienia"
        ),
    )


__all__ = ["ClientContextSuggestion", "context_suggestions"]
