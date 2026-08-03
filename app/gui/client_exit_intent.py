from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from app.assistant.natural_language import fold_text


_DIRECT_ENDINGS = (
    "koniec na dzis",
    "to wszystko na dzis",
    "mozemy skonczyc na dzis",
    "do jutra jarvis",
    "dobranoc jarvis",
)
_CLOSE_ACTIONS = (
    "zamknij",
    "wylacz",
    "zakoncz",
    "skoncz dzialanie",
    "wyjdz",
)
_SELF_TARGETS = (
    "zamknij sie",
    "wylacz sie",
    "sie zamknij",
    "sie wylacz",
    "sie zamknac",
    "sie wylaczyc",
    "zakoncz swoje dzialanie",
    "zamknij swoj program",
    "wylacz swoj program",
    "zamknij program jarvis",
    "wylacz program jarvis",
    "zamknij aplikacje jarvis",
    "wylacz aplikacje jarvis",
    "zamknij jarvisa",
    "wylacz jarvisa",
    "wyjdz z programu",
)
_OTHER_TARGETS = (
    "przegladark",
    "strone",
    "karte",
    "dokument",
    "plik",
    "notatnik",
    "gmail",
    "kalendar",
)


def is_jarvis_exit_request(text: object) -> bool:
    """Recognize natural requests to close JARVIS, not other applications."""
    value = fold_text(text)
    if not value:
        return False
    if any(phrase in value for phrase in _DIRECT_ENDINGS):
        return True
    if not any(action in value for action in _CLOSE_ACTIONS):
        return False
    if any(target in value for target in _SELF_TARGETS):
        return True
    if any(target in value for target in _OTHER_TARGETS):
        return False
    return "jarvis" in value and any(
        word in value for word in ("program", "aplikac", "system", "dzialanie")
    )


def request_jarvis_shutdown(window: Any, text: object = "") -> bool:
    """Acknowledge a natural exit request and close the complete application."""
    if text and not is_jarvis_exit_request(text):
        return False
    message = "Jasne. Kończę pracę. Do zobaczenia."
    presenter = getattr(window, "presenter", None)
    if presenter is not None:
        presenter.show("success", message, progress=100)
    speaker = getattr(window, "say_safe", None)
    if callable(speaker):
        speaker(message)
    close = getattr(window, "close", None)
    if callable(close):
        QTimer.singleShot(650, close)
    return True


__all__ = ["is_jarvis_exit_request", "request_jarvis_shutdown"]
