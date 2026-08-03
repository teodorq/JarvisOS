from __future__ import annotations

from typing import Any
import re
import unicodedata


_UNDO_COMMANDS = {
    "cofnij to", "cofnij ostatnia zmiane",
    "cofnij ostatnia zmiane kalendarza", "przywroc poprzedni termin",
}

_APPLY_COMMANDS = {
    "zrob to",
    "wykonaj to",
    "zastosuj propozycje",
    "wykonaj propozycje",
    "tak zrob",
}

_GMAIL_SEND_COMMANDS = {
    "wyslij te odpowiedz", "wyslij ta odpowiedz", "wyslij odpowiedz",
    "wyslij przygotowana odpowiedz", "wyslij ostatnia odpowiedz",
    "wyslij ten szkic", "wyslij przygotowany szkic", "wyslij ostatni szkic",
    "nadaj te odpowiedz", "przeslij te odpowiedz", "podeslij te odpowiedz",
    "wyslij szkic", "wyslij go", "wyslij ja", "prosze wyslij odpowiedz",
}


def _fold_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold())
    ascii_text = "".join(
        char for char in text if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def active_resolution_priority_thought(window: Any, command: object) -> dict | None:
    """Return exact calendar or Gmail follow-up plans before global routing."""
    assistant = getattr(window, "assistant", None)
    natural = getattr(assistant, "natural_actions", None)
    folded = _fold_text(command)
    if natural is None:
        return None

    if folded in _GMAIL_SEND_COMMANDS:
        thought = natural.plan(command)
        if thought.get("assistant_intent") != "mail_send_existing":
            raise RuntimeError("Wysyłka szkicu została skierowana do złego routera.")
        return thought if thought.get("requires_confirmation") else None

    if folded not in _APPLY_COMMANDS | _UNDO_COMMANDS:
        return None
    if folded in _APPLY_COMMANDS:
        active = getattr(getattr(natural, "runtime", None), "active", None)
        memory = getattr(active, "memory", None)
        if memory is None or not dict(memory.last_suggestion() or {}):
            return None
    thought = natural.plan(command)
    expected = (
        "active_apply_suggestion" if folded in _APPLY_COMMANDS
        else "active_undo_calendar"
    )
    if not bool(thought.get("natural_action")) or thought.get("assistant_intent") != expected:
        raise RuntimeError("Aktywne działanie zostało skierowane do złego routera.")
    if folded in _APPLY_COMMANDS:
        return thought
    return thought if thought.get("requires_confirmation") else None
