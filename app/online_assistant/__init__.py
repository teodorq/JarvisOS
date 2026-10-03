"""Online assistant public API with deferred controller import."""

from importlib import import_module
from typing import Any

__all__ = ["OnlineAssistantController"]


def __getattr__(name: str) -> Any:
    if name != "OnlineAssistantController":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("app.online_assistant.controller"), name)
    globals()[name] = value
    return value
