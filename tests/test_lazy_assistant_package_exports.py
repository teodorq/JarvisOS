from __future__ import annotations

import subprocess
import sys


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True,
    )


def test_optional_packages_do_not_import_controllers_eagerly() -> None:
    result = _run(
        "import sys; import app.natural_actions, app.online_assistant, app.productivity; "
        "assert 'app.natural_actions.service' not in sys.modules; "
        "assert 'app.online_assistant.controller' not in sys.modules; "
        "assert 'app.productivity.controller' not in sys.modules"
    )

    assert result.returncode == 0, result.stderr


def test_public_exports_remain_compatible() -> None:
    result = _run(
        "from app.natural_actions import NaturalActionService; "
        "from app.online_assistant import OnlineAssistantController; "
        "from app.productivity import ProductivitySuiteController, ReminderCenterV2; "
        "assert all((NaturalActionService, OnlineAssistantController, "
        "ProductivitySuiteController, ReminderCenterV2))"
    )

    assert result.returncode == 0, result.stderr
