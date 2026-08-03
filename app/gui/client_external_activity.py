from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.ai.actions import ActionTypes
from app.core.project_paths import resolve_project_root
from app.core.safe_process import SafeProcessRunner


EXTERNAL_ACTIONS = {
    ActionTypes.OPEN_WEBSITE,
    ActionTypes.OPEN_APP,
    ActionTypes.OPEN_URL,
    ActionTypes.GOOGLE_SEARCH,
    ActionTypes.YOUTUBE_SEARCH,
    ActionTypes.YOUTUBE_FIRST_VIDEO,
    ActionTypes.TYPE_TEXT,
    ActionTypes.PRESS_ENTER,
    ActionTypes.CLICK,
    ActionTypes.SCREENSHOT,
    ActionTypes.VISION_ANALYZE,
    ActionTypes.VISION_CLICK,
}

CALENDAR_COMPANION_INTENTS = {
    "calendar_today",
    "calendar_search",
    "calendar_today_overview",
    "day_overview",
}

TODAY_CALENDAR_URL = "https://calendar.google.com/calendar/u/0/r/day"
WEEK_CALENDAR_URL = "https://calendar.google.com/calendar/u/0/r/week"
GMAIL_URL = "https://mail.google.com/mail/u/0/#inbox"
DRIVE_RECENT_URL = "https://drive.google.com/drive/u/0/recent"
COMPANION_URLS = {
    **{intent: TODAY_CALENDAR_URL for intent in CALENDAR_COMPANION_INTENTS},
    "calendar_week_overview": WEEK_CALENDAR_URL,
    "documents_recent": DRIVE_RECENT_URL,
    "drive_search": DRIVE_RECENT_URL,
    "drive_summarize": DRIVE_RECENT_URL,
    "gmail_latest": GMAIL_URL,
    "gmail_priority": GMAIL_URL,
    "gmail_search": GMAIL_URL,
    "gmail_read": GMAIL_URL,
    "gmail_thread": GMAIL_URL,
}
PUPIL_ONLY_INTENTS = {"bills_overview"}


def view_mode_for_thought(thought: object) -> str:
    """Use the pupil only while JARVIS is visibly working outside its window."""
    planned = dict(thought or {}) if isinstance(thought, dict) else {}
    intent = str(planned.get("assistant_intent", "")).casefold()
    if intent in COMPANION_URLS or intent in PUPIL_ONLY_INTENTS:
        return "pupil"
    for action in list(planned.get("actions", []) or []):
        if not isinstance(action, dict):
            continue
        if str(action.get("action_type", "")).casefold() in EXTERNAL_ACTIONS:
            return "pupil"
    return "conversation"


def open_external_companion(window: Any, thought: object) -> str:
    """Open an allowlisted visual companion for a matching read-only action."""
    planned = dict(thought or {}) if isinstance(thought, dict) else {}
    intent = str(planned.get("assistant_intent", "")).casefold()
    url = COMPANION_URLS.get(intent, "")
    if not url or not bool(planned.get("read_only", False)):
        return ""
    executor = getattr(getattr(window, "brain", None), "executor", None)
    browser = getattr(executor, "browser", None)
    open_url = getattr(browser, "open_url", None)
    if not callable(open_url):
        return ""
    try:
        return str(open_url(url) or "")
    except Exception:
        return ""


def open_result_companion(window: Any, thought: object) -> str:
    """Open a locally generated result only for an exact safe client intent."""
    if os.environ.get("QT_QPA_PLATFORM", "").casefold() == "offscreen":
        return ""
    planned = dict(thought or {}) if isinstance(thought, dict) else {}
    if not bool(planned.get("read_only", False)):
        return ""
    intent = str(planned.get("assistant_intent", "")).casefold()
    controller = getattr(window, "controller", None)
    root = resolve_project_root(getattr(controller, "project_root", None))
    target: Path | None = None
    executable = ""
    if intent == "bills_overview":
        target = root / "AI_PLIKI" / "finanse" / "RACHUNKI_DZISIAJ.txt"
        executable = "notepad.exe"
    elif intent == "documents_recent":
        target = root / "AI_PLIKI" / "documents"
        if not target.exists():
            target = root / "AI_PLIKI"
        executable = "explorer.exe"
    if target is None or not target.exists():
        return ""
    try:
        runner = SafeProcessRunner(project_root=root, allowed_executables=(executable,))
        runner.spawn([executable, str(target)])
        return str(target)
    except (OSError, ValueError):
        return ""


__all__ = [
    "TODAY_CALENDAR_URL",
    "WEEK_CALENDAR_URL",
    "open_external_companion",
    "open_result_companion",
    "view_mode_for_thought",
]
