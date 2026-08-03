from __future__ import annotations

from typing import Any

from app.natural_actions.calendar_plan_guard import CalendarPlanStaleError
from app.natural_actions.calendar_result_verifier import (
    CalendarResultVerificationError,
)
from app.natural_actions.revisions import rebuild_command
from app.natural_actions.validation import classify_confirmation
from app.gui.repeated_confirmation import remember_confirmed_calendar_write
from app.gui.confirmed_calendar_execution import execute_confirmed_calendar_plan


def handle_owner_confirmation(window: Any, answer: object) -> None:
    """Accept, reject or revise an owner-mode pending action safely."""
    pending = getattr(window, "pending_thought", None)
    if pending is None:
        return

    decision = classify_confirmation(answer)
    if decision.kind == "accept":
        remember_confirmed_calendar_write(window, pending)
        window.pending_thought = None
        if getattr(window, "_owner_async_enabled", False):
            window._execute_thought(pending)
            return
        try:
            response = execute_confirmed_calendar_plan(window, pending)
        except CalendarPlanStaleError as error:
            message = str(error)
            window.console_page.append(f"Jarvis: {message}")
            window.console_page.set_state("PLAN NIEAKTUALNY", "danger")
            window.say_safe(message)
            return
        except CalendarResultVerificationError as error:
            message = str(error)
            window.console_page.append(f"Jarvis: {message}")
            window.console_page.set_state("ZMIANA NIEPOTWIERDZONA", "danger")
            window.say_safe(message)
            return
        window.console_page.append(f"Jarvis: {response}")
        window.console_page.set_state("GOTOWY NA POLECENIE", "healthy")
        window.say_safe(response)
        return

    if decision.kind == "reject":
        window.pending_thought = None
        window.console_page.set_state("POLECENIE ANULOWANE", "neutral")
        window.console_page.append("Jarvis: Anulowano.")
        window.say_safe("Anulowano")
        return

    revised = rebuild_command(dict(pending), decision.text)
    if not revised:
        window.console_page.set_state(
            "OCZEKIWANIE NA POTWIERDZENIE",
            "danger",
        )
        window.console_page.append(
            "Jarvis: Nie zrozumiałem poprawki. Powiedz TAK, NIE albo "
            "podaj konkretną zmianę."
        )
        window.say_safe("Podaj konkretną zmianę")
        return

    window.pending_thought = None
    window.console_page.set_state("AKTUALIZACJA PLANU", "accent")
    window.console_page.append(
        f"Jarvis: Uwzględniam poprawkę. Nowe polecenie: {revised}"
    )
    window.process_command(revised, source="Ty")
