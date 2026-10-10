from __future__ import annotations

from pathlib import Path
from typing import Any

from app.assistant.project_memory import ProjectMemoryService


STYLE_OPTIONS = (
    ("Naturalny", "natural"),
    ("Krótki", "concise"),
    ("Luźny", "casual"),
    ("Dokładny", "detailed"),
)
QUESTION_MODE_OPTIONS = (
    ("Pytaj tylko, gdy pomaga", "balanced"),
    ("Nie kończ odpowiedzi pytaniem", "none"),
    ("Częściej podtrzymuj rozmowę", "engaged"),
)
_STYLES = {value for _label, value in STYLE_OPTIONS}
_QUESTION_MODES = {value for _label, value in QUESTION_MODE_OPTIONS}


def load_conversation_preferences(
    project_root: str | Path | None = None,
) -> dict[str, str]:
    memory = ProjectMemoryService(project_root)
    return {
        "style": _style(memory.get_preference("conversation_style", "natural")),
        "question_mode": _question_mode(
            memory.get_preference("conversation_question_mode", "balanced")
        ),
    }


def save_conversation_preferences(
    project_root: str | Path | None,
    *,
    style: object,
    question_mode: object,
) -> dict[str, str]:
    selected = {
        "style": _style(style),
        "question_mode": _question_mode(question_mode),
    }
    memory = ProjectMemoryService(project_root)
    memory.set_preference(
        "conversation_style",
        selected["style"],
        category="assistant_setting",
    )
    memory.set_preference(
        "conversation_question_mode",
        selected["question_mode"],
        category="assistant_setting",
    )
    return selected


def reset_conversation_preferences(
    project_root: str | Path | None = None,
) -> dict[str, str]:
    return save_conversation_preferences(
        project_root,
        style="natural",
        question_mode="balanced",
    )


def _style(value: Any) -> str:
    normalized = str(value or "natural").strip().casefold()
    if normalized == "neutral":
        normalized = "natural"
    return normalized if normalized in _STYLES else "natural"


def _question_mode(value: Any) -> str:
    normalized = str(value or "balanced").strip().casefold()
    return normalized if normalized in _QUESTION_MODES else "balanced"


__all__ = [
    "QUESTION_MODE_OPTIONS",
    "STYLE_OPTIONS",
    "load_conversation_preferences",
    "reset_conversation_preferences",
    "save_conversation_preferences",
]
