"""Assistant 1.2 public API with deferred controller import."""

from importlib import import_module
from typing import Any

__all__ = ["AssistantV12Controller"]


def __getattr__(name: str) -> Any:
    if name != "AssistantV12Controller":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("app.assistant_v12.controller"), name)
    globals()[name] = value
    return value
