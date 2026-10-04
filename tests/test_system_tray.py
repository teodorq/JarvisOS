from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.gui.system_tray import (
    notify_tray_event,
    should_start_in_tray,
    show_jarvis_window,
)


def test_background_start_requires_user_preference_and_available_tray() -> None:
    config = {"ui": {"start_minimized": True}}

    assert should_start_in_tray(config, tray_available=True) is True
    assert should_start_in_tray(config, tray_available=False) is False
    assert should_start_in_tray({}, tray_available=True) is False


def test_show_jarvis_restores_visible_client_window() -> None:
    client = SimpleNamespace(
        isVisible=Mock(return_value=True),
        show=Mock(),
        raise_=Mock(),
        activateWindow=Mock(),
    )
    window = SimpleNamespace(
        client_window=client,
        show_start_mode=Mock(),
        show=Mock(),
        raise_=Mock(),
        activateWindow=Mock(),
    )

    with patch("app.gui.system_tray.QTimer.singleShot") as single_shot:
        show_jarvis_window(window)
        callback = single_shot.call_args.args[1]
        callback()

    window.show_start_mode.assert_called_once_with()
    single_shot.assert_called_once()
    client.show.assert_called_once_with()
    client.raise_.assert_called_once_with()
    client.activateWindow.assert_called_once_with()


def test_tray_notification_uses_safe_event_and_user_preference() -> None:
    tray = SimpleNamespace(supportsMessages=Mock(return_value=True), showMessage=Mock())
    window = SimpleNamespace(
        business_config={"notifications": {"desktop_enabled": True}},
        _system_tray_icon=tray,
    )

    assert notify_tray_event(window, {
        "state": "important",
        "message": "  Ochrona   PAPER wymaga uwagi.  ",
    }) is True
    assert tray.showMessage.call_args.args[0] == "JARVIS OS — Forex PAPER"
    assert tray.showMessage.call_args.args[1] == "Ochrona PAPER wymaga uwagi."

    window.business_config["notifications"]["desktop_enabled"] = False
    assert notify_tray_event(window, {"message": "Nowe zdarzenie"}) is False
    assert tray.showMessage.call_count == 1
