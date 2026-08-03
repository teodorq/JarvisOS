from __future__ import annotations

import re
from typing import Any

from app.core.user_text import naturalize_user_text


class TrustedActionResult(str):
    """Already sanitized user-facing result from an exact action plan."""


class ClientIsolationPolicy:
    """Twarda granica pomiędzy widokiem klienta i panelem właściciela."""

    TECHNICAL_MARKERS = (
        "audit", "audyt", "traceback", "exception", "sha-256",
        "integrity", "pytest", "unittest", "/app/",
        "autodev", "debug", "owner", "właściciel", "router", "controller",
        "stack", "token", "client_secret", "api key", "error_id",
    )
    RESULT_TYPES = {"mail", "calendar", "documents", "reminders", "day", "finances", "general", "warning", "error"}

    @classmethod
    def sanitize_text(cls, value: object, *, fallback: str = "Zadanie zostało obsłużone.") -> str:
        text = naturalize_user_text(value, maximum=900, preserve_lines=False)
        if not text:
            return fallback
        lower = text.casefold()
        if any(marker in lower for marker in cls.TECHNICAL_MARKERS):
            return cls._friendly_summary(text, fallback)
        text = re.sub(r"[A-Za-z]:\\[^\s]+", "", text)
        text = re.sub(r"\b[0-9a-f]{12,64}\b", "", text, flags=re.I)
        text = " ".join(text.split()).strip(" -—:;")
        return text[:900] or fallback

    @classmethod
    def sanitize_action_result(
        cls,
        value: object,
        *,
        fallback: str = "Zadanie zostało zakończone.",
    ) -> str:
        """Sanitize a trusted user-facing action result without hiding titles."""
        text = naturalize_user_text(value, maximum=6000, preserve_lines=True)
        if not text:
            return fallback
        text = re.sub(r"[A-Za-z]:\\[^\s]+", "", text)
        text = re.sub(r"\b[0-9a-f]{12,64}\b", "", text, flags=re.I)
        lines = [line.strip(" -—:;") for line in text.splitlines()]
        text = "\n".join(line for line in lines if line).strip()
        return TrustedActionResult(text[:6000] or fallback)

    @classmethod
    def sanitize_event(cls, event: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "state", "message", "progress", "requires_confirmation",
            "result", "result_type", "view_mode",
        }
        clean = {key: event[key] for key in allowed if key in event}
        if "message" in clean:
            cleaner = cls.sanitize_action_result if isinstance(clean["message"], TrustedActionResult) else cls.sanitize_text
            clean["message"] = cleaner(clean["message"])
        if "result" in clean:
            cleaner = cls.sanitize_action_result if isinstance(clean["result"], TrustedActionResult) else cls.sanitize_text
            clean["result"] = cleaner(clean["result"])
        if "result_type" in clean:
            result_type = str(clean.get("result_type", "")).casefold()
            clean["result_type"] = result_type if result_type in cls.RESULT_TYPES else ""
        if "view_mode" in clean:
            view_mode = str(clean.get("view_mode", "")).casefold()
            clean["view_mode"] = (
                view_mode if view_mode in {"conversation", "pupil"} else ""
            )
        clean["progress"] = max(0, min(100, int(clean.get("progress", 0) or 0)))
        clean["requires_confirmation"] = bool(clean.get("requires_confirmation", False))
        clean["state"] = str(clean.get("state", "idle")).lower()
        return clean

    @staticmethod
    def _strip_stage_prefix(text: str) -> str:
        return naturalize_user_text(text)

    @classmethod
    def _friendly_summary(cls, text: str, fallback: str) -> str:
        lower = text.casefold()
        if "właściciel" in lower:
            return (
                "Ta funkcja jest dostępna tylko dla właściciela JARVISA."
            )
        if "odmowa" in lower or "brak uprawn" in lower:
            return "Nie mam uprawnień do wykonania tego działania."
        if "błąd" in lower or "error" in lower or "exception" in lower:
            return "Nie udało się zakończyć zadania. Sprawdzę bezpieczną drogę ponowienia."
        if "potwierd" in lower:
            return "To działanie wymaga Twojego potwierdzenia."
        if "plan" in lower or "analiz" in lower:
            return "Analizuję cel i wybieram najlepszy sposób wykonania."
        return fallback
