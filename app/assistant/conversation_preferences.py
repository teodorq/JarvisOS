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
_STYLES = {value for _label, value in STYLE_OPTIONS}
_QUESTION_MODES = {value for _label, value in QUESTION_MODE_OPTIONS}
_MEMORY_DEPTHS = {value for _label, value in MEMORY_DEPTH_OPTIONS}


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
    }


def save_conversation_preferences(
    project_root: str | Path | None,
    *,
    style: object,
    question_mode: object,
    memory_depth: object = 6,
) -> dict[str, Any]:
    selected = {
        "style": _style(style),
        "question_mode": _question_mode(question_mode),
        "memory_depth": _memory_depth(memory_depth),
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
    return selected


def reset_conversation_preferences(
    project_root: str | Path | None = None,
) -> dict[str, str]:
    return save_conversation_preferences(
        project_root,
        style="natural",
        question_mode="balanced",
        memory_depth=6,
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


__all__ = [
    "MEMORY_DEPTH_OPTIONS",
    "QUESTION_MODE_OPTIONS",
    "STYLE_OPTIONS",
    "load_conversation_preferences",
    "reset_conversation_preferences",
    "save_conversation_preferences",
]
