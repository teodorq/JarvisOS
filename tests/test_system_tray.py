from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.gui.system_tray import should_start_in_tray, show_jarvis_window


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
