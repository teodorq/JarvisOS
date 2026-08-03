from __future__ import annotations

from datetime import datetime, time, timedelta
import re
from typing import Any

from app.assistant.natural_language import fold_text
from app.natural_actions.active_understanding import (
    ACTIVE_INTENTS, classify_active, extract_active_slots,
)
from app.natural_actions.temporal import PolishTemporalParser


ADVANCED_INTENTS = {
    "calendar_search",
    "calendar_update",
    "calendar_delete",
    "mail_send_existing",
    "day_overview",
    "day_priority",
    "day_plan_tomorrow",
    "day_history",
    "day_mark_done",
} | ACTIVE_INTENTS


def classify_advanced(text: str) -> tuple[str, float] | None:
    folded = fold_text(text)
    if not folded:
        return None
    active = classify_active(folded)
    if active is not None:
        return active
    if any(phrase in folded for phrase in (
        "co powinienem zrobic teraz", "co jest najwazniejsze",
        "czym mam sie zajac", "od czego zaczac", "co wymaga reakcji",
        "co jest teraz najwazniejsze",
    )):
        return "day_priority", 0.98
    if any(phrase in folded for phrase in (
        "uporzadkuj mi jutro", "zaplanuj mi jutro", "plan na jutro",
        "jak wyglada jutro", "uloz mi jutro",
        "zaplanuj moj jutrzejszy dzien",
    )):
        return "day_plan_tomorrow", 0.97
    if any(phrase in folded for phrase in (
        "co zrobilem dzisiaj", "co juz zrobilem", "podsumuj wykonane",
        "pokaz zakonczone", "co mam za soba",
        "co ostatnio udalo mi sie zrobic",
    )):
        return "day_history", 0.96
    if (
        re.search(r"\b(?:oznacz|zapisz)\b.+\bjako\s+(?:zrobione|wykonane|gotowe)\b", folded)
        or re.match(r"^(?:zrobilem|wykonalem|skonczylem)\b", folded)
    ):
        return "day_mark_done", 0.95
    if any(phrase in folded for phrase in (
        "co mam dzisiaj", "co mam dzis", "pokaz moj dzien",
        "pokaz moj plan na dzis", "plan na dzis", "jaki mam plan na dzis",
        "podsumuj moj dzien", "podsumuj mi dzien", "moj dzien", "centrum dnia",
    )):
        return "day_overview", 0.96
    send_existing = any(phrase in folded for phrase in (
        "wyslij te odpowiedz", "wyslij ta odpowiedz", "wyslij odpowiedz",
        "wyslij przygotowana odpowiedz", "wyslij ostatnia odpowiedz",
        "wyslij ten szkic", "wyslij przygotowany szkic", "wyslij ostatni szkic",
        "nadaj te odpowiedz", "przeslij te odpowiedz", "podeslij te odpowiedz",
        "wyslij szkic", "wyslij go", "wyslij ja", "prosze wyslij odpowiedz",
    ))
    if send_existing or ("szkic" in folded and any(
        word in folded for word in ("wyslij", "podeslij", "przeslij", "nadaj")
    )):
        return "mail_send_existing", 0.99
    if any(phrase in folded for phrase in (
        "tej samej osoby", "do tej samej osoby", "napisz ponownie",
    )):
        return "mail_draft", 0.92
    calendar_hint = any(word in folded for word in (
        "kalendar", "wydarzen", "spotkan", "trening", "silown",
        "wizyt", "lekarz", "urodzin", "zebran", "termin",
    ))
    if calendar_hint and any(
        word in folded for word in ("usun", "skasuj", "wykasuj", "odwol")
    ):
        return "calendar_delete", 0.98
    if calendar_hint and any(
        word in folded for word in ("przenies", "przesun", "zmien", "edytuj")
    ):
        return "calendar_update", 0.98
    if calendar_hint and any(
        word in folded for word in ("znajdz", "pokaz", "wyszukaj", "kiedy", "sprawdz")
    ):
        return "calendar_search", 0.92
    return None


def extract_advanced_slots(
    intent: str,
    text: str,
    temporal: PolishTemporalParser,
    existing: dict[str, Any],
) -> dict[str, Any]:
    if intent == "mail_send_existing":
        return {}
    if intent in ACTIVE_INTENTS:
        return extract_active_slots(intent, text, temporal, existing)
    if intent == "day_mark_done":
        return {"item_text": _done_text(text)}
    if intent.startswith("day_"):
        return {}
    if not intent.startswith("calendar_"):
        return {}
    slots = dict(existing)
    query = _calendar_query(text, temporal)
    if query:
        slots["event_query"] = query
    target_date = _target_date(text, temporal)
    if target_date is not None:
        slots["search_date"] = target_date.date().isoformat()
    if intent == "calendar_update":
        new_when = _update_when(text, temporal, target_date)
        if new_when is not None:
            slots["new_when"] = new_when.isoformat()
        reminder = temporal.reminder_minutes(text)
        if reminder is not None:
            slots["new_reminder_minutes"] = reminder
    return slots


def _target_date(text: str, temporal: PolishTemporalParser) -> datetime | None:
    now = temporal.now_provider().astimezone()
    folded = fold_text(text)
    if "pojutrzejsz" in folded:
        day = now.date() + timedelta(days=2)
    elif "jutrzejsz" in folded or re.search(r"\bjutra\b", folded):
        day = now.date() + timedelta(days=1)
    elif "dzisiejsz" in folded:
        day = now.date()
    else:
        parsed = temporal.parse_date(text, today=now.date())
        if parsed is None:
            return None
        day = parsed
    return datetime.combine(day, time.min, tzinfo=now.tzinfo)


def _update_when(
    text: str,
    temporal: PolishTemporalParser,
    target_date: datetime | None,
) -> datetime | None:
    parsed_time = temporal.parse_time(text)
    if parsed_time is None:
        return None
    now = temporal.now_provider().astimezone()
    day = target_date.date() if target_date is not None else now.date()
    value = datetime.combine(day, parsed_time, tzinfo=now.tzinfo)
    if target_date is None and value <= now:
        value += timedelta(days=1)
    return value


def _calendar_query(text: str, temporal: PolishTemporalParser) -> str:
    candidate = temporal.strip_temporal(text)
    candidate = re.sub(
        r"\b(?:dzisiejsz\w*|jutrzejsz\w*|pojutrzejsz\w*|jutra)\b",
        " ",
        candidate,
        flags=re.I,
    )
    candidate = re.sub(
        r"^(?:prosz[eę]\s+)?(?:znajd[zź]|poka[zż]|wyszukaj|sprawd[zź]|kiedy\s+mam|"
        r"usu[nń]|skasuj|wykasuj|odwo[lł]aj|przenie[sś]|przesu[nń]|zmie[nń]|edytuj)\s+",
        "",
        candidate,
        flags=re.I,
    )
    candidate = re.sub(r"\b(?:w|z)\s+kalendarz(?:u|a)\b", " ", candidate, flags=re.I)
    candidate = re.sub(r"\b(?:wydarzenie|termin)\b", " ", candidate, flags=re.I)
    candidate = re.sub(r"\b(?:na|o)\s*$", "", candidate, flags=re.I)
    candidate = re.sub(r"\b(?:ten|to|tego)\b", " ", candidate, flags=re.I)
    return " ".join(candidate.split()).strip(" ,.-?!")[:240]


def _done_text(text: str) -> str:
    candidate = re.sub(
        r"^(?:prosz[eę]\s+)?(?:oznacz|zapisz)\s+(?:to\s+)?",
        "",
        text,
        flags=re.I,
    )
    candidate = re.sub(
        r"^(?:zrobi[lł]em|wykona[lł]em|sko[nń]czy[lł]em)\s+",
        "",
        candidate,
        flags=re.I,
    )
    candidate = re.sub(
        r"\s+jako\s+(?:zrobione|wykonane|gotowe)\b.*$",
        "",
        candidate,
        flags=re.I,
    )
    return " ".join(candidate.split()).strip(" ,.-?!")[:300]
