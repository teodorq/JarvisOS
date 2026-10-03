"""Stability public API with deferred controller import."""

from importlib import import_module
from typing import Any

__all__ = ["StabilitySuiteController"]


def __getattr__(name: str) -> Any:
    if name != "StabilitySuiteController":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("app.stability.controller"), name)
    globals()[name] = value
    return value
