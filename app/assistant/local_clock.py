from __future__ import annotations

from datetime import datetime

from app.assistant.natural_language import fold_text


_WEEKDAYS = (
    "poniedziałek",
    "wtorek",
    "środa",
    "czwartek",
    "piątek",
    "sobota",
    "niedziela",
)
_MONTHS = (
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
)
_DATE_MARKERS = (
    "data",
    "date",
    "dzien tygodnia",
    "dzis dzien",
    "dzisiaj dzien",
    "dzisiejszy dzien",
)
_TIME_MARKERS = ("godzin", "czas")


def format_local_clock(command: object, *, now: datetime | None = None) -> str:
    """Return a natural Polish local time/date response without network use."""
    current = now or datetime.now()
    text = fold_text(command)
    asks_date = any(marker in text for marker in _DATE_MARKERS)
    asks_time = any(marker in text for marker in _TIME_MARKERS)
    date_text = (
        f"{_WEEKDAYS[current.weekday()]}, {current.day} "
        f"{_MONTHS[current.month - 1]} {current.year} roku"
    )
    if asks_date and asks_time:
        return f"Dzisiaj jest {date_text}, a aktualna godzina to {current:%H:%M}."
    if asks_date:
        return f"Dzisiaj jest {date_text}."
    return f"Teraz jest {current:%H:%M}."


__all__ = ["format_local_clock"]
