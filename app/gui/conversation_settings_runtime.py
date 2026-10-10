from __future__ import annotations

from pathlib import Path
from typing import Any

from app.assistant.conversation_preferences import (
    load_conversation_preferences,
    reset_conversation_preferences,
    save_conversation_preferences,
)
from app.gui.settings_page_extensions import load_conversation_settings


def load_owner_conversation_settings(
    page: Any,
    project_root: str | Path,
) -> None:
    load_conversation_settings(
        page,
        load_conversation_preferences(project_root),
    )


def save_owner_conversation_settings(
    project_root: str | Path,
    value: dict[str, Any],
) -> None:
    save_conversation_preferences(
        project_root,
        style=value.get("style", "natural"),
        question_mode=value.get("question_mode", "balanced"),
        memory_depth=value.get("memory_depth", 6),
        context_hours=value.get("context_hours", 1),
    )


def reset_owner_conversation_settings(project_root: str | Path) -> None:
    reset_conversation_preferences(project_root)


__all__ = [
    "load_owner_conversation_settings",
    "reset_owner_conversation_settings",
    "save_owner_conversation_settings",
]
