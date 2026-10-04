from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from app.gui.business_widgets import SectionCard


STARTUP_MODES = (
    ("Ostatnio używany ekran", "remember"),
    ("Rozmowa z JARVIS", "client"),
    ("Panel właściciela", "owner"),
)
START_PAGES = (
    ("Konsola", "console"),
    ("Asystent i codzienna praca", "assistant"),
    ("Produktywność", "productivity"),
    ("Forex PAPER", "forex"),
    ("Stabilność", "stability"),
    ("Ustawienia", "settings"),
)
PERFORMANCE_PROFILES = (
    ("Automatyczna — reaguje na baterię do 30 s", "auto"),
    ("Oszczędna — słabsze urządzenia", "low_resource"),
    ("Pełna jakość", "balanced"),
)


def install_settings_extensions(page: Any, content: Any) -> None:
    runtime = SectionCard(
        "Uruchamianie i wydajność",
        "Wybierz ekran startowy i dopasuj obciążenie do komputera.",
    )
    form = QFormLayout()
    form.setHorizontalSpacing(18)
    page.startup_mode = _combo(STARTUP_MODES)
    page.start_minimized = _combo((
        ("Pokaż okno", False),
        ("Zacznij w zasobniku obok zegara", True),
    ))
    page.start_page = _combo(START_PAGES)
    page.performance_profile = _combo(PERFORMANCE_PROFILES)
    page.sound_effects = _combo((
        ("Włączone", True),
        ("Wyłączone", False),
    ))
    page.desktop_notifications = _combo((
        ("Włączone", True),
        ("Wyłączone", False),
    ))
    form.addRow("Ekran po uruchomieniu", page.startup_mode)
    form.addRow("Widoczność po uruchomieniu", page.start_minimized)
    form.addRow("Start panelu właściciela", page.start_page)
    form.addRow("Tryb wydajności", page.performance_profile)
    form.addRow("Dźwięki interfejsu", page.sound_effects)
    form.addRow("Powiadomienia Windows", page.desktop_notifications)
    runtime.content_layout.addLayout(form)
    note = QLabel(
        "Zmiana wydajności i dźwięków działa od razu. Sposób uruchomienia "
        "zacznie obowiązywać przy następnym starcie JARVIS."
    )
    note.setObjectName("Muted")
    note.setWordWrap(True)
    runtime.content_layout.addWidget(note)
    content.addWidget(runtime)

    maintenance = SectionCard(
        "Stan systemu i miejsce na dysku",
        "Kontrola jest tylko do odczytu. Porządkowanie zachowuje ustawienia, "
        "pamięć, rozmowy i dane tradingowe.",
    )
    row = QHBoxLayout()
    page.health_button = QPushButton("SPRAWDŹ STAN JARVIS")
    page.health_button.setObjectName("SecondaryButton")
    page.health_button.clicked.connect(page.health_requested.emit)
    page.cleanup_button = QPushButton("UPORZĄDKUJ DANE")
    page.cleanup_button.setObjectName("SecondaryButton")
    page.cleanup_button.clicked.connect(page.cleanup_requested.emit)
    row.addWidget(page.health_button)
    row.addWidget(page.cleanup_button)
    row.addStretch(1)
    maintenance.content_layout.addLayout(row)
    page.maintenance_feedback = QLabel("Gotowy do sprawdzenia.")
    page.maintenance_feedback.setObjectName("Muted")
    page.maintenance_feedback.setWordWrap(True)
    maintenance.content_layout.addWidget(page.maintenance_feedback)
    content.addWidget(maintenance)

    autostart = SectionCard(
        "Autostart Windows",
        "Uruchamiaj JARVIS po zalogowaniu, bez okna konsoli. Ręczne zamknięcie "
        "nie uruchamia aplikacji ponownie.",
    )
    autostart_row = QHBoxLayout()
    page.autostart_check_button = QPushButton("SPRAWDŹ")
    page.autostart_on_button = QPushButton("WŁĄCZ")
    page.autostart_off_button = QPushButton("WYŁĄCZ")
    for button in (
        page.autostart_check_button,
        page.autostart_on_button,
        page.autostart_off_button,
    ):
        button.setObjectName("SecondaryButton")
        autostart_row.addWidget(button)
    autostart_row.addStretch(1)
    page.autostart_check_button.clicked.connect(
        page.autostart_refresh_requested.emit
    )
    page.autostart_on_button.clicked.connect(
        lambda: page.autostart_set_requested.emit(True)
    )
    page.autostart_off_button.clicked.connect(
        lambda: page.autostart_set_requested.emit(False)
    )
    autostart.content_layout.addLayout(autostart_row)
    page.autostart_feedback = QLabel("Stan autostartu: nie sprawdzono.")
    page.autostart_feedback.setObjectName("Muted")
    autostart.content_layout.addWidget(page.autostart_feedback)
    content.addWidget(autostart)


def load_settings_extensions(page: Any, config: dict[str, Any]) -> None:
    ui = dict(config.get("ui", {}) or {})
    _select(page.startup_mode, ui.get("startup_mode", "remember"))
    _select(page.start_minimized, bool(ui.get("start_minimized", False)))
    _select(page.start_page, ui.get("start_page", "console"))
    performance = dict(config.get("performance", {}) or {})
    _select(page.performance_profile, performance.get("profile", "auto"))
    sound = dict(config.get("sound", {}) or {})
    _select(page.sound_effects, bool(sound.get("effects_enabled", True)))
    notifications = dict(config.get("notifications", {}) or {})
    _select(
        page.desktop_notifications,
        bool(notifications.get("desktop_enabled", True)),
    )


def settings_extension_updates(page: Any) -> dict[str, Any]:
    return {
        "ui": {
            "startup_mode": page.startup_mode.currentData(),
            "start_minimized": bool(page.start_minimized.currentData()),
            "start_page": page.start_page.currentData(),
            "show_quick_actions": bool(page.quick_actions.currentData()),
        },
        "performance": {"profile": page.performance_profile.currentData()},
        "sound": {"effects_enabled": bool(page.sound_effects.currentData())},
        "notifications": {
            "desktop_enabled": bool(page.desktop_notifications.currentData())
        },
    }


def set_settings_action_busy(page: Any, busy: bool) -> None:
    page.health_button.setDisabled(bool(busy))
    page.cleanup_button.setDisabled(bool(busy))
    for name in (
        "autostart_check_button", "autostart_on_button",
        "autostart_off_button",
    ):
        button = getattr(page, name, None)
        if button is not None:
            button.setDisabled(bool(busy))
    if busy:
        page.maintenance_feedback.setText("Sprawdzam — możesz dalej używać JARVIS.")


def set_settings_action_feedback(page: Any, text: str, healthy: bool) -> None:
    set_settings_action_busy(page, False)
    page.maintenance_feedback.setText(str(text))
    page.maintenance_feedback.setObjectName("Healthy" if healthy else "Danger")
    page.maintenance_feedback.style().unpolish(page.maintenance_feedback)
    page.maintenance_feedback.style().polish(page.maintenance_feedback)


def set_autostart_action_feedback(page: Any, text: str, healthy: bool) -> None:
    set_settings_action_busy(page, False)
    page.autostart_feedback.setText(str(text))
    page.autostart_feedback.setObjectName("Healthy" if healthy else "Danger")
    page.autostart_feedback.style().unpolish(page.autostart_feedback)
    page.autostart_feedback.style().polish(page.autostart_feedback)


def _combo(items: tuple[tuple[str, Any], ...]) -> QComboBox:
    combo = QComboBox()
    for label, value in items:
        combo.addItem(label, value)
    return combo


def _select(combo: QComboBox, value: object) -> None:
    index = combo.findData(value)
    combo.setCurrentIndex(max(0, index))


__all__ = [
    "install_settings_extensions", "load_settings_extensions",
    "set_autostart_action_feedback",
    "set_settings_action_busy", "set_settings_action_feedback",
    "settings_extension_updates",
]
