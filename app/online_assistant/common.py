from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


class OnlineAssistantError(RuntimeError):
    """Human-safe online integration error without credentials or raw payloads."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clip(value: object, limit: int = 500) -> str:
    text = str(value or "").replace("\x00", " ").strip()
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def fold_text(value: object) -> str:
    text = str(value or "").casefold()
    replacements = str.maketrans("ąćęłńóśżź", "acelnoszz")
    return re.sub(r"\s+", " ", text.translate(replacements)).strip()


def safe_error(error: BaseException) -> str:
    """Return a bounded message and suppress tokens/authorization material."""
    text = clip(error, 350)
    text = re.sub(
        r"(?i)(access_token|refresh_token|client_secret|authorization|bearer)\s*[:=]\s*[^\s,;]+",
        r"\1=[UKRYTO]",
        text,
    )
    text = re.sub(r"ya29\.[A-Za-z0-9._-]+", "[TOKEN UKRYTY]", text)
    return text or type(error).__name__


def header_value(headers: list[dict[str, Any]], name: str) -> str:
    target = name.casefold()
    for item in headers:
        if str(item.get("name", "")).casefold() == target:
            return clip(item.get("value", ""), 500)
    return ""
