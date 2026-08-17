"""Client-safe, human-readable capability guide for JARVIS OS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapabilityCategory:
    title: str
    summary: str
    examples: tuple[str, ...]


CAPABILITY_CATEGORIES: tuple[CapabilityCategory, ...] = (
    CapabilityCategory(
        "Twój dzień",
        "priorytety, plan dnia, podsumowania i przypomnienia",
        (
            "Co jest teraz najważniejsze?",
            "Przypomnij mi o rachunku jutro o 18",
        ),
    ),
    CapabilityCategory(
        "Poczta i kalendarz",
        "wyszukiwanie Gmaila, przygotowanie wiadomości i obsługa terminów",
        (
            "Znajdź moje najnowsze wiadomości Gmail",
            "Co mam dziś w kalendarzu?",
        ),
    ),
    CapabilityCategory(
        "Dokumenty i pamięć",
        "szukanie dokumentów oraz pamięć projektów i preferencji",
        (
            "Znajdź dokument umowa",
            "Status pamięci projektów",
        ),
    ),
    CapabilityCategory(
        "Komputer i głos",
        "sterowanie pulpitem, programami i ustawieniami głosu",
        (
            "Status sterowania pulpitem",
            "Status głosu",
        ),
    ),
    CapabilityCategory(
        "Pogoda",
        "bie\u017c\u0105ce warunki i prognoza na jutro dla miast na ca\u0142ym \u015bwiecie",
        (
            "Jaka jest pogoda w Miami?",
            "Jaka b\u0119dzie pogoda jutro w Warszawie?",
        ),
    ),
    CapabilityCategory(
        "System i integracje",
        "stan JARVIS OS, Azure i opcjonalnych połączeń zewnętrznych",
        (
            "Pokaż status integracji",
            "Status asystenta",
        ),
    ),
)


class CapabilityGuideService:
    """Expose only verified, daily-use examples without performing actions."""

    categories = CAPABILITY_CATEGORIES

    def examples(self) -> tuple[str, ...]:
        return tuple(
            example
            for category in self.categories
            for example in category.examples
        )

    def status(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "category_count": len(self.categories),
            "example_count": len(self.examples()),
            "client_safe": True,
            "external_requests": False,
        }

    def format_guide(self) -> str:
        lines = ["JARVIS OS — w czym mogę Ci pomóc:"]
        for category in self.categories:
            lines.append(
                f"• {category.title}: {category.summary}. "
                f"Spróbuj: „{category.examples[0]}”"
            )
        lines.append(
            "Polecenia zmieniające dane lub sterujące komputerem nadal wymagają "
            "potwierdzenia zgodnie z zasadami bezpieczeństwa."
        )
        return "\n".join(lines)


__all__ = [
    "CAPABILITY_CATEGORIES",
    "CapabilityCategory",
    "CapabilityGuideService",
]
