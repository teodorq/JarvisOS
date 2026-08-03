from __future__ import annotations

import re
from typing import Any

from app.assistant.natural_language import fold_text, normalize_user_command
from app.natural_actions.advanced_understanding import (
    ADVANCED_INTENTS, classify_advanced, extract_advanced_slots,
)
from app.natural_actions.business_day_understanding import (
    classify_business_day,
)
from app.natural_actions.gmail_live_understanding import (
    GMAIL_LIVE_INTENTS, classify_gmail_live, extract_gmail_live_slots,
)
from app.natural_actions.models import NaturalActionRequest
from app.natural_actions.temporal import PolishTemporalParser


_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_SEND_ACTIONS = {"wyslij", "podeslij", "przeslij", "nadaj"}
_CALENDAR_WORDS = {
    "kalendarz", "termin", "wydarzenie", "spotkanie", "trening", "silownia",
    "wizyta", "lekarz", "urodziny", "rozmowa", "zebranie", "rezerwacja",
}
_CANCEL = {"anuluj", "niewazne", "odwolaj", "zapomnij", "stop"}
_RECIPIENT_PRONOUNS = {
    "mu", "jej", "im", "jemu", "do niego", "do niej", "do nich",
}


class NaturalActionUnderstanding:
    """Intent and slot extraction based on meaning signals, not exact commands."""

    def __init__(self, temporal: PolishTemporalParser | None = None) -> None:
        self.temporal = temporal or PolishTemporalParser()

    @staticmethod
    def classify(command: object) -> tuple[str, float]:
        text = fold_text(normalize_user_command(command))
        if not text:
            return "standard", 0.0
        business_day = classify_business_day(text)
        if business_day is not None:
            return business_day
        advanced = classify_advanced(text)
        if advanced is not None:
            return advanced
        gmail_live = classify_gmail_live(text)
        if gmail_live is not None:
            return gmail_live
        tokens = set(re.findall(r"[\w@.+-]+", text))
        hit = lambda stems: sum(
            any(token.startswith(stem) for stem in stems) for token in tokens
        )
        mail_domain = hit(("mail", "email", "e-mail", "wiadom", "poczt", "list"))
        mail_action = hit((
            "napisz", "przygot", "utworz", "stworz", "wyslij", "podeslij",
            "przeslij", "skrobnij", "odpisz", "zredag",
        ))
        calendar_domain = hit((
            "kalendar", "termin", "wydarz", "spotkan", "trening", "silown",
            "wizyt", "lekarz", "urodzin", "rozmow", "zebran", "rezerw",
        ))
        calendar_action = hit((
            "dodaj", "wpisz", "zaplan", "ustaw", "umow", "zaklep",
            "zarezerw", "zanot", "wrzuc", "dopisz",
        ))
        has_time = bool(re.search(
            r"\b(?:dzis|jutro|pojutrze|za\s+\d+|o\s*\d{1,2}|"
            r"\d{1,2}:\d{2}|rano|poludnie|popoludniu|wieczorem|"
            r"poniedzial|wtorek|srod|czwartek|piatek|sobot|niedziel|"
            r"pierwszej|drugiej|trzeciej|czwartej|piatej|szostej|"
            r"siodmej|osmej|dziewiatej|dziesiatej|jedenastej|"
            r"dwunastej|trzynastej|czternastej|pietnastej|"
            r"szesnastej|siedemnastej|osiemnastej|dziewietnastej)",
            text,
        ))
        mail_score = mail_domain * 0.45 + mail_action * 0.35
        if re.search(r"\b(?:do|dla)\s+\S+.*\b(?:ze|tresc|wiadomosc)\b", text):
            mail_score += 0.35
        if re.search(
            r"\b(?:napisz|przygotuj|wyslij|podeslij|przeslij|skrobnij|odpisz)\s+"
            r"(?:mu|jej|im|jemu)\b.*\b(?:ze|tresc|wiadomosc)\b",
            text,
        ):
            mail_score += 0.55
        direct_recipient = re.search(
            r"\b(?:napisz|przygotuj|wyslij|podeslij|przeslij|skrobnij|odpisz)\s+"
            r"[a-z0-9_.+-]+(?:owi|emu|ej|ce|i)\b.*\b(?:ze|tresc|wiadomosc|mail)\b",
            text,
        )
        if direct_recipient:
            mail_score += 0.45
        calendar_score = (
            calendar_domain * 0.35
            + calendar_action * 0.35
            + (0.3 if has_time else 0.0)
        )
        if "mam" in tokens and calendar_domain and has_time:
            calendar_score += 0.15
        if "przypomnij" in text and any(word in text for word in _CALENDAR_WORDS):
            calendar_score += 0.35
        if mail_score >= 0.7 and mail_score >= calendar_score:
            return (
                "mail_send" if tokens & _SEND_ACTIONS else "mail_draft",
                min(mail_score, 1.0),
            )
        if calendar_score >= 0.7:
            return "calendar_create", min(calendar_score, 1.0)
        return "standard", max(mail_score, calendar_score)

    def parse(
        self,
        command: object,
        *,
        pending: dict[str, Any] | None = None,
    ) -> NaturalActionRequest:
        original = str(command).strip()
        cleaned = normalize_user_command(original)
        folded = fold_text(cleaned)
        if folded in _CANCEL:
            return NaturalActionRequest(original, cleaned, "cancel", 1.0)
        used_context = bool(pending)
        fresh_intent, fresh_confidence = self.classify(cleaned)
        pending_intent = str((pending or {}).get("intent", "standard"))
        starts_new_action = bool(
            pending
            and fresh_intent != "standard"
            and fresh_confidence >= 0.7
            and fresh_intent != pending_intent
        )
        if pending and not starts_new_action:
            intent = pending_intent
            slots = dict(pending.get("slots", {}) or {})
            confidence = 1.0
        else:
            intent, confidence = fresh_intent, fresh_confidence
            slots = {}
            used_context = False
        if intent in GMAIL_LIVE_INTENTS:
            slots.update(extract_gmail_live_slots(intent, cleaned, slots))
        elif intent.startswith("mail_"):
            slots.update(self._mail_slots(cleaned, slots))
        elif intent == "calendar_create":
            slots.update(self._calendar_slots(cleaned, slots))
        elif intent in ADVANCED_INTENTS:
            slots.update(extract_advanced_slots(intent, cleaned, self.temporal, slots))
        return NaturalActionRequest(
            original=original,
            command=cleaned,
            intent=intent,
            confidence=confidence,
            slots=slots,
            used_context=used_context,
            read_only=intent in {"standard", "cancel"},
        )

    def _mail_slots(self, text: str, existing: dict[str, Any]) -> dict[str, Any]:
        slots: dict[str, Any] = {}
        email = _EMAIL.search(text)
        if email:
            slots["recipient_email"] = email.group(0)
            if not existing.get("recipient_ref"):
                slots["recipient_ref"] = email.group(0)
        recipient = self._capture(
            text,
            r"\b(?:do|dla)\s+(.+?)(?=\s*(?:,|:|\btemat\b|\btytu[lł]\b|"
            r"\btre[sś][cć]\b|\bo\s+tre[sś]ci\b|\bwiadomo[sś][cć]\b|"
            r"\b(?:z|o)\s+wiadomo[sś]ci[aą]\b|\b(?:że|ze)\b|$))",
        )
        if not recipient:
            recipient = self._capture(
                text,
                r"\b(?:napisz|przygotuj|wys[lł]ij|pode[sś]lij|prze[sś]lij|"
                r"skrobnij|odpisz)\s+(?:maila?\s+|e-?maila?\s+|"
                r"wiadomo[sś][cć]\s+)?(?:do\s+|dla\s+)?(.+?)"
                r"(?=\s+(?:maila?|e-?maila?|wiadomo[sś][cć])\s*(?:,|:|"
                r"\b(?:że|ze)\b)|\s*(?:,|:|\b(?:że|ze)\b|"
                r"\btre[sś][cć]\b|$))",
            )
        if recipient and not email and not _EMAIL.fullmatch(recipient):
            slots["recipient_ref"] = recipient
        pronoun = next(
            (value for value in _RECIPIENT_PRONOUNS if re.search(
                rf"\b{re.escape(value)}\b", fold_text(text)
            )),
            "",
        )
        if pronoun and not slots.get("recipient_ref"):
            slots["recipient_ref"] = pronoun
        subject = self._capture(
            text,
            r"\b(?:temat|tytu[lł])\s*[:\-]?\s*(.+?)(?=\s+(?:"
            r"tre[sś][cć]|o\s+tre[sś]ci|wiadomo[sś][cć])\b|$)",
        )
        if subject:
            slots["subject"] = subject
        for pattern in (
            r"\b(?:o\s+takiej\s+tre[sś]ci|o\s+tre[sś]ci|tre[sś][cć])"
            r"\s*[:\-]?\s*[„\"']?(.+?)[”\"']?$",
            r"\b(?:z|o)\s+wiadomo[sś]ci[aą]\s*[:\-]?\s*[„\"']?"
            r"(.+?)[”\"']?$",
            r"\b(?:że|ze)\s+(.+)$",
        ):
            body = self._capture(text, pattern)
            if body:
                slots["body"] = body
                break
        pending_body = str(existing.get("body", "")).strip()
        if not slots.get("body") and pending_body:
            slots["body"] = pending_body
        return slots

    def _calendar_slots(self, text: str, existing: dict[str, Any]) -> dict[str, Any]:
        slots: dict[str, Any] = {}
        when = self.temporal.parse_when(text)
        if when is not None:
            slots["when"] = when.isoformat()
        else:
            target_date = self.temporal.parse_date(text)
            if target_date is not None:
                slots["date_only"] = target_date.isoformat()
        reminder = self.temporal.reminder_minutes(text)
        if reminder is not None:
            slots["reminder_minutes"] = reminder
        slots["duration_minutes"] = self.temporal.duration_minutes(
            text,
            default=int(existing.get("duration_minutes", 60) or 60),
        )
        title = self._calendar_title(text)
        if title:
            slots["title"] = title
        return slots

    def _calendar_title(self, text: str) -> str:
        candidate = self.temporal.strip_temporal(text)
        for pattern in (
            r"^(?:dodaj|wpisz|zaplanuj|ustaw|umów|umow|zaklep|zarezerwuj|"
            r"zanotuj|wrzuć|wrzuc|dopisz)\s+(?:mi\s+)?"
            r"(?:do\s+kalendarza\s+)?(?:że\s+mam\s+|ze\s+mam\s+|mam\s+)?",
            r"^(?:do\s+kalendarza\s+)(?:że\s+mam\s+|ze\s+mam\s+|mam\s+)?",
            r"^mam\s+",
        ):
            candidate = re.sub(pattern, "", candidate, flags=re.I)
        candidate = re.sub(
            r"[, ]*(?:wrzuć|wrzuc|dodaj|wpisz)\s+(?:to\s+)?"
            r"do\s+kalendarza\b.*$",
            "",
            candidate,
            flags=re.I,
        )
        candidate = re.sub(r"\b(?:i\s+)?przypomnij\b.*$", "", candidate, flags=re.I)
        return " ".join(candidate.split()).strip(" ,.-").removesuffix(" na").strip()[:240]

    @staticmethod
    def _capture(text: str, pattern: str) -> str:
        match = re.search(pattern, text, flags=re.I)
        return (
            " ".join(match.group(1).split()).strip(" ,.;:'\"„”")[:2000]
            if match else ""
        )
