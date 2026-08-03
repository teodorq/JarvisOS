from __future__ import annotations

import re
import unicodedata
from typing import Any


class IntelligentDayQuality:
    """Text cleanup, Polish grammar and conservative mail ranking for B160.1."""

    ACTION_TERMS = (
        "pilne",
        "ważne",
        "odpowiedź",
        "odpowiedz",
        "termin",
        "faktura",
        "płatność",
        "spotkanie",
        "klient",
        "projekt",
        "umowa",
        "potwierdzenie",
        "rezerwacja",
        "zamówienie",
        "problem",
        "awaria",
        "prośba",
        "wymaga",
        "do akceptacji",
        "przesyłka",
        "doręczenie",
        "numer zamówienia",
        "status zamówienia",
        "śledzenie przesyłki",
        "tracking",
    )
    MARKETING_TERMS = (
        "wypisz się",
        "unsubscribe",
        "newsletter",
        "promocja",
        "wyprzedaż",
        "rabat",
        "kod rabatowy",
        "kup teraz",
        "oferta specjalna",
        "limited offer",
        "black friday",
        "cyber monday",
        "darmowa dostawa",
        "bonus",
        "okazja",
        "wybór należy do ciebie",
        "tylko dziś",
        "ostatnia szansa",
        "specjalna dostawa",
        "specjalnie dla ciebie",
        "czeka na ciebie",
        "niespodzianka",
        "prezent dla ciebie",
        "odbierz nagrodę",
        "nie przegap",
        "poznaj ofertę",
        "wyjątkowa oferta",
        "nowość dla ciebie",
    )
    MARKETING_SENDERS = (
        "newsletter",
        "marketing",
        "promocje",
        "offers",
        "deals",
        "no-reply",
        "noreply",
    )
    SOCIAL_NOTIFICATION_TERMS = (
        "właśnie wysłał(a) ci wiadomość",
        "właśnie wysłała ci wiadomość",
        "właśnie wysłał ci wiadomość",
        "zaczął cię obserwować",
        "polubił twój",
        "oznaczył cię",
    )
    SOCIAL_NOTIFICATION_SENDERS = ("notification@service.tiktok.com", "facebookmail.com", "instagram.com")

    @classmethod
    def clean_text(cls, value: object, limit: int = 300) -> str:
        text = unicodedata.normalize("NFKC", str(value or ""))
        kept: list[str] = []
        for char in text:
            category = unicodedata.category(char)
            if char == "\ufffd" or category in {"Cf", "Cs", "Co", "Cn"}:
                continue
            if category.startswith("S"):
                continue
            if category.startswith("C") and char not in "\n\t":
                continue
            kept.append(char)
        result = " ".join("".join(kept).split())
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)
        return result.strip(" ,.;:-")[:limit]

    @classmethod
    def rank_mail(cls, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked: list[tuple[int, int, dict[str, Any]]] = []
        for index, raw in enumerate(messages):
            message = dict(raw)
            subject = cls.clean_text(message.get("subject"), 240)
            sender = cls.clean_text(message.get("from"), 240)
            snippet = cls.clean_text(message.get("snippet"), 500)
            message.update({"subject": subject, "from": sender, "snippet": snippet})
            haystack = f"{subject} {sender} {snippet}".casefold()
            action_hits = sum(term in haystack for term in cls.ACTION_TERMS)
            marketing_hits = sum(term in haystack for term in cls.MARKETING_TERMS)
            sender_hits = sum(term in sender.casefold() for term in cls.MARKETING_SENDERS)
            social_notice = any(
                term in haystack for term in cls.SOCIAL_NOTIFICATION_TERMS
            ) or any(
                term in sender.casefold()
                for term in cls.SOCIAL_NOTIFICATION_SENDERS
            )
            if social_notice:
                continue
            if not action_hits:
                continue
            if marketing_hits and action_hits < 2:
                continue
            score = min(action_hits, 3) * 3
            score += 2 if bool(message.get("important")) else 0
            score += 1 if bool(message.get("unread")) else 0
            score -= marketing_hits * 5
            score -= sender_hits
            if not subject or subject.casefold() in {"(bez tematu)", "bez tematu"}:
                score -= 2
            if score < 2:
                continue
            ranked.append((score, -index, message))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in ranked]

    @staticmethod
    def event_count(count: int) -> str:
        return IntelligentDayQuality._plural(
            count,
            "wydarzenie",
            "wydarzenia",
            "wydarzeń",
        )

    @staticmethod
    def reminder_count(count: int) -> str:
        if count == 1:
            return "1 pilne przypomnienie"
        if IntelligentDayQuality._few(count):
            return f"{count} pilne przypomnienia"
        return f"{count} pilnych przypomnień"

    @staticmethod
    def completed_count(count: int) -> str:
        return IntelligentDayQuality._plural(
            count,
            "zakończona sprawa",
            "zakończone sprawy",
            "zakończonych spraw",
        )

    @staticmethod
    def _plural(count: int, one: str, few: str, many: str) -> str:
        if count == 1:
            return f"1 {one}"
        if IntelligentDayQuality._few(count):
            return f"{count} {few}"
        return f"{count} {many}"

    @staticmethod
    def _few(count: int) -> bool:
        return count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}
