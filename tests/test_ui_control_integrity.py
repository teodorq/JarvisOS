from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import SIGNAL, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton, QTabWidget

from app.client_experience.controller import ClientExperienceController
from app.gui.client_experience_window import ClientExperienceWindow
from app.gui.main_window import MainWindow


def _disable_voice(window: MainWindow) -> None:
    window.voice = None
    window.voice_online = False


def _build_complete_ui(root: Path) -> tuple[MainWindow, ClientExperienceWindow]:
    with (
        patch("app.gui.main_window.resolve_project_root", return_value=root),
        patch("app.gui.main_window.connect_main_runtime", return_value=None),
        patch.object(MainWindow, "_initialize_voice", _disable_voice),
    ):
        owner = MainWindow()
    owner._ensure_owner_interface()
    for page_name in tuple(owner.pages):
        owner._show_page(page_name)
    client = ClientExperienceWindow(ClientExperienceController(root), owner)
    return owner, client


def _dispose(*windows: object) -> None:
    for window in windows:
        for timer in window.findChildren(QTimer):
            timer.stop()
        window.hide()
        window.deleteLater()


def test_every_ui_button_is_named_and_connected() -> None:
    app = QApplication.instance() or QApplication([])
    with TemporaryDirectory() as temporary:
        owner, client = _build_complete_ui(Path(temporary))
        buttons = [
            *owner.findChildren(QPushButton),
            *client.findChildren(QPushButton),
        ]

        assert len(buttons) >= 200
        for button in buttons:
            identity = (
                button.text().strip()
                or button.toolTip().strip()
                or button.accessibleName().strip()
            )
            assert identity, f"Przycisk bez nazwy: {button.objectName()}"
            assert button.receivers(SIGNAL("clicked(bool)")) > 0, identity

        _dispose(client, owner)
    app.processEvents()


def test_every_choice_has_alternatives_or_is_disabled() -> None:
    app = QApplication.instance() or QApplication([])
    with TemporaryDirectory() as temporary:
        owner, client = _build_complete_ui(Path(temporary))
        combos = [
            *owner.findChildren(QComboBox),
            *client.findChildren(QComboBox),
        ]

        assert len(combos) >= 18
        for combo in combos:
            assert combo.count() > 1 or not combo.isEnabled()

        tabs = owner.findChildren(QTabWidget)
        assert tabs
        assert all(tab.count() > 1 for tab in tabs)
        _dispose(client, owner)
    app.processEvents()


def test_profile_selector_only_activates_a_different_profile() -> None:
    app = QApplication.instance() or QApplication([])
    with TemporaryDirectory() as temporary:
        owner, client = _build_complete_ui(Path(temporary))
        page = owner.pages["platform"]

        assert page.profile_selector.count() == 1
        assert not page.profile_selector.isEnabled()
        assert not page.activate_profile_button.isEnabled()

        page.service.organization_profiles.snapshot_current("Drugi profil")
        page.refresh()
        assert page.profile_selector.count() == 2
        assert page.profile_selector.isEnabled()
        assert not page.activate_profile_button.isEnabled()

        active = page.profile_selector.currentIndex()
        page.profile_selector.setCurrentIndex(1 - active)
        assert page.activate_profile_button.isEnabled()
        _dispose(client, owner)
    app.processEvents()


def test_client_does_not_build_replaced_quick_button_row() -> None:
    app = QApplication.instance() or QApplication([])
    with TemporaryDirectory() as temporary:
        owner, client = _build_complete_ui(Path(temporary))
        assert not hasattr(client, "quick_buttons")
        _dispose(client, owner)
    app.processEvents()
