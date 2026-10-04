from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def install_system_tray(
    app: QApplication,
    window: Any,
    icon: QIcon,
) -> QSystemTrayIcon | None:
    """Install a small, persistent entry point next to the Windows clock."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(icon, window)
    tray.setToolTip("JARVIS OS — działa w tle")
    menu = QMenu(window)
    show_action = QAction("Pokaż JARVIS OS", menu)
    quit_action = QAction("Zamknij JARVIS OS", menu)
    show_action.triggered.connect(lambda: show_jarvis_window(window))
    quit_action.triggered.connect(lambda: quit_jarvis(app, window))
    menu.addAction(show_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: _handle_activation(reason, window)
    )
    tray.show()

    # Qt objects without a lasting owner/reference can be collected early.
    window._system_tray_menu = menu
    window._system_tray_icon = tray
    return tray


def should_start_in_tray(
    config: dict[str, Any],
    *,
    tray_available: bool,
) -> bool:
    ui = dict(config.get("ui", {}) or {})
    return bool(ui.get("start_minimized", False)) and tray_available


def show_jarvis_window(window: Any) -> None:
    window.show_start_mode()
    QTimer.singleShot(0, lambda: _raise_active_window(window))


def _raise_active_window(window: Any) -> None:
    client = getattr(window, "client_window", None)
    target = client if client is not None and client.isVisible() else window
    target.show()
    target.raise_()
    target.activateWindow()


def quit_jarvis(app: QApplication, window: Any) -> None:
    client = getattr(window, "client_window", None)
    if client is not None and client.isVisible():
        client.close()
    else:
        window.close()
    app.quit()


def _handle_activation(reason: object, window: Any) -> None:
    if reason in (
        QSystemTrayIcon.ActivationReason.Trigger,
        QSystemTrayIcon.ActivationReason.DoubleClick,
    ):
        show_jarvis_window(window)


__all__ = [
    "install_system_tray",
    "quit_jarvis",
    "should_start_in_tray",
    "show_jarvis_window",
]
