from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from app.assistant.deferred_services import (
    DEFERRED_STAGES,
    LazyAssistantService,
    google_token_present,
)


def test_controller_start_does_not_load_deferred_suites() -> None:
    code = (
        "import sys; from app.assistant.controller import PersonalAssistantController; "
        "assistant=PersonalAssistantController('.'); "
        "assistant.set_progress_callback(lambda event: None); "
        "assert not assistant.productivity.loaded; "
        "assert not assistant.online.loaded; "
        "assert not assistant.natural_actions.loaded; "
        "assert 'app.online_assistant.controller' not in sys.modules; "
        "assert 'app.natural_actions.service' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr


def test_progress_callback_is_applied_when_service_loads() -> None:
    instance = Mock()
    service = LazyAssistantService(lambda: instance)
    callback = Mock()

    service.set_progress_callback(callback)
    assert not service.loaded
    service.status()

    instance.set_progress_callback.assert_called_once_with(callback)
    instance.status.assert_called_once_with()


def test_google_token_probe_needs_no_online_controller() -> None:
    with TemporaryDirectory() as directory:
        local = Path(directory)
        environment = {"LOCALAPPDATA": str(local)}
        token = local / "JARVIS_OS" / "secrets" / "google_workspace_token.json"

        assert not google_token_present(environment)
        token.parent.mkdir(parents=True)
        token.write_text("{}", encoding="utf-8")
        assert google_token_present(environment)


def test_deferred_stage_manifest_matches_real_services() -> None:
    from app.natural_actions import NaturalActionService
    from app.online_assistant import OnlineAssistantController
    from app.productivity import ProductivitySuiteController

    expected = {
        **ProductivitySuiteController.STAGES,
        **OnlineAssistantController.STAGES,
        **NaturalActionService.STAGES,
    }

    assert DEFERRED_STAGES == expected
