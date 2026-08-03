from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Any

from app.assistant.natural_language import fold_text, normalize_user_command
from app.assistant_v12.context_hub import UnifiedContextHub


_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_TIME = re.compile(r"\b(?:o\s*)?([01]?\d|2[0-3])(?:[:.]([0-5]\d))?\b")
_RELATIVE = re.compile(
    r"\bza\s+(\d{1,4})\s*(minut(?:y|ę)?|min|godzin(?:y|ę)?|godz|dni|dzień)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ParsedRequest:
    original: str
    command: str
    intent: str
    slots: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    clarification: str = ""
    used_context: bool = False
    read_only: bool = True


class NaturalConversationEngineV3:
    """B121 Polish natural conversation with bounded, deterministic follow-ups."""

    READ_ONLY = {
        "suite_status", "context_status", "progress_status", "day_overview",
        "mail_status", "calendar_status", "calendar_conflicts",
        "document_search", "reminder_status", "beta_status",
    }

    def __init__(self, context: UnifiedContextHub) -> None:
        self.context = context

    @staticmethod
    def matches(command: object) -> bool:
        text = fold_text(normalize_user_command(command))
        phrases = (
            "status b121", "status b122", "status b123", "status b124",
            "status b125", "status asystenta 1.2", "assistant 1.2",
            "asystent 1.2", "kontekst 1.2", "postep asystenta",
            "co mam dzisiaj", "pokaz moj dzien", "podsumuj moj dzien",
            "napisz mail", "utworz mail", "szkic mail", "status poczty",
            "dodaj spotkanie", "zaplanuj spotkanie", "status kalendarza",
            "konflikty kalendarza", "znajdz dokument", "poszukaj dokument",
            "skanuj dokumenty", "przypomnij mi", "dodaj przypomnienie",
            "status przypomnien", "generuj raport dnia",
            "audyt business 1.2", "potwierdz business 1.2",
            "business 1.2 beta", "wyczysc kontekst 1.2",
        )
        return any(phrase in text for phrase in phrases)

    def parse(
        self,
        command: object,
        *,
        source: str = "TEXT",
        mutate_context: bool = True,
    ) -> ParsedRequest:
        original = str(command).strip()
        cleaned = normalize_user_command(original)
        folded = fold_text(cleaned)
        data = self.context.load()
        pending = dict(data.get("pending", {}) or {})

        if pending and self._looks_like_follow_up(cleaned):
            intent = str(pending.get("intent", ""))
            slots = dict(pending.get("slots", {}) or {})
            slots.update(self._extract_slots(cleaned, intent))
            request = ParsedRequest(
                original=original,
                command=cleaned,
                intent=intent,
                slots=slots,
                used_context=True,
                read_only=intent in self.READ_ONLY,
            )
            self._complete_requirements(request, mutate_context=mutate_context)
            return request

        intent = self._classify(folded)
        slots = self._extract_slots(cleaned, intent)
        request = ParsedRequest(
            original=original,
            command=cleaned,
            intent=intent,
            slots=slots,
            read_only=intent in self.READ_ONLY,
        )
        self._complete_requirements(request, mutate_context=mutate_context)
        return request

    def _classify(self, folded: str) -> str:
        if "wyczysc kontekst 1.2" in folded:
            return "context_clear"
        if any(item in folded for item in ("status b121", "status b122", "status b123", "status b124", "status asystenta 1.2", "assistant 1.2", "asystent 1.2")):
            return "suite_status"
        if "kontekst 1.2" in folded:
            return "context_status"
        if "postep asystenta" in folded or "status postepu" in folded:
            return "progress_status"
        if any(item in folded for item in ("co mam dzisiaj", "pokaz moj dzien", "podsumuj moj dzien", "moj dzien")):
            return "day_overview"
        if any(item in folded for item in ("napisz mail", "utworz mail", "szkic mail", "przygotuj mail")):
            return "mail_create"
        if "status poczty" in folded:
            return "mail_status"
        if any(item in folded for item in ("dodaj spotkanie", "zaplanuj spotkanie", "umow spotkanie", "wpisz do kalendarza")):
            return "calendar_add"
        if "konflikty kalendarza" in folded:
            return "calendar_conflicts"
        if "status kalendarza" in folded:
            return "calendar_status"
        if any(item in folded for item in ("znajdz dokument", "poszukaj dokument", "wyszukaj dokument")):
            return "document_search"
        if "skanuj dokumenty" in folded:
            return "document_scan"
        if any(item in folded for item in ("przypomnij mi", "dodaj przypomnienie", "ustaw przypomnienie")):
            return "reminder_add"
        if "status przypomnien" in folded:
            return "reminder_status"
        if any(item in folded for item in ("generuj raport dnia", "eksportuj raport dnia", "raport na jutro")):
            return "report_export"
        if "audyt business 1.2" in folded:
            return "beta_audit"
        if "potwierdz business 1.2" in folded:
            return "beta_confirm"
        if "business 1.2 beta" in folded or "status b125" in folded:
            return "beta_status"
        return "standard"

    def _extract_slots(self, command: str, intent: str) -> dict[str, Any]:
        slots: dict[str, Any] = {}
        email = _EMAIL.search(command)
        if email:
            slots["recipient"] = email.group(0)

        when = self._parse_datetime(command)
        if when is not None:
            slots["when"] = when.isoformat()

        if intent == "mail_create":
            subject = self._capture(command, r"(?:temat|tytuł|tytul)\s*[:\-]?\s*(.+?)(?=\s+(?:treść|tresc)\s*[:\-]|$)")
            body = self._capture(command, r"(?:treść|tresc)\s*[:\-]?\s*(.+)$")
            if subject:
                slots["subject"] = subject
            if body:
                slots["body"] = body
        elif intent == "calendar_add":
            title = re.sub(
                r"^(?:dodaj|zaplanuj|umów|umow|wpisz)\s+(?:spotkanie\s+|do\s+kalendarza\s+)?",
                "",
                command,
                flags=re.IGNORECASE,
            )
            title = re.sub(r"\b(?:dzisiaj|jutro|pojutrze|za\s+\d+\s+\w+|o\s+\d{1,2}(?::\d{2})?)\b.*$", "", title, flags=re.IGNORECASE).strip(" ,.-")
            if title:
                slots["title"] = title[:180]
        elif intent == "document_search":
            query = re.sub(
                r"^(?:znajdź|znajdz|poszukaj|wyszukaj)\s+(?:dokument(?:u|y)?\s*)?",
                "",
                command,
                flags=re.IGNORECASE,
            ).strip(" :,-")
            if query:
                slots["query"] = query[:300]
        elif intent == "reminder_add":
            text = re.sub(
                r"^(?:przypomnij\s+mi|dodaj\s+przypomnienie|ustaw\s+przypomnienie)\s*",
                "",
                command,
                flags=re.IGNORECASE,
            )
            text = re.sub(r"\b(?:dzisiaj|jutro|pojutrze|za\s+\d+\s+\w+|o\s+\d{1,2}(?::\d{2})?)\b.*$", "", text, flags=re.IGNORECASE).strip(" ,.-")
            if text:
                slots["text"] = text[:400]
        return slots

    def _complete_requirements(
        self,
        request: ParsedRequest,
        *,
        mutate_context: bool,
    ) -> None:
        required = {
            "mail_create": ("recipient",),
            "calendar_add": ("title", "when"),
            "document_search": ("query",),
            "reminder_add": ("text", "when"),
        }.get(request.intent, ())
        request.missing = [name for name in required if not request.slots.get(name)]
        if not request.missing:
            if mutate_context:
                self.context.clear_pending()
            return
        prompts = {
            "recipient": "Podaj adres e-mail odbiorcy.",
            "title": "Jak nazywa się spotkanie?",
            "when": "Podaj termin, na przykład „jutro o 9:00” albo „za 30 minut”.",
            "query": "Jakiego dokumentu mam szukać?",
            "text": "Co mam Ci przypomnieć?",
        }
        request.clarification = " ".join(prompts[name] for name in request.missing)
        if mutate_context:
            self.context.set_pending(
                intent=request.intent,
                missing=request.missing,
                slots=request.slots,
                prompt=request.clarification,
            )

    @staticmethod
    def _looks_like_follow_up(text: str) -> bool:
        folded = fold_text(text)
        return (
            len(text.split()) <= 12
            or bool(_EMAIL.search(text))
            or any(token in folded for token in ("jutro", "dzisiaj", "pojutrze", "za ", "o "))
        )

    @staticmethod
    def _capture(text: str, pattern: str) -> str:
        match = re.search(pattern, text, re.IGNORECASE)
        return " ".join(match.group(1).split())[:1000] if match else ""

    @staticmethod
    def _parse_datetime(text: str) -> datetime | None:
        now = datetime.now().astimezone()
        relative = _RELATIVE.search(text)
        if relative:
            amount = int(relative.group(1))
            unit = fold_text(relative.group(2))
            if unit.startswith("min"):
                return now + timedelta(minutes=amount)
            if unit.startswith("godz"):
                return now + timedelta(hours=amount)
            return now + timedelta(days=amount)

        folded = fold_text(text)
        day = None
        if "pojutrze" in folded:
            day = now.date() + timedelta(days=2)
        elif "jutro" in folded:
            day = now.date() + timedelta(days=1)
        elif "dzisiaj" in folded:
            day = now.date()

        time_match = _TIME.search(text)
        if day is None and time_match is None:
            return None
        if day is None:
            day = now.date()
        hour = int(time_match.group(1)) if time_match else 9
        minute = int(time_match.group(2) or 0) if time_match else 0
        result = datetime(day.year, day.month, day.day, hour, minute, tzinfo=now.tzinfo)
        if result < now and "dzisiaj" not in folded and "jutro" not in folded and "pojutrze" not in folded:
            result += timedelta(days=1)
        return result
