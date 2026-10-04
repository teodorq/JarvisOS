from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.business.business_config import DEFAULT_BUSINESS_CONFIG
from app.gui.business_pages import SettingsPage


APP = QApplication.instance() or QApplication([])


def test_settings_page_emits_complete_user_preferences() -> None:
    page = SettingsPage()
    page.load_config(DEFAULT_BUSINESS_CONFIG)
    page.startup_mode.setCurrentIndex(page.startup_mode.findData("client"))
    page.start_minimized.setCurrentIndex(page.start_minimized.findData(True))
    page.start_page.setCurrentIndex(page.start_page.findData("forex"))
    page.performance_profile.setCurrentIndex(
        page.performance_profile.findData("low_resource")
    )
    page.sound_effects.setCurrentIndex(page.sound_effects.findData(False))
    emitted: list[dict] = []
    page.save_requested.connect(emitted.append)

    page._save()

    assert emitted[0]["ui"]["startup_mode"] == "client"
    assert emitted[0]["ui"]["start_minimized"] is True
    assert emitted[0]["ui"]["start_page"] == "forex"
    assert emitted[0]["performance"]["profile"] == "low_resource"
    assert emitted[0]["sound"]["effects_enabled"] is False
    page.deleteLater()


def test_settings_maintenance_buttons_emit_actions() -> None:
    page = SettingsPage()
    events: list[str] = []
    page.health_requested.connect(lambda: events.append("health"))
    page.cleanup_requested.connect(lambda: events.append("cleanup"))
    page.autostart_refresh_requested.connect(
        lambda: events.append("autostart_check")
    )
    page.autostart_set_requested.connect(
        lambda enabled: events.append(f"autostart_{enabled}")
    )

    page.health_button.click()
    page.cleanup_button.click()
    page.autostart_check_button.click()
    page.autostart_on_button.click()
    page.autostart_off_button.click()

    assert events == [
        "health", "cleanup", "autostart_check",
        "autostart_True", "autostart_False",
    ]
    page.deleteLater()
