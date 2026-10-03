"""Natural actions public API loaded only when the service is requested."""

from importlib import import_module
from typing import Any

__all__ = ["NaturalActionService"]


def __getattr__(name: str) -> Any:
    if name != "NaturalActionService":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("app.natural_actions.service"), name)
    globals()[name] = value
    return value
