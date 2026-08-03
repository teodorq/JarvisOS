from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.user_text import naturalize_user_text


@dataclass(frozen=True)
class DirectedSpeech:
    text: str
    profile: str


class PolishSpeechDirector:
    """Prepare concise, natural Polish text and a restrained delivery profile."""

    PROFILE_MARKERS = (
        ("warning", ("uwaga", "błąd", "nie udało", "nie mogę", "ostrzeż")),
        ("confirmation", ("potwierd", "czy mam", "zgadzasz", "wykonać")),
        ("result", ("gotow", "zakończ", "znalazłem", "utworzyłem", "masz ")),
        ("brief", ("brief", "mój dzień", "dzisiaj", "najważniejsze")),
    )
    STATUS_WORDS = {
        "COMPLETED": "zakończone",
        "READY": "gotowe",
        "PENDING": "oczekuje",
        "FAILED": "niepowodzenie",
        "BRAK": "brak",
        "TAK": "tak",
        "NIE": "nie",
    }

    def direct(self, value: object) -> DirectedSpeech:
        text = self._normalize(value)
        return DirectedSpeech(text=text, profile=self._profile(text))

    @classmethod
    def _normalize(cls, value: object) -> str:
        text = naturalize_user_text(
            value, maximum=2000, preserve_lines=True
        )
        text = re.sub(r"https?://\S+", "link", text, flags=re.I)
        text = re.sub(r"[A-Za-z]:\\[^\s,;]+", "lokalny plik", text)
        text = re.sub(r"\b[0-9a-f]{16,64}\b", "", text, flags=re.I)
        text = re.sub(r"(?:^|\n)\s*\d{1,2}\.\s*", "; ", text)
        text = text.replace("\n", "; ")
        for technical, natural in cls.STATUS_WORDS.items():
            text = re.sub(rf"\b{technical}\b", natural, text)
        text = re.sub(r"\b(?:Faza|Postęp|Status techniczny)\s*:\s*", "", text)
        text = re.sub(r"\s*;\s*", "; ", text)
        text = re.sub(r"\s+", " ", text).strip(" ;")
        return cls._bounded(text)

    @staticmethod
    def _bounded(text: str, maximum: int = 520) -> str:
        if len(text) <= maximum:
            return text
        candidate = text[:maximum]
        boundary = max(candidate.rfind("."), candidate.rfind(";"))
        if boundary >= 180:
            candidate = candidate[:boundary + 1]
        else:
            candidate = candidate[:maximum - 1].rstrip(" ,;:-") + "…"
        return candidate

    @classmethod
    def _profile(cls, text: str) -> str:
        lower = text.casefold()
        for profile, markers in cls.PROFILE_MARKERS:
            if any(marker in lower for marker in markers):
                return profile
        if text.rstrip().endswith("?"):
            return "confirmation"
        return "calm"
