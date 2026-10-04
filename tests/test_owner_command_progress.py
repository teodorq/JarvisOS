from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QObject

from app.gui.owner_command_progress import OwnerCommandProgress
from app.gui.owner_background_commands import (
    OwnerBackgroundCommandRuntime,
    _OwnerJob,
)


def test_owner_progress_updates_only_the_status_bar() -> None:
    states: list[tuple[str, str]] = []
    now = [50.0]
    window = QObject()
    window.console_page = SimpleNamespace(
        set_state=lambda label, tone: states.append((label, tone))
    )
    progress = OwnerCommandProgress(
        window,
        interval_ms=30_000,
        clock=lambda: now[0],
    )

    progress.start("planning")
    now[0] = 57.0
    progress._tick()
    progress.start("executing")
    now[0] = 69.0
    progress._tick()
    progress.start("chatting")
    now[0] = 84.0
    progress._tick()
    progress.stop()
    progress._tick()

    assert states == [
        ("ANALIZUJĘ POLECENIE • 7 S", "accent"),
        ("WYKONUJĘ I SPRAWDZAM • 12 S", "accent"),
        ("UKŁADAM ODPOWIEDŹ LOKALNIE • 15 S", "accent"),
    ]
    assert progress.active is False


def test_owner_progress_rejects_unknown_phase() -> None:
    window = QObject()
    window.console_page = SimpleNamespace(set_state=lambda *_args: None)
    progress = OwnerCommandProgress(window)

    try:
        progress.start("unknown")
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("unknown progress phase must be rejected")


def test_owner_runtime_stops_progress_before_completion_callback() -> None:
    states: list[tuple[str, str]] = []
    completed: list[str] = []
    window = QObject()
    window.console_page = SimpleNamespace(
        set_state=lambda label, tone: states.append((label, tone)),
        append=lambda _message: None,
    )
    runtime = OwnerBackgroundCommandRuntime(window)
    job = _OwnerJob(lambda: "done")
    runtime._job = job
    runtime._callback = lambda result: completed.append(result)
    runtime.progress.start("planning")

    runtime._complete(job, "done")

    assert runtime.progress.active is False
    assert runtime.busy is False
    assert completed == ["done"]
    runtime.shutdown()
