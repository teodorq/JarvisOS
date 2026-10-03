from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.business.business_config import BusinessConfigStore
from app.core.runtime_maintenance import (
    cleanup_runtime_storage,
    runtime_storage_status,
)
from app.core.windows_autostart import autostart_status, set_autostart
from app.gui.client_background_reads import submit_client_read


def install_client_settings_controls(window: Any, content: QVBoxLayout) -> None:
    frame = QFrame()
    frame.setObjectName("ClientSettingsAdvanced")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 8, 0, 0)
    layout.setSpacing(10)
    title = QLabel("DZIAŁANIE JARVIS OS")
    title.setObjectName("ClientHint")
    layout.addWidget(title)
    form = QFormLayout()
    form.setHorizontalSpacing(16)
    window.client_performance = _combo((
        ("Automatyczna — zalecana", "auto"),
        ("Oszczędna", "low_resource"),
        ("Pełna jakość", "balanced"),
    ))
    window.client_sounds = _combo((("Włączone", True), ("Wyłączone", False)))
    window.client_startup = _combo((
        ("Ostatnio używany ekran", "remember"),
        ("Rozmowa z JARVIS", "client"),
        ("Panel właściciela", "owner"),
    ))
    form.addRow("Wydajność", window.client_performance)
    form.addRow("Dźwięki", window.client_sounds)
    form.addRow("Ekran po uruchomieniu", window.client_startup)
    layout.addLayout(form)
    actions = QHBoxLayout()
    window.client_health_button = QPushButton("SPRAWDŹ STAN")
    window.client_health_button.setObjectName("ClientSecondary")
    window.client_cleanup_button = QPushButton("UPORZĄDKUJ DANE")
    window.client_cleanup_button.setObjectName("ClientSecondary")
    window.client_health_button.clicked.connect(
        lambda: _run_maintenance(window, cleanup=False)
    )
    window.client_cleanup_button.clicked.connect(
        lambda: _run_maintenance(window, cleanup=True)
    )
    actions.addWidget(window.client_health_button)
    actions.addWidget(window.client_cleanup_button)
    layout.addLayout(actions)
    window.client_maintenance_feedback = QLabel(
        "Porządkowanie nie usuwa ustawień, pamięci ani danych tradingowych."
    )
    window.client_maintenance_feedback.setObjectName("ClientHint")
    window.client_maintenance_feedback.setWordWrap(True)
    layout.addWidget(window.client_maintenance_feedback)
    autostart_title = QLabel("AUTOSTART PO WŁĄCZENIU KOMPUTERA")
    autostart_title.setObjectName("ClientHint")
    layout.addWidget(autostart_title)
    autostart_actions = QHBoxLayout()
    window.client_autostart_on = QPushButton("WŁĄCZ")
    window.client_autostart_off = QPushButton("WYŁĄCZ")
    for button in (window.client_autostart_on, window.client_autostart_off):
        button.setObjectName("ClientSecondary")
        autostart_actions.addWidget(button)
    window.client_autostart_on.clicked.connect(
        lambda: _run_autostart(window, enabled=True)
    )
    window.client_autostart_off.clicked.connect(
        lambda: _run_autostart(window, enabled=False)
    )
    layout.addLayout(autostart_actions)
    window.client_autostart_feedback = QLabel("Stan autostartu: nie sprawdzono.")
    window.client_autostart_feedback.setObjectName("ClientHint")
    window.client_autostart_feedback.setWordWrap(True)
    layout.addWidget(window.client_autostart_feedback)
    window.client_settings_advanced = frame
    frame.hide()
    content.addWidget(frame)


def show_client_settings_controls(window: Any) -> None:
    if not hasattr(window, "client_settings_advanced"):
        return
    config = _store(window).ensure()
    ui = dict(config.get("ui", {}) or {})
    performance = dict(config.get("performance", {}) or {})
    sound = dict(config.get("sound", {}) or {})
    _select(window.client_performance, performance.get("profile", "auto"))
    _select(window.client_sounds, bool(sound.get("effects_enabled", True)))
    _select(window.client_startup, ui.get("startup_mode", "remember"))
    window.client_settings_advanced.show()
    _run_autostart(window, enabled=None)


def save_client_settings_controls(window: Any) -> None:
    if not window.client_settings_advanced.isVisible():
        return
    config = _store(window).update({
        "ui": {"startup_mode": window.client_startup.currentData()},
        "performance": {"profile": window.client_performance.currentData()},
        "sound": {"effects_enabled": bool(window.client_sounds.currentData())},
    })
    if getattr(window, "owner_window", None) is not None:
        window.owner_window.business_config = config


def _run_maintenance(window: Any, *, cleanup: bool) -> None:
    _set_busy(window, True)
    if cleanup:
        operation = lambda: cleanup_runtime_storage(
            window.controller.project_root
        )
    else:
        operation = lambda: runtime_storage_status(
            window.controller.project_root
        )
    accepted = submit_client_read(
        window,
        operation,
        lambda result: _maintenance_done(window, result, cleanup=cleanup),
        lambda _error: _maintenance_failed(window),
    )
    if not accepted:
        _set_busy(window, False)
        window.client_maintenance_feedback.setText(
            "Kończę inne sprawdzanie. Spróbuj ponownie za chwilę."
        )


def _maintenance_done(window: Any, result: object, *, cleanup: bool) -> None:
    _set_busy(window, False)
    value = dict(result) if isinstance(result, dict) else {}
    if cleanup:
        text = (
            f"Gotowe. Odzyskano {_size(value.get('saved_bytes', 0))}; "
            f"usunięte stare zrzuty: "
            f"{int(value.get('removed_screenshots', 0) or 0)}; cache: "
            f"{int(value.get('removed_cache_files', 0) or 0)} plików."
        )
    else:
        text = (
            f"Dane JARVIS: {_size(value.get('data_bytes', 0))}; wolne na "
            f"dysku: {_size(value.get('disk_free_bytes', 0))}."
        )
    window.client_maintenance_feedback.setText(text)


def _maintenance_failed(window: Any) -> None:
    _set_busy(window, False)
    window.client_maintenance_feedback.setText(
        "Nie udało się zakończyć kontroli. Dane pozostały bez zmian."
    )


def _run_autostart(window: Any, *, enabled: bool | None) -> None:
    _set_autostart_busy(window, True)
    if enabled is None:
        operation = autostart_status
    else:
        operation = lambda: set_autostart(
            window.controller.project_root, enabled=enabled
        )
    accepted = submit_client_read(
        window,
        operation,
        lambda result: _autostart_done(window, result),
        lambda _error: _autostart_failed(window),
    )
    if not accepted:
        _set_autostart_busy(window, False)
        window.client_autostart_feedback.setText(
            "Kończę inną kontrolę. Stan odświeży się przy kolejnym otwarciu."
        )


def _autostart_done(window: Any, result: object) -> None:
    _set_autostart_busy(window, False)
    value = dict(result) if isinstance(result, dict) else {}
    if not value.get("supported", True):
        text = "Autostart jest dostępny na komputerze z Windows."
    elif value.get("installed"):
        state = str(value.get("state") or "READY").upper()
        state_label = "działa" if state == "RUNNING" else "gotowy"
        text = f"Autostart: WŁĄCZONY — {state_label}."
    else:
        text = "Autostart: WYŁĄCZONY."
    window.client_autostart_feedback.setText(text)


def _autostart_failed(window: Any) -> None:
    _set_autostart_busy(window, False)
    window.client_autostart_feedback.setText(
        "Nie udało się sprawdzić autostartu. Ustawienie nie zostało zmienione."
    )


def _set_autostart_busy(window: Any, busy: bool) -> None:
    window.client_autostart_on.setDisabled(busy)
    window.client_autostart_off.setDisabled(busy)
    if busy:
        window.client_autostart_feedback.setText("Sprawdzam autostart w tle…")


def _set_busy(window: Any, busy: bool) -> None:
    window.client_health_button.setDisabled(busy)
    window.client_cleanup_button.setDisabled(busy)
    if busy:
        window.client_maintenance_feedback.setText("Sprawdzam w tle…")


def _store(window: Any) -> BusinessConfigStore:
    candidate = getattr(getattr(window, "owner_window", None), "config_store", None)
    return candidate or BusinessConfigStore(window.controller.project_root)


def _combo(items: tuple[tuple[str, Any], ...]) -> QComboBox:
    combo = QComboBox()
    for label, value in items:
        combo.addItem(label, value)
    return combo


def _select(combo: QComboBox, value: object) -> None:
    combo.setCurrentIndex(max(0, combo.findData(value)))


def _size(value: object) -> str:
    amount = max(0, int(value or 0))
    if amount >= 1024**3:
        return f"{amount / 1024**3:.1f} GB"
    if amount >= 1024**2:
        return f"{amount / 1024**2:.1f} MB"
    return f"{amount / 1024:.1f} KB"


__all__ = [
    "install_client_settings_controls", "save_client_settings_controls",
    "show_client_settings_controls",
]
