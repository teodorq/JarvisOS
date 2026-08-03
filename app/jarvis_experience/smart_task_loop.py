from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from app.gui.command_safety import (
    is_safe_read_only_thought, is_safe_workspace_preparation_thought,
)
from app.jarvis_experience.isolation import ClientIsolationPolicy
from app.jarvis_experience.read_result_policy import sanitize_task_result
from app.natural_actions.calendar_plan_guard import CalendarPlanStaleError
from app.natural_actions.calendar_result_verifier import (
    CalendarResultVerificationError,
)

@dataclass(frozen=True)
class TaskOutcome:
    status: str
    message: str
    requires_confirmation: bool = False
    thought: dict[str, Any] | None = None

class SmartTaskLoop:
    """Goal -> plan -> authorization -> execution -> public result."""

    def __init__(
        self,
        brain: Any,
        authorizer: Callable[[str, bool], dict[str, Any]],
        safe_check: Callable[[dict], bool],
    ) -> None:
        self.brain = brain
        self.authorizer = authorizer
        self.safe_check = safe_check
    def plan(self, command: str) -> TaskOutcome:
        text = " ".join(str(command or "").split())
        if not text:
            return TaskOutcome("EMPTY", "Powiedz, czego potrzebujesz.")
        try:
            thought = self.brain.think(text)
        except Exception:
            return TaskOutcome(
                "FAILED",
                "Nie udało się teraz przeanalizować polecenia. Spróbuj ponownie.",
            )
        if not isinstance(thought, dict) or not thought.get("can_execute", False):
            return TaskOutcome(
                "REJECTED",
                "Nie mogę bezpiecznie wykonać tego polecenia.",
                thought=thought if isinstance(thought, dict) else None,
            )
        read_only = (
            is_safe_read_only_thought(thought)
            or is_safe_workspace_preparation_thought(thought)
        )
        try:
            authorization = self.authorizer(text, read_only)
        except Exception:
            authorization = {"allowed": False}
        if not isinstance(authorization, dict) or not authorization.get(
            "allowed", False
        ):
            return TaskOutcome(
                "DENIED",
                "Nie mam uprawnień do wykonania tego działania.",
                thought=thought,
            )
        try:
            safe = bool(self.safe_check(thought))
        except Exception:
            safe = False
        if not safe:
            return TaskOutcome(
                "CONFIRM",
                str(thought.get("confirmation_message") or "To działanie wymaga Twojego potwierdzenia."),
                True,
                thought,
            )
        return TaskOutcome(
            "READY",
            "Plan jest gotowy. Rozpoczynam wykonanie.",
            thought=thought,
        )

    def prepare(self, command: str) -> TaskOutcome:
        """Backward-compatible one-call flow used by existing integrations."""
        plan = self.plan(command)
        if plan.status != "READY" or plan.thought is None:
            return plan
        return self.execute(plan.thought)

    def execute(self, thought: dict[str, Any], *, executor: Callable | None = None) -> TaskOutcome:
        runner = executor if callable(executor) else self.brain.execute
        try:
            result = runner(thought)
        except CalendarPlanStaleError as error:
            message = ClientIsolationPolicy.sanitize_text(str(error))
            return TaskOutcome(
                "STALE_PLAN",
                message or (
                    "Plan zmiany kalendarza jest już nieaktualny. "
                    "Nie wykonałem zmiany."
                ),
                thought=thought,
            )
        except CalendarResultVerificationError as error:
            message = ClientIsolationPolicy.sanitize_text(str(error))
            return TaskOutcome(
                "CALENDAR_UNVERIFIED",
                message or "Nie mogę potwierdzić zmiany w Google Calendar.",
                thought=thought,
            )
        except Exception as error:
            message = ClientIsolationPolicy.sanitize_text(str(error))
            if type(error).__name__ != "OnlineAssistantError" or not message:
                message = "Nie udało się zakończyć zadania. Spróbuj ponownie."
            return TaskOutcome("FAILED", message, thought=thought)
        message = sanitize_task_result(result, thought)
        if not message:
            message = "Zadanie zostało zakończone."
        return TaskOutcome("COMPLETED", message, thought=thought)
