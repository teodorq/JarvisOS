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
MEMORY_DEPTH_OPTIONS = (
    ("Krótka — 3 ostatnie wymiany", 3),
    ("Naturalna — 6 ostatnich wymian", 6),
    ("Długa — 10 ostatnich wymian", 10),
)
CONTEXT_HOURS_OPTIONS = (
    ("1 godzina", 1),
    ("8 godzin — bieżący dzień", 8),
    ("24 godziny — do następnego dnia", 24),
)
_STYLES = {value for _label, value in STYLE_OPTIONS}
_QUESTION_MODES = {value for _label, value in QUESTION_MODE_OPTIONS}
_MEMORY_DEPTHS = {value for _label, value in MEMORY_DEPTH_OPTIONS}
_CONTEXT_HOURS = {value for _label, value in CONTEXT_HOURS_OPTIONS}


def load_conversation_preferences(
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    memory = ProjectMemoryService(project_root)
    return {
        "style": _style(memory.get_preference("conversation_style", "natural")),
        "question_mode": _question_mode(
            memory.get_preference("conversation_question_mode", "balanced")
        ),
        "memory_depth": _memory_depth(
            memory.get_preference("conversation_memory_depth", 6)
        ),
        "context_hours": _context_hours(
            memory.get_preference("conversation_context_hours", 1)
        ),
    }


def save_conversation_preferences(
    project_root: str | Path | None,
    *,
    style: object,
    question_mode: object,
    memory_depth: object = 6,
    context_hours: object = 1,
) -> dict[str, Any]:
    selected = {
        "style": _style(style),
        "question_mode": _question_mode(question_mode),
        "memory_depth": _memory_depth(memory_depth),
        "context_hours": _context_hours(context_hours),
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
    memory.set_preference(
        "conversation_memory_depth",
        selected["memory_depth"],
        category="assistant_setting",
    )
    memory.set_preference(
        "conversation_context_hours",
        selected["context_hours"],
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
        memory_depth=6,
        context_hours=1,
    )


def _style(value: Any) -> str:
    normalized = str(value or "natural").strip().casefold()
    if normalized == "neutral":
        normalized = "natural"
    return normalized if normalized in _STYLES else "natural"


def _question_mode(value: Any) -> str:
    normalized = str(value or "balanced").strip().casefold()
    return normalized if normalized in _QUESTION_MODES else "balanced"


def _memory_depth(value: Any) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 6
    return normalized if normalized in _MEMORY_DEPTHS else 6


def _context_hours(value: Any) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 1
    return normalized if normalized in _CONTEXT_HOURS else 1


__all__ = [
    "CONTEXT_HOURS_OPTIONS",
    "MEMORY_DEPTH_OPTIONS",
    "QUESTION_MODE_OPTIONS",
    "STYLE_OPTIONS",
    "load_conversation_preferences",
    "reset_conversation_preferences",
    "save_conversation_preferences",
]
