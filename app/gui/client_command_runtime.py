from __future__ import annotations

from PySide6.QtCore import QTimer

from app.gui.client_capability_policy import ClientCapabilityPolicy, enforce_client_outcome
from app.gui.client_execution_scope import approve_client_thought, executable_client_thought, scope_client_thought
from app.jarvis_experience.isolation import ClientIsolationPolicy
from app.jarvis_experience.smart_task_loop import SmartTaskLoop, TaskOutcome
from app.gui.active_resolution_priority import active_resolution_priority_thought
from app.gui.client_external_activity import (
    open_external_companion, open_result_companion, view_mode_for_thought,
)
from app.gui.confirmed_calendar_execution import execute_confirmed_calendar_plan
from app.gui.client_result_formatter import ClientResultFormatter
from app.natural_actions.revisions import rebuild_command
from app.natural_actions.validation import classify_confirmation
from app.gui.repeated_confirmation import (
    remember_confirmed_calendar_write, repeated_calendar_confirmation,
)

class ClientCommandRuntimeMixin:
    """Isolated command channel used only by the client experience."""

    def _publish_client_event(self, **event) -> None:
        signal = getattr(self, "client_event_signal", None)
        if signal is not None:
            signal.emit(ClientIsolationPolicy.sanitize_event(event))
    def _client_task_loop(self, *, confirmed: bool = False) -> SmartTaskLoop:
        if confirmed:
            authorizer = lambda command, read_only: {"allowed": True}
        else:
            authorizer = lambda command, read_only: (
                self.business_service.access_control.authorize(
                    command, read_only=read_only,
                )
            )
        return SmartTaskLoop(self.brain, authorizer, self.is_safe_thought)

    def _client_background(self):
        runtime = getattr(self, "_client_background_commands", None)
        if runtime is None:
            from app.gui.client_background_commands import ClientBackgroundCommandRuntime
            runtime = ClientBackgroundCommandRuntime(self)
            self._client_background_commands = runtime
        return runtime

    def process_client_command(self, text: str) -> None:
        """Run a client command without exposing it in the owner console."""
        value = " ".join(str(text or "").split())
        if not value:
            return
        if self.pending_thought is not None:
            self._handle_client_confirmation(value)
            return
        denial = ClientCapabilityPolicy.denial_message(value)
        if denial:
            self._publish_client_event(
                state="error", message=denial, progress=100,
            )
            self.say_safe(denial)
            return
        repeated = repeated_calendar_confirmation(self, value)
        if repeated is not None:
            self._publish_client_event(
                state="acting",
                message="Sprawdzam, czy ta zmiana została już wykonana.",
                progress=60,
            )
            QTimer.singleShot(80, lambda planned=scope_client_thought(self, repeated): self._execute_client_thought(planned))
            return
        self._publish_client_event(
            state="thinking",
            message="Rozumiem cel i wybieram najlepszy sposób działania.",
            progress=18,
        )
        if getattr(self, "_client_async_enabled", False):
            self._client_background().plan(value)
            return
        priority = active_resolution_priority_thought(self, value)
        if priority is None:
            outcome = self._client_task_loop().plan(value)
        else:
            try:
                authorization = self.business_service.access_control.authorize(
                    value, read_only=False,
                )
                allowed = bool(authorization.get("allowed", False))
            except Exception:
                allowed = False
            outcome = TaskOutcome(
                "CONFIRM" if allowed else "DENIED",
                (str(priority.get("confirmation_message") or (
                    "To działanie wymaga Twojego potwierdzenia."
                )) if allowed else
                 "Nie mam uprawnień do wykonania tego działania."),
                allowed, dict(priority),
            )
        outcome = enforce_client_outcome(outcome)
        if outcome.requires_confirmation:
            self.pending_thought = scope_client_thought(self, outcome.thought)
            self._publish_client_event(
                state="warning", message=outcome.message, progress=45,
                requires_confirmation=True,
            )
            self.say_safe("Potwierdź wykonanie.")
            return
        if outcome.status != "READY" or outcome.thought is None:
            self._finish_client_outcome(outcome)
            return
        self._publish_client_event(
            state="acting", message="Wykonuję zadanie i sprawdzam rezultat.",
            progress=58,
            view_mode=view_mode_for_thought(outcome.thought),
        )
        thought = scope_client_thought(self, outcome.thought)
        QTimer.singleShot(170, lambda planned=thought: self._execute_client_thought(planned))

    def _execute_client_thought(self, thought: dict) -> None:
        if not approve_client_thought(self, thought):
            return
        if getattr(self, "_client_async_enabled", False):
            self._client_background().execute(thought)
            return
        open_external_companion(self, thought)
        outcome = self._client_task_loop(confirmed=True).execute(
            executable_client_thought(thought),
            executor=lambda planned: execute_confirmed_calendar_plan(self, planned),
        )
        if outcome.status == "COMPLETED":
            remember_confirmed_calendar_write(self, thought)
            open_result_companion(self, thought)
        self._finish_client_outcome(outcome)

    def _finish_client_outcome(self, outcome) -> None:
        state = "success" if outcome.status == "COMPLETED" else "error"
        presentation = ClientResultFormatter.for_outcome(outcome, state)
        self._publish_client_event(state=state, message=outcome.message, progress=100, result_type=presentation.kind)
        self.say_safe(presentation.spoken)

    def _handle_client_confirmation(self, answer: str) -> None:
        if (pending := self.pending_thought) is None or not approve_client_thought(self, pending):
            return
        decision = classify_confirmation(answer)
        if decision.kind == "accept":
            remember_confirmed_calendar_write(self, pending)
            self.pending_thought = None
            self._publish_client_event(
                state="acting",
                message="Wykonuję zatwierdzone zadanie i sprawdzam rezultat.",
                progress=60,
                view_mode=view_mode_for_thought(pending),
            )
            thought = dict(pending)
            QTimer.singleShot(170, lambda planned=thought: self._execute_client_thought(planned))
            return
        if decision.kind == "reject":
            self.pending_thought = None
            self._publish_client_event(
                state="idle", message="Anulowałem działanie.", progress=0,
            )
            self.say_safe("Anulowano")
            return
        revised = rebuild_command(dict(pending), decision.text)
        if not revised:
            self._publish_client_event(
                state="warning",
                message=("Nie zrozumiałem poprawki. Powiedz TAK, NIE albo "
                         "podaj konkretną zmianę."),
                progress=45, requires_confirmation=True,
            )
            return
        self.pending_thought = None
        self._publish_client_event(
            state="thinking",
            message="Uwzględniam poprawkę i przygotowuję nowy plan.",
            progress=28,
        )
        QTimer.singleShot(80, lambda command=revised: self.process_client_command(command))
