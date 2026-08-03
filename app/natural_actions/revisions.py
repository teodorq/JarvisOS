from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from app.assistant.natural_language import fold_text
from app.natural_actions.validation import clean_reference, valid_email


_DATE_HINT = re.compile(
    r"\b(?:dzis(?:iaj)?|jutro|pojutrze|poniedzialek|wtorek|srod[ae]?|"
    r"czwartek|piatek|sobot[ae]?|niedziel[ae]?|\d{4}-\d{1,2}-\d{1,2}|"
    r"\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?)\b",
    re.I,
)
_TIME_HINT = re.compile(
    r"\b(?:o|na)\s*\d{1,2}(?::\d{2})?|\b\d{1,2}:\d{2}\b|"
    r"\b(?:rano|poludnie|popoludniu|wieczorem)\b",
    re.I,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", re.I)


def _clean_correction(value: object) -> str:
    text = clean_reference(value)
    text = re.sub(
        r"^(?:(?:nie|jednak|poprawka)\s*[,;:]?\s*|"
        r"(?:zmien|zmień)\s+to\s+na\s+|"
        r"ma\s+(?:byc|być)\s+)+",
        "",
        text,
        flags=re.I,
    )
    return text.strip(" ,.;")


def rebuild_command(thought: dict[str, Any], correction: object) -> str:
    intent = str(thought.get("assistant_intent", "") or "")
    slots = dict(thought.get("natural_slots", {}) or {})
    text = _clean_correction(correction)
    if not text:
        return ""
    if intent == "calendar_create":
        return _calendar_command(slots, text)
    if intent.startswith("mail_"):
        return _mail_command(intent, slots, text)
    return ""


def _calendar_command(slots: dict[str, Any], correction: str) -> str:
    title = str(slots.get("title", "") or "").strip() or "wydarzenie"
    title_change = re.search(
        r"(?:nazwa|tytul|tytuł)\s*(?:ma\s+byc|ma\s+być|to)?\s*[:\-]?\s*(.+?)(?=\s+(?:jutro|dzis|pojutrze|o\s*\d|na\s*\d)|$)",
        correction,
        flags=re.I,
    )
    if title_change:
        title = title_change.group(1).strip(" ,.;")
        correction = correction.replace(title_change.group(0), "").strip(" ,.;")

    try:
        when = datetime.fromisoformat(str(slots.get("when", "")))
    except (TypeError, ValueError):
        when = None

    parts = [f"Dodaj {title}"]
    folded = fold_text(correction)
    if when is not None and not _DATE_HINT.search(folded):
        parts.append(when.date().isoformat())
    if when is not None and not _TIME_HINT.search(folded):
        parts.append(f"o {when:%H:%M}")

    duration = int(slots.get("duration_minutes", 60) or 60)
    if duration != 60 and not re.search(r"\b(?:na|przez)\s+", folded):
        parts.append(f"na {duration} minut")

    reminder = slots.get("reminder_minutes")
    if reminder is not None and not any(
        marker in folded for marker in ("przypomnij", "przed", "wczesniej")
    ):
        parts.append(f"i przypomnij {int(reminder)} minut wcześniej")

    if correction:
        parts.append(correction)
    return " ".join(parts)


def _mail_command(intent: str, slots: dict[str, Any], correction: str) -> str:
    recipient = str(
        slots.get("recipient_email") or slots.get("recipient_ref") or ""
    ).strip()
    email = _EMAIL.search(correction)
    if email:
        recipient = email.group(0)
    else:
        target = re.search(
            r"\b(?:do|dla)\s+(.+?)(?=\s*(?:,|:|\btemat\b|\btresc\b|\btreść\b|\bze\b|\bże\b|$))",
            correction,
            flags=re.I,
        )
        if target:
            recipient = target.group(1).strip(" ,.;")

    subject = str(slots.get("subject", "") or "").strip()
    subject_match = re.search(
        r"\b(?:temat|tytul|tytuł)\s*[:\-]?\s*(.+?)(?=\s+(?:tresc|treść|ze|że)\b|$)",
        correction,
        flags=re.I,
    )
    if subject_match:
        subject = subject_match.group(1).strip(" ,.;")

    body = str(slots.get("body", "") or "").strip()
    body_match = re.search(
        r"\b(?:tresc|treść|wiadomosc|wiadomość)\s*[:\-]?\s*(.+)$|"
        r"\b(?:ze|że)\s+(.+)$",
        correction,
        flags=re.I,
    )
    if body_match:
        body = next(
            value.strip(" ,.;") for value in body_match.groups() if value
        )
    folded = fold_text(correction)
    action_only = (
        folded.startswith(("wyslij", "podeslij", "przeslij"))
        and not any(marker in folded for marker in (" ze ", " tresc ", " wiadomosc "))
    )
    if (
        not email
        and not target
        and not subject_match
        and not action_only
    ):
        body = correction

    action = "Wyślij email" if intent == "mail_send" else "Napisz email"
    if folded.startswith(("wyslij", "podeslij", "przeslij")):
        action = "Wyślij email"
    if not recipient:
        return ""
    subject_part = f" temat {subject}" if subject else ""
    body_part = f" treść {body}" if body else ""
    return f"{action} do {recipient}{subject_part}{body_part}".strip()
