from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.gui.active_resolution_priority import active_resolution_priority_thought
from app.gui.command_safety import (
    is_safe_read_only_thought,
    is_safe_workspace_preparation_thought,
)
from app.gui.confirmed_calendar_execution import execute_confirmed_calendar_plan
from app.gui.self_improvement_advisor import self_improvement_advice
from app.gui.self_development_console import SelfDevelopmentConsoleSession


class _OwnerJobSignals(QObject):
    done = Signal(object, object)
    failed = Signal(object, object)


class _OwnerJob(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = _OwnerJobSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self, self.function())
        except Exception as error:
            self.signals.failed.emit(self, error)


class OwnerBackgroundCommandRuntime(QObject):
    """One background lane for owner planning and execution."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._job: _OwnerJob | None = None
        self._callback: Callable[[Any], None] | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._job is not None

    def plan(self, command: str) -> None:
        if self.busy:
            self._show_busy()
            return
        self.window.console_page.set_state("ANALIZUJĘ POLECENIE", "accent")
        self._submit(lambda: self._plan(command), self._after_plan)

    def execute(self, thought: dict[str, Any]) -> None:
        if self.busy:
            self._show_busy()
            return
        planned = dict(thought)
        self.window.console_page.set_state("WYKONUJĘ I SPRAWDZAM", "accent")
        development = SelfDevelopmentConsoleSession.start(
            getattr(self.window, "project_root", None), planned
        )

        def perform() -> object:
            if development is not None:
                development.publish(
                    "WYKONANIE",
                    "Python wykonuje rzeczywistą operację i zapisuje jej wynik.",
                )
            try:
                response = execute_confirmed_calendar_plan(
                    self.window, planned
                )
            except Exception as error:
                if development is not None:
                    development.publish(
                        "BŁĄD", type(error).__name__, terminal=True
                    )
                raise
            if development is not None:
                development.publish("GOTOWE", response, terminal=True)
            return response

        self._submit(
            perform,
            self._after_execute,
        )

    def shutdown(self) -> None:
        self._closed = True
        self._callback = None
        self.pool.clear()
        self.pool.waitForDone(800)

    def _plan(self, command: str) -> tuple[str, dict[str, Any]]:
        if advice := self_improvement_advice(self.window, command):
            return command, {
                "handler": "self_improvement_advice", "message": advice,
            }
        priority = active_resolution_priority_thought(self.window, command)
        thought = priority if priority is not None else self.window.brain.think(command)
        return command, dict(thought or {})

    def _after_plan(self, result: tuple[str, dict[str, Any]]) -> None:
        command, thought = result
        if thought.get("handler") == "self_improvement_advice":
            message = str(thought.get("message", ""))
            self.window.console_page.append(f"Jarvis: {message}")
            self.window.console_page.set_state("GOTOWY NA POLECENIE", "healthy")
            self.window.say_safe(message)
            return
        self.window.console_page.append("Jarvis: Oto co zrobię:")
        for step in thought.get("plan", []):
            self.window.console_page.append(f"• {step}")
        if not thought.get("can_execute", False):
            self.window.console_page.append("Jarvis: Nie mogę bezpiecznie wykonać tej akcji.")
            self.window.console_page.set_state("POLECENIE ODRZUCONE", "danger")
            return
        read_only = (
            is_safe_read_only_thought(thought)
            or is_safe_workspace_preparation_thought(thought)
        )
        authorization = self.window.business_service.access_control.authorize(
            command, read_only=read_only
        )
        if not authorization.get("allowed", False):
            reason = str(authorization.get("reason", "brak uprawnienia"))
            self.window.console_page.append(f"Jarvis: Nie mam uprawnień: {reason}")
            self.window.console_page.set_state("ODMOWA UPRAWNIEŃ", "danger")
            return
        if self.window.is_safe_thought(thought):
            self.window._execute_thought(thought)
            return
        self.window.pending_thought = thought
        self.window.console_page.set_state("CZEKAM NA POTWIERDZENIE", "danger")
        confirmation = str(thought.get("confirmation_message", "")).strip()
        self.window.console_page.append(
            "Jarvis: " + (confirmation or (
                "To ważne działanie. Wpisz TAK, aby je wykonać, albo NIE, aby anulować."
            ))
        )
        self.window.say_safe("Potwierdź wykonanie.")

    def _after_execute(self, response: object) -> None:
        message = str(response or "Zadanie zostało zakończone.")
        self.window.console_page.append(f"Jarvis: {message}")
        self.window.console_page.set_state("GOTOWY NA POLECENIE", "healthy")
        self.window.say_safe(message)

    def _show_busy(self) -> None:
        self.window.console_page.append(
            "Jarvis: Kończę poprzednie zadanie. Za chwilę będę gotowy na kolejne."
        )
        self.window.console_page.set_state("KOŃCZĘ BIEŻĄCE ZADANIE", "accent")

    def _submit(
        self,
        function: Callable[[], Any],
        callback: Callable[[Any], None],
    ) -> None:
        job = _OwnerJob(function)
        self._job = job
        self._callback = callback
        job.signals.done.connect(self._complete)
        job.signals.failed.connect(self._failed)
        self.pool.start(job)

    @Slot(object, object)
    def _complete(self, job: _OwnerJob, result: Any) -> None:
        if job is not self._job:
            return
        callback = self._callback
        self._job = None
        self._callback = None
        if not self._closed and callable(callback):
            callback(result)

    @Slot(object, object)
    def _failed(self, job: _OwnerJob, error: object) -> None:
        if job is not self._job:
            return
        self._job = None
        self._callback = None
        if self._closed:
            return
        print("Owner command error:", repr(error))
        self.window.console_page.append(
            "Jarvis: Nie udało się zakończyć zadania. Możesz spróbować ponownie."
        )
        self.window.console_page.set_state("NIE UDAŁO SIĘ WYKONAĆ", "danger")


def _runtime(window: Any) -> OwnerBackgroundCommandRuntime:
    runtime = getattr(window, "_owner_background_commands", None)
    if runtime is None:
        runtime = OwnerBackgroundCommandRuntime(window)
        window._owner_background_commands = runtime
    return runtime


def start_owner_command(window: Any, command: str) -> bool:
    if not getattr(window, "_owner_async_enabled", False):
        return False
    _runtime(window).plan(command)
    return True


def execute_owner_thought(window: Any, thought: dict[str, Any]) -> bool:
    if not getattr(window, "_owner_async_enabled", False):
        return False
    _runtime(window).execute(thought)
    return True


def shutdown_owner_commands(window: Any) -> None:
    runtime = getattr(window, "_owner_background_commands", None)
    if runtime is not None:
        runtime.shutdown()
