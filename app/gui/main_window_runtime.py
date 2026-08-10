from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from app.gui.user_text_widgets import clean_user_visible_widgets
from app.gui.remote_command_runtime import connect_remote_command_runtime


def connect_main_runtime(window: Any) -> None:
    """Connect shared voice immediately and owner-only metrics on demand."""
    if not window._voice_runtime_connected:
        window.voice_text_signal.connect(window.handle_voice_text)
        if window.voice is not None:
            window.voice.start()
        window._voice_runtime_connected = True
    connect_remote_command_runtime(window)
    if not window._interface_ready or hasattr(window, "timer"):
        return
    window.timer = QTimer(window)
    window.timer.timeout.connect(window.update_system_status)
    window.timer.start(1000)


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


__all__ = ["connect_main_runtime", "prepare_owner_interface"]
