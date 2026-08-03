from __future__ import annotations

from datetime import timedelta
import re
from typing import Any

from app.assistant.natural_language import fold_text
from app.natural_actions.temporal import PolishTemporalParser


ACTIVE_INTENTS = {
    "active_conflict_advice", "active_conflict_move",
    "active_apply_suggestion", "active_mail_reply",
    "active_snooze", "active_ignore", "active_mark_done",
    "active_undo_calendar",
}


def classify_active(text: str) -> tuple[str, float] | None:
    folded = " ".join(re.findall(r"[a-z0-9]+", fold_text(text)))
    if folded in {
        "cofnij to", "cofnij ostatnia zmiane",
        "cofnij ostatnia zmiane kalendarza", "przywroc poprzedni termin",
        "przywroc poprzednia godzine",
    }:
        return "active_undo_calendar", 0.99
    if any(phrase in folded for phrase in (
        "co mam zrobic z tym konfliktem", "jak rozwiazac ten konflikt",
        "co z tym konfliktem", "zaproponuj rozwiazanie konfliktu",
    )):
        return "active_conflict_advice", 0.99
    if folded in {
        "zrob to", "wykonaj to", "zastosuj propozycje",
        "wykonaj propozycje", "tak zrob",
    }:
        return "active_apply_suggestion", 0.98
    if (
        any(word in folded for word in ("przenies", "przesun", "zmien"))
        and any(phrase in folded for phrase in (
            "pierwsze spotkanie", "pierwszy termin",
            "drugie spotkanie", "drugi termin", "z konfliktu",
        ))
    ):
        return "active_conflict_move", 0.99
    if any(phrase in folded for phrase in (
        "odpisz na te wiadomosc", "odpisz na ten mail",
        "przygotuj odpowiedz na te wiadomosc",
        "przygotuj odpowiedz na ten mail", "odpowiedz na to",
    )):
        return "active_mail_reply", 0.99
    if any(phrase in folded for phrase in (
        "przypomnij pozniej", "przypomnij mi o tym pozniej",
        "wroc do tego za", "odloz to na", "przypomnij o tym za",
    )):
        return "active_snooze", 0.98
    if folded in {"pomin", "pomin to", "zignoruj", "zignoruj to"} or (
        "nie pokazuj" in folded and "tego" in folded
    ):
        return "active_ignore", 0.98
    if any(phrase in folded for phrase in (
        "oznacz to jako zrobione", "oznacz alert jako zrobiony",
        "ta sprawa zalatwiona", "to juz zalatwione",
    )):
        return "active_mark_done", 0.98
    return None


def extract_active_slots(
    intent: str,
    text: str,
    temporal: PolishTemporalParser,
    existing: dict[str, Any],
) -> dict[str, Any]:
    if intent == "active_conflict_move":
        slots = dict(existing)
        folded = fold_text(text)
        slots["event_selector"] = (
            "first" if any(word in folded for word in ("pierwsze", "pierwszy"))
            else "second"
        )
        new_when = _update_when(text, temporal)
        if new_when is not None:
            slots["new_when"] = new_when.isoformat()
        return slots
    if intent == "active_mail_reply":
        body = _reply_body(text)
        return {"body": body} if body else dict(existing)
    if intent == "active_snooze":
        return {"snooze_minutes": _snooze_minutes(text, temporal)}
    return dict(existing)


def _update_when(text: str, temporal: PolishTemporalParser):
    parsed_time = temporal.parse_time(text)
    if parsed_time is None:
        return None
    now = temporal.now_provider().astimezone()
    value = now.replace(
        hour=parsed_time.hour, minute=parsed_time.minute,
        second=0, microsecond=0,
    )
    return value if value > now else value + timedelta(days=1)


def _reply_body(text: str) -> str:
    match = re.search(
        r"\b(?:ze|że|tresc|treść)\s*[:,-]?\s*(.+)$",
        text, flags=re.I,
    )
    return " ".join(match.group(1).split()).strip(" ,.-")[:2000] if match else ""


def _snooze_minutes(text: str, temporal: PolishTemporalParser) -> int:
    folded = fold_text(text)
    match = re.search(
        r"\bza\s+(\d{1,4})\s*(min|minut\w*|godz\w*|dni?)\b",
        folded,
    )
    if match:
        value, unit = int(match.group(1)), match.group(2)
        factor = 60 if unit.startswith("godz") else 1440 if unit.startswith("dni") else 1
        return max(5, min(value * factor, 10080))
    if re.search(r"\bza\s+(?:godzine|godzinę)\b", text, re.I):
        return 60
    if re.search(r"\bza\s+(?:pol|pół)\s+godziny\b", text, re.I):
        return 30
    return temporal.duration_minutes(text, default=60)
