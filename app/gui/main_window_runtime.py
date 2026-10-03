from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from app.gui.user_text_widgets import clean_user_visible_widgets
from app.gui.remote_command_runtime import connect_remote_command_runtime

OWNER_METRICS_INTERVAL_MS = 1000
OWNER_FOREX_INTERVAL_MS = 5000


def _interval(window: Any, name: str, fallback: int) -> int:
    profile = getattr(window, "performance_profile", None)
    value = getattr(profile, name, fallback)
    if not isinstance(value, int):
        return fallback
    return max(250, value)


def _runtime_timer(window: Any, name: str):
    attributes = getattr(window, "__dict__", {})
    return attributes.get(name) if isinstance(attributes, dict) else None


def connect_main_runtime(window: Any) -> None:
    """Connect shared voice immediately and owner-only metrics on demand."""
    if not window._voice_runtime_connected:
        window.voice_text_signal.connect(window.handle_voice_text)
        if window.voice is not None and bool(
            getattr(window.voice, "continuous_mode", False)
        ):
            window.voice.start()
        window._voice_runtime_connected = True
    connect_remote_command_runtime(window)
    _connect_forex_activity_runtime(window)
    if not window._interface_ready or hasattr(window, "timer"):
        return
    window.timer = QTimer(window)
    window.timer.timeout.connect(window.update_system_status)
    window.timer.start(
        _interval(
            window,
            "owner_metrics_interval_ms",
            OWNER_METRICS_INTERVAL_MS,
        )
    )


def set_owner_metrics_active(window: Any, active: bool) -> None:
    """Avoid refreshing hidden owner widgets while shared runtimes stay alive."""
    timer = _runtime_timer(window, "timer")
    forex_timer = _runtime_timer(window, "_forex_activity_timer")
    if active:
        if timer is not None:
            if not timer.isActive():
                timer.start(
                    _interval(
                        window,
                        "owner_metrics_interval_ms",
                        OWNER_METRICS_INTERVAL_MS,
                    )
                )
            window.update_system_status()
        if forex_timer is not None and not forex_timer.isActive():
            forex_timer.start(
                _interval(
                    window,
                    "owner_forex_interval_ms",
                    OWNER_FOREX_INTERVAL_MS,
                )
            )
        return
    if timer is not None:
        timer.stop()
    if forex_timer is not None:
        forex_timer.stop()


def _connect_forex_activity_runtime(window: Any) -> None:
    if hasattr(window, "_forex_activity_timer"):
        return
    window._forex_activity_timer = QTimer(window)
    window._forex_activity_timer.timeout.connect(
        lambda: _show_forex_paper_activity(window)
    )
    window._forex_activity_timer.start(
        _interval(
            window,
            "owner_forex_interval_ms",
            OWNER_FOREX_INTERVAL_MS,
        )
    )


def _show_forex_paper_activity(window: Any) -> None:
    client_window = getattr(window, "client_window", None)
    client_visible = getattr(client_window, "isVisible", None)
    if callable(client_visible) and client_visible():
        return
    try:
        event = window.assistant.trading.forex_activity.poll()
    except Exception:
        return
    if not isinstance(event, dict):
        return
    message = str(event.get("message", "")).strip()
    if window._interface_ready and message:
        window.console_page.append(f"Jarvis: {message}")
    window.client_event_signal.emit(event)


def prepare_owner_interface(window: Any) -> None:
    """Build the large owner dashboard only when the owner opens it."""
    if window._interface_ready:
        return
    window._build_interface()
    clean_user_visible_widgets(window)
    window._interface_ready = True
    window.assistant.set_progress_callback(window._on_assistant_v12_progress)
    connect_main_runtime(window)
    window._refresh_business_status()
    window.update_system_status()


__all__ = [
    "connect_main_runtime", "prepare_owner_interface", "set_owner_metrics_active",
]
