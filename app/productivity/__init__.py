"""Productivity public API with per-component deferred imports."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "DailyProductivityBriefing": "app.productivity.daily_briefing",
    "LocalCalendarCenter": "app.productivity.calendar_center",
    "LocalDocumentCenter": "app.productivity.document_center",
    "LocalMailCenter": "app.productivity.mail_center",
    "ProductivitySuiteController": "app.productivity.controller",
    "ReminderCenterV2": "app.productivity.reminder_center",
}
__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
