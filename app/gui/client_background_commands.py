from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.assistant.fast_local_commands import FastLocalCommandService
from app.gui.active_resolution_priority import active_resolution_priority_thought
from app.gui.confirmed_calendar_execution import execute_confirmed_calendar_plan
from app.gui.client_capability_policy import (
    ClientCapabilityPolicy,
    enforce_client_outcome,
)
from app.gui.client_execution_scope import (
    client_execution_denial, executable_client_thought, scope_client_thought,
)
from app.gui.client_external_activity import (
    open_external_companion, open_result_companion, view_mode_for_thought,
)
from app.gui.repeated_confirmation import remember_confirmed_calendar_write
from app.gui.self_improvement_advisor import self_improvement_advice
from app.jarvis_experience.smart_task_loop import TaskOutcome


class _JobSignals(QObject):
    done = Signal(object, object)
    failed = Signal(object, object)


class _Job(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = _JobSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self, self.function())
        except Exception as error:
            self.signals.failed.emit(self, error)


class ClientBackgroundCommandRuntime(QObject):
    """Single-worker command lane that keeps network and planning off the UI."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._jobs: set[_Job] = set()
        self._callbacks: dict[_Job, Callable[[Any], None]] = {}
        self._closed = False

    @property
    def busy(self) -> bool:
        return bool(self._jobs)

    def plan(self, command: str) -> bool:
        if self._closed or self.busy:
            return False
        self._submit(lambda: self._plan(command), self._after_plan)
        return True

    def execute(self, thought: dict[str, Any]) -> bool:
        if self._closed or self.busy:
            return False
        planned = dict(thought)
        self._submit(lambda: self._execute(planned), self._after_execute)
        return True

    def shutdown(self) -> None:
        self._closed = True
        self.pool.clear()
        self.pool.waitForDone(1500)
        self._jobs.clear()
        self._callbacks.clear()

    def _plan(self, command: str) -> TaskOutcome:
        if denial := ClientCapabilityPolicy.denial_message(command):
            return TaskOutcome("DENIED", denial)
        if advice := self_improvement_advice(self.window, command):
            return TaskOutcome("COMPLETED", advice)
        assistant = getattr(self.window, "assistant", None)
        access_control = getattr(
            getattr(self.window, "business_service", None),
            "access_control",
            None,
        )
        authorize = getattr(access_control, "authorize", None)
        if assistant is not None and callable(authorize):
            fast = FastLocalCommandService.try_execute(
                assistant,
                command,
                authorize=authorize,
            )
            if fast is not None:
                status = (
                    "COMPLETED"
                    if fast.get("handler") == "fast_local_response"
                    else "DENIED"
                )
                return TaskOutcome(status, str(fast.get("message", "")))
        priority = active_resolution_priority_thought(self.window, command)
        if priority is None:
            return self.window._client_task_loop().plan(command)
        try:
            authorization = self.window.business_service.access_control.authorize(
                command, read_only=False
            )
            allowed = bool(authorization.get("allowed", False))
        except Exception:
            allowed = False
        message = (
            str(priority.get("confirmation_message") or
                "To działanie wymaga Twojego potwierdzenia.")
            if allowed else "Nie mam uprawnień do wykonania tego działania."
        )
        return TaskOutcome(
            "CONFIRM" if allowed else "DENIED", message, allowed, dict(priority)
        )

    def _execute(self, thought: dict[str, Any]) -> TaskOutcome:
        denial = client_execution_denial(self.window, thought)
        if denial:
            return TaskOutcome("DENIED", denial, thought=thought)
        open_external_companion(self.window, thought)
        outcome = self.window._client_task_loop(confirmed=True).execute(
            executable_client_thought(thought),
            executor=lambda planned: execute_confirmed_calendar_plan(
                self.window, planned
            ),
        )
        if outcome.thought is None:
            return outcome
        return TaskOutcome(
            outcome.status, outcome.message, outcome.requires_confirmation,
            thought,
        )

    def _after_plan(self, outcome: TaskOutcome) -> None:
        outcome = enforce_client_outcome(outcome)
        if outcome.requires_confirmation:
            self.window.pending_thought = scope_client_thought(
                self.window, outcome.thought
            )
            self.window._publish_client_event(
                state="warning", message=outcome.message, progress=45,
                requires_confirmation=True,
            )
            self.window.say_safe("Potwierdź wykonanie.")
            return
        if outcome.status != "READY" or outcome.thought is None:
            self.window._finish_client_outcome(outcome)
            return
        self.window._publish_client_event(
            state="acting", message="Wykonuję zadanie i sprawdzam rezultat.",
            progress=58,
            view_mode=view_mode_for_thought(outcome.thought),
        )
        if not self.execute(
            scope_client_thought(self.window, outcome.thought)
        ):
            self.window._publish_client_event(
                state="warning",
                message="Kończę poprzednie zadanie. Spróbuj ponownie za chwilę.",
                progress=18,
            )

    def _after_execute(self, outcome: TaskOutcome) -> None:
        if outcome.status == "COMPLETED" and outcome.thought is not None:
            remember_confirmed_calendar_write(self.window, outcome.thought)
            open_result_companion(self.window, outcome.thought)
        self.window._finish_client_outcome(outcome)

    def _submit(
        self, function: Callable[[], Any], callback: Callable[[Any], None]
    ) -> None:
        job = _Job(function)
        self._jobs.add(job)
        self._callbacks[job] = callback
        job.signals.done.connect(self._complete)
        job.signals.failed.connect(self._failed)
        self.pool.start(job)

    @Slot(object, object)
    def _complete(self, job: _Job, result: Any) -> None:
        self._jobs.discard(job)
        callback = self._callbacks.pop(job, None)
        if not self._closed and callable(callback):
            callback(result)

    @Slot(object, object)
    def _failed(self, job: _Job, error: object) -> None:
        self._jobs.discard(job)
        self._callbacks.pop(job, None)
        if self._closed:
            return
        message = str(error).strip()
        if not message or any(marker in message.casefold() for marker in (
            "traceback", "exception", "c:" + "\\jarvisai", "/app/",
        )):
            message = "Nie udało się zakończyć zadania. Spróbuj ponownie."
        self.window._finish_client_outcome(TaskOutcome("FAILED", message))
