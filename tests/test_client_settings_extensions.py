from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from app.business.business_config import BusinessConfigStore
from app.gui.client_settings_extensions import (
    _run_maintenance,
    install_client_settings_controls,
    save_client_settings_controls,
    show_client_settings_controls,
)


def _window(tmp_path):
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    content = QVBoxLayout(host)
    store = BusinessConfigStore(tmp_path)
    owner = SimpleNamespace(config_store=store, business_config=store.ensure())
    window = SimpleNamespace(
        controller=SimpleNamespace(project_root=tmp_path),
        owner_window=owner,
    )
    install_client_settings_controls(window, content)
    host.show()
    app.processEvents()
    return app, host, window, store


def test_client_settings_are_loaded_and_saved(tmp_path) -> None:
    app, host, window, store = _window(tmp_path)

    with patch(
        "app.gui.client_settings_extensions.autostart_status",
        return_value={"supported": True, "installed": True, "state": "READY"},
    ):
        show_client_settings_controls(window)
    window.client_performance.setCurrentIndex(
        window.client_performance.findData("low_resource")
    )
    window.client_sounds.setCurrentIndex(
        window.client_sounds.findData(False)
    )
    window.client_desktop_notifications.setCurrentIndex(
        window.client_desktop_notifications.findData(False)
    )
    window.client_startup.setCurrentIndex(
        window.client_startup.findData("client")
    )
    window.client_start_minimized.setCurrentIndex(
        window.client_start_minimized.findData(True)
    )
    save_client_settings_controls(window)

    saved = store.ensure()
    assert saved["performance"]["profile"] == "low_resource"
    assert saved["sound"]["effects_enabled"] is False
    assert saved["notifications"]["desktop_enabled"] is False
    assert saved["ui"]["startup_mode"] == "client"
    assert saved["ui"]["start_minimized"] is True
    assert window.owner_window.business_config == saved
    assert window.client_autostart_feedback.text() == (
        "Autostart: WŁĄCZONY — gotowy."
    )
    host.close()
    app.processEvents()


def test_client_storage_status_submits_a_real_operation(tmp_path) -> None:
    _app, host, window, _store = _window(tmp_path)

    with patch(
        "app.gui.client_settings_extensions.submit_client_read",
        return_value=True,
    ) as submit:
        _run_maintenance(window, cleanup=False)

    operation = submit.call_args.args[1]
    result = operation()
    assert isinstance(result, dict)
    assert "disk_free_bytes" in result
    host.close()
