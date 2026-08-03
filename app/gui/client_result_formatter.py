from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ClientResultCard:
    kind: str
    title: str
    summary: str
    body: str
    spoken: str


class ClientResultFormatter:
    """Turn assistant output into a compact, non-technical client card."""

    INTENT_KINDS = {
        "gmail_latest": "mail",
        "gmail_priority": "mail",
        "gmail_search": "mail",
        "gmail_read": "mail",
        "gmail_thread": "mail",
        "calendar_today": "calendar",
        "calendar_conflicts": "calendar",
        "calendar_status": "calendar",
        "calendar_today_overview": "calendar",
        "calendar_week_overview": "calendar",
        "drive_search": "documents",
        "drive_summarize": "documents",
        "document_search": "documents",
        "document_status": "documents",
        "documents_recent": "documents",
        "reminder_status": "reminders",
        "reminders_overview": "reminders",
        "day_overview": "day",
        "day_review": "day",
        "day_business_summary": "day",
        "bills_overview": "finances",
        "advertising_overview": "advertising",
        "trading_overview": "trading",
        "report_review": "day",
    }
    TITLES = {
        "mail": "POCZTA",
        "calendar": "KALENDARZ",
        "documents": "DOKUMENTY",
        "reminders": "PRZYPOMNIENIA",
        "day": "MÓJ DZIEŃ",
        "finances": "RACHUNKI",
        "advertising": "REKLAMY",
        "trading": "TRADING",
        "warning": "POTRZEBUJĘ DECYZJI",
        "error": "WYMAGANA UWAGA",
        "general": "JARVIS",
    }

    @classmethod
    def kind_for_intent(cls, intent: object) -> str:
        return cls.INTENT_KINDS.get(str(intent or "").casefold(), "")

    @classmethod
    def for_outcome(cls, outcome: object, state: str) -> ClientResultCard:
        thought = dict(getattr(outcome, "thought", {}) or {})
        intent = thought.get("assistant_intent") or thought.get("intent")
        result_type = (
            cls.kind_for_intent(intent) if state == "success" else "error"
        )
        return cls.format(
            getattr(outcome, "message", ""), state=state,
            result_type=result_type,
        )

    @classmethod
    def format(
        cls,
        message: object,
        *,
        state: object = "success",
        result_type: object = "",
    ) -> ClientResultCard:
        text = cls._clean(message)
        state_name = str(state or "success").casefold()
        kind = str(result_type or "").casefold()
        if state_name == "error":
            kind = "error"
        elif state_name in {"warning", "important"}:
            kind = "warning"
        elif kind not in cls.TITLES:
            kind = cls._infer_kind(text)
        lines = cls._readable_lines(text)
        if cls._has_list_header(kind, lines):
            lines = lines[1:]
        body = "\n".join(lines).strip() or "Zadanie zostało zakończone."
        summary = cls._summary(kind, lines, body)
        spoken = cls._spoken(kind, summary, body)
        return ClientResultCard(
            kind=kind,
            title=cls.TITLES.get(kind, cls.TITLES["general"]),
            summary=summary,
            body=body,
            spoken=spoken,
        )

    @staticmethod
    def _clean(message: object) -> str:
        value = str(message or "").replace("\r\n", "\n").replace("\r", "\n")
        cleaned: list[str] = []
        for raw in value.splitlines():
            line = " ".join(raw.split()).strip()
            line = re.sub(
                r"^B\d{2,3}(?:\.\d+)?(?:\s*[–—-]\s*B?\d{2,3})?"
                r"(?:\s*[:•-]\s*|\s+)",
                "",
                line,
                flags=re.I,
            ).strip()
            if line:
                cleaned.append(line)
        return "\n".join(cleaned)

    @staticmethod
    def _infer_kind(text: str) -> str:
        lower = text.casefold()
        markers = (
            ("mail", ("gmail", "wiadomoś", "e-mail", "poczta", "nadawca")),
            ("calendar", ("kalendar", "wydarzeni", "spotkani", "termin")),
            ("documents", ("dokument", "dysk google", "drive", "plik")),
            ("reminders", ("przypomn",)),
            ("finances", ("rachun", "faktur", "abonament", "do zapłaty")),
            ("advertising", ("reklam", "kampani")),
            ("trading", ("trading", "transakcj", "pnl")),
            ("day", ("mój dzień", "plan na dziś", "brief dnia", "produktywnoś")),
        )
        for kind, words in markers:
            if any(word in lower for word in words):
                return kind
        return "general"

    @staticmethod
    def _readable_lines(text: str) -> list[str]:
        if not text:
            return []
        lines = [line for line in text.splitlines() if line]
        if len(lines) == 1:
            parts = re.split(r"\s+(?=(?:[1-9]|1[0-2])\.\s+)", lines[0])
            if len(parts) > 1:
                lines = [part.strip() for part in parts if part.strip()]
        return lines[:14]

    @staticmethod
    def _has_list_header(kind: str, lines: list[str]) -> bool:
        if kind not in {"mail", "calendar", "documents", "reminders"}:
            return False
        if len(lines) < 2 or re.match(r"^\d{1,2}\.\s", lines[0]):
            return False
        return any(re.match(r"^\d{1,2}\.\s", line) for line in lines[1:])

    @classmethod
    def _summary(cls, kind: str, lines: list[str], body: str) -> str:
        numbered = sum(
            bool(re.match(r"^\d{1,2}\.\s", line)) for line in lines
        )
        forms = {
            "mail": ("Znalazłem", "jedną wiadomość", "wiadomości", "wiadomości"),
            "calendar": ("Masz", "jedno wydarzenie", "wydarzenia", "wydarzeń"),
            "documents": ("Znalazłem", "jeden dokument", "dokumenty", "dokumentów"),
            "reminders": (
                "Masz", "jedno przypomnienie", "przypomnienia", "przypomnień"
            ),
        }
        if numbered and kind in forms:
            return cls._count(numbered, *forms[kind])
        first = lines[0] if lines else body
        if len(first) <= 170:
            return first
        return first[:167].rstrip(" ,;:-") + "…"

    @staticmethod
    def _count(
        number: int,
        opening: str,
        one: str,
        few: str,
        many: str,
    ) -> str:
        if number == 1:
            return f"{opening} {one}."
        takes_few = number % 10 in {2, 3, 4} and number % 100 not in {12, 13, 14}
        return f"{opening} {number} {few if takes_few else many}."

    @staticmethod
    def _spoken(kind: str, summary: str, body: str) -> str:
        if kind == "day":
            return body
        detailed = {"mail", "calendar", "documents", "reminders", "finances", "advertising", "trading"}
        if kind in detailed and body != summary:
            return f"{summary} Szczegóły wyświetliłem na ekranie."
        return summary
