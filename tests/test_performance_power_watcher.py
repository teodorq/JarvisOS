from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from app.core.performance_profile import BALANCED, LOW_RESOURCE
from app.gui.performance_power_watcher import PerformancePowerWatcher


APP = QApplication.instance() or QApplication([])


class _Owner(QObject):
    def __init__(self, root) -> None:
        super().__init__()
        self.project_root = root
        self.business_config = {"performance": {"profile": "auto"}}
        self.performance_profile = BALANCED


def test_auto_profile_reacts_to_power_change(tmp_path) -> None:
    owner = _Owner(tmp_path)
    watcher = PerformancePowerWatcher(owner)
    watcher.sync()
    assert watcher.timer.isActive()

    with patch(
        "app.gui.performance_power_watcher.load_performance_profile",
        return_value=LOW_RESOURCE,
    ), patch(
        "app.gui.performance_power_watcher.apply_runtime_preferences"
    ) as apply:
        watcher.check()

    apply.assert_called_once_with(owner)
    watcher.timer.stop()


def test_manual_profile_disables_power_polling(tmp_path) -> None:
    owner = _Owner(tmp_path)
    watcher = PerformancePowerWatcher(owner)
    watcher.sync()
    owner.business_config["performance"]["profile"] = "balanced"
    watcher.sync()

    assert not watcher.timer.isActive()
