from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from PySide6.QtCore import QObject

from app.assistant.fast_local_commands import (
    FastLocalCommandService,
    is_fast_local_read,
)
from app.gui.owner_background_commands import OwnerBackgroundCommandRuntime
from app.gui.client_background_commands import ClientBackgroundCommandRuntime


def _thought(**updates) -> dict:
    value = {
        "handler": "personal_assistant",
        "assistant_intent": "current_time",
        "read_only": True,
        "can_execute": True,
        "actions": [],
        "used_context": False,
        "clarification": "",
    }
    value.update(updates)
    return value


class FakeAssistant:
    def __init__(self, thought: dict) -> None:
        self.thought = deepcopy(thought)
        self.handled: list[str] = []

    @staticmethod
    def matches(command: object) -> bool:
        return bool(str(command).strip())

    def plan(self, command: object) -> dict:
        return deepcopy(self.thought)

    def handle(self, command: object) -> str:
        self.handled.append(str(command))
        return "Teraz jest 12:34."


def test_verified_local_read_executes_once_after_authorization() -> None:
    assistant = FakeAssistant(_thought())
    calls: list[tuple[str, bool]] = []

    result = FastLocalCommandService.try_execute(
        assistant,
        "Która jest godzina?",
        authorize=lambda command, read_only: (
            calls.append((command, read_only)) or {"allowed": True}
        ),
    )

    assert result == {
        "handler": "fast_local_response",
        "assistant_intent": "current_time",
        "message": "Teraz jest 12:34.",
        "read_only": True,
    }
    assert calls == [("Która jest godzina?", True)]
    assert assistant.handled == ["Która jest godzina?"]


def test_write_network_context_and_action_plans_never_use_fast_path() -> None:
    rejected = (
        _thought(read_only=False),
        _thought(assistant_intent="weather"),
        _thought(used_context=True),
        _thought(actions=[{"action_type": "OPEN_APP"}]),
        _thought(requires_confirmation=True),
        _thought(natural_action=True),
    )

    for thought in rejected:
        assert is_fast_local_read(thought) is False
        assistant = FakeAssistant(thought)
        result = FastLocalCommandService.try_execute(
            assistant,
            "polecenie",
            authorize=lambda *_args, **_kwargs: {"allowed": True},
        )
        assert result is None
        assert assistant.handled == []


def test_denied_read_is_not_executed() -> None:
    assistant = FakeAssistant(_thought())

    result = FastLocalCommandService.try_execute(
        assistant,
        "Status asystenta",
        authorize=lambda *_args, **_kwargs: {
            "allowed": False,
            "reason": "tryb właściciela jest zablokowany",
        },
    )

    assert result == {
        "handler": "fast_local_denied",
        "message": (
            "Nie mam uprawnień: tryb właściciela jest zablokowany"
        ),
    }
    assert assistant.handled == []


def test_authorization_failure_is_fail_closed() -> None:
    assistant = FakeAssistant(_thought())

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("unavailable")

    result = FastLocalCommandService.try_execute(
        assistant,
        "Status asystenta",
        authorize=unavailable,
    )

    assert result == {
        "handler": "fast_local_denied",
        "message": "Nie udało się bezpiecznie sprawdzić uprawnień.",
    }
    assert assistant.handled == []


def test_owner_runtime_skips_general_brain_for_fast_local_read() -> None:
    class BrainMustNotRun:
        @staticmethod
        def think(_command: str) -> dict:
            raise AssertionError("general Brain planner must not run")

    window = QObject()
    window.assistant = FakeAssistant(_thought())
    window.business_service = SimpleNamespace(
        access_control=SimpleNamespace(
            authorize=lambda *_args, **_kwargs: {"allowed": True},
        )
    )
    window.brain = BrainMustNotRun()
    runtime = OwnerBackgroundCommandRuntime(window)

    command, result = runtime._plan("Która jest godzina?")
    runtime.shutdown()

    assert command == "Która jest godzina?"
    assert result["handler"] == "fast_local_response"
    assert result["message"] == "Teraz jest 12:34."
    assert window.assistant.handled == ["Która jest godzina?"]


def test_client_runtime_skips_task_loop_for_fast_local_read() -> None:
    window = QObject()
    window.assistant = FakeAssistant(_thought())
    window.business_service = SimpleNamespace(
        access_control=SimpleNamespace(
            authorize=lambda *_args, **_kwargs: {"allowed": True},
        )
    )
    window._client_task_loop = lambda: (_ for _ in ()).throw(
        AssertionError("client task loop must not run")
    )
    runtime = ClientBackgroundCommandRuntime(window)

    outcome = runtime._plan("Która jest godzina?")
    runtime.shutdown()

    assert outcome.status == "COMPLETED"
    assert outcome.message == "Teraz jest 12:34."
    assert window.assistant.handled == ["Która jest godzina?"]


def test_client_runtime_blocks_owner_command_before_fast_execution() -> None:
    window = QObject()
    window.assistant = FakeAssistant(_thought())
    window.business_service = SimpleNamespace(
        access_control=SimpleNamespace(
            authorize=lambda *_args, **_kwargs: {"allowed": True},
        )
    )
    runtime = ClientBackgroundCommandRuntime(window)

    outcome = runtime._plan("Status Forex")
    runtime.shutdown()

    assert outcome.status == "DENIED"
    assert "tylko w trybie właściciela" in outcome.message
    assert window.assistant.handled == []
