from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from PySide6.QtCore import QObject

from app.assistant.fast_local_commands import (
    FastLocalCommandService,
    is_fast_local_read,
)
from app.gui.owner_background_commands import OwnerBackgroundCommandRuntime
from app.gui.client_background_commands import (
    ClientBackgroundCommandRuntime,
    _Job,
)
from app.gui.client_busy_feedback import publish_client_busy
from app.gui.client_command_progress import ClientCommandProgress


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


def test_client_runtime_never_queues_a_second_command() -> None:
    window = QObject()
    runtime = ClientBackgroundCommandRuntime(window)
    occupied = object()
    runtime._jobs.add(occupied)  # type: ignore[arg-type]

    accepted = runtime.plan("Która jest godzina?")

    assert accepted is False
    assert runtime.busy is True
    assert runtime._jobs == {occupied}
    runtime.shutdown()


def test_closed_client_runtime_rejects_new_work() -> None:
    window = QObject()
    runtime = ClientBackgroundCommandRuntime(window)
    runtime.shutdown()

    assert runtime.plan("Która jest godzina?") is False
    assert runtime.execute({"handler": "personal_assistant"}) is False
    assert runtime.busy is False


def test_client_busy_feedback_reports_that_command_was_not_queued() -> None:
    events: list[dict] = []
    window = SimpleNamespace(
        _publish_client_event=lambda **event: events.append(event)
    )

    publish_client_busy(window)
    publish_client_busy(window, confirmed=True)

    assert events[0]["state"] == "warning"
    assert events[0]["progress"] == 18
    assert "nie dodałem tego polecenia" in events[0]["message"]
    assert events[1]["progress"] == 60
    assert "Zatwierdzone działanie" in events[1]["message"]


def test_client_command_progress_reports_liveness_without_finishing() -> None:
    events: list[dict] = []
    now = [100.0]
    window = QObject()
    window._publish_client_event = lambda **event: events.append(event)
    progress = ClientCommandProgress(
        window,
        interval_ms=30_000,
        clock=lambda: now[0],
    )

    progress.start("planning")
    now[0] = 112.0
    progress._tick()
    progress.start("executing")
    now[0] = 130.0
    progress._tick()
    progress.start("chatting")
    now[0] = 145.0
    progress._tick()
    progress.stop()
    progress._tick()

    assert events[0] == {
        "state": "thinking",
        "message": "Nadal analizuję polecenie — 12 s.",
        "progress": 24,
    }
    assert events[1] == {
        "state": "acting",
        "message": "Nadal wykonuję i sprawdzam zadanie — 18 s.",
        "progress": 64,
    }
    assert events[2] == {
        "state": "thinking",
        "message": "Nadal układam lokalną odpowiedź — 15 s.",
        "progress": 57,
    }
    assert all(event["progress"] < 100 for event in events)
    assert progress.active is False


def test_client_command_progress_rejects_unknown_phase() -> None:
    window = QObject()
    progress = ClientCommandProgress(window)

    try:
        progress.start("unknown")
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("unknown progress phase must be rejected")


def test_client_runtime_stops_progress_before_completion_callback() -> None:
    completed: list[str] = []
    window = QObject()
    runtime = ClientBackgroundCommandRuntime(window)
    job = _Job(lambda: "done")
    runtime._jobs.add(job)
    runtime._callbacks[job] = lambda result: completed.append(result)
    runtime.progress.start("planning")

    runtime._complete(job, "done")

    assert runtime.progress.active is False
    assert runtime.busy is False
    assert completed == ["done"]
    runtime.shutdown()
