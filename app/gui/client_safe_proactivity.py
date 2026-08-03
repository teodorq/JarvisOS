from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QTimer


class ClientSafeProactivityRuntime:
    """Queues at most one proactive client action until the UI is idle."""

    CHECK_INTERVAL_MS = 500
    GENERIC_MESSAGE = "Wykryłem nową ważną informację w kalendarzu."

    def __init__(self, window: Any) -> None:
        self.window = window
        self.pending_action: Callable[[], None] | None = None
        self.pending_priority = -1
        self.pending_kind = ""
        self.timer = QTimer(window)
        self.timer.setInterval(self.CHECK_INTERVAL_MS)
        self.timer.timeout.connect(self.flush)

    def request(
        self,
        action: Callable[[], None],
        *,
        priority: int = 0,
        kind: str = "proactive",
    ) -> bool:
        if self._safe():
            action()
            return True
        if self.pending_action is None or priority >= self.pending_priority:
            self.pending_action = action
            self.pending_priority = int(priority)
            self.pending_kind = str(kind)
        if not self.timer.isActive():
            self.timer.start()
        return False

    def deliver(
        self,
        raw_event: object,
        *,
        priority: int = 0,
        kind: str = "proactive",
    ) -> bool:
        event = self._safe_event(raw_event)
        return self.request(
            lambda value=event: self.window._on_client_event(value),
            priority=priority,
            kind=kind,
        )

    def flush(self) -> None:
        if self.pending_action is None:
            self.timer.stop()
            return
        if not self._safe():
            return
        action = self.pending_action
        self.pending_action = None
        self.pending_priority = -1
        self.pending_kind = ""
        self.timer.stop()
        action()

    def status(self) -> dict[str, Any]:
        return {
            "status": "SAFE_PROACTIVITY_POLICY_READY",
            "pending_count": 1 if self.pending_action is not None else 0,
            "pending_kind": self.pending_kind,
            "automatic_writes": False,
            "voice_notifications": False,
        }

    def _safe(self) -> bool:
        presenter = getattr(self.window, "presenter", None)
        if bool(getattr(presenter, "busy", False)):
            return False
        owner = getattr(self.window, "owner_window", None)
        if getattr(owner, "pending_thought", None) is not None:
            return False
        frame = getattr(self.window, "confirm_frame", None)
        visible = getattr(frame, "isVisible", None)
        if callable(visible) and visible():
            return False
        entry = getattr(self.window, "command_entry", None)
        text = getattr(entry, "text", None)
        if callable(text) and str(text()).strip():
            return False
        return True

    @classmethod
    def _safe_event(cls, raw_event: object) -> dict[str, Any]:
        event = dict(raw_event) if isinstance(raw_event, dict) else {}
        message = " ".join(str(event.get("message", "")).split()).strip()
        technical = (
            "traceback",
            "exception",
            "c:\\",
            "/home/",
            "sha-256",
            "install_",
            "tests.",
            ".py:",
        )
        if not message or any(marker in message.lower() for marker in technical):
            message = cls.GENERIC_MESSAGE
        return {
            "state": "important"
            if str(event.get("state", "")).lower() == "important"
            else "brief",
            "message": message[:420],
            "progress": 0,
            "requires_confirmation": False,
        }
