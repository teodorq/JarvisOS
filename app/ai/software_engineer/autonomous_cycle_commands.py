from __future__ import annotations

from typing import Any

from app.ai.unified_intent_router import DEFAULT_INTENT_ROUTER

from .autonomous_cycle_service import AutonomousBacklogCycleService


def plan_autonomous_cycle_command(
    brain: Any,
    command: str,
) -> dict[str, Any] | None:
    """Route a single B211-B220 cycle through the unified intent router."""
    decision = DEFAULT_INTENT_ROUTER.route(command)
    if decision is None:
        return None
    if decision.intent == "autodev_cycle_run":
        return _thought(
            command,
            "autonomous_cycle_run",
            "Samodzielnie wybrać jedno bezpieczne zadanie z backlogu",
            [
                "Odczytać backlog bez jego modyfikowania",
                "Odrzucić zadania aktywne, stare, ryzykowne i nieobsługiwane",
                "Uszeregować kandydatów według wartości, ryzyka i pewności",
                "Zająć dokładnie jedno zadanie ograniczoną dzierżawą",
                "Przygotować patch i testy na izolowanej kopii",
                "Zatrzymać się w stanie gotowym do osobnej decyzji o wdrożeniu",
            ],
            intent=decision.to_dict(),
        )
    if decision.intent == "autodev_cycle_status":
        return _thought(
            command,
            "autonomous_cycle_status",
            "Pokazać stan autonomicznego cyklu AutoDev 2.1",
            ["Odczytać trwały rejestr cyklu", "Zsynchronizować stan poprawki"],
            read_only=True,
            intent=decision.to_dict(),
        )
    if decision.intent == "autodev_cycle_resume":
        return _thought(
            command,
            "autonomous_cycle_resume",
            "Bezpiecznie wznowić ostatni cykl AutoDev 2.1",
            ["Odzyskać stan", "Nie duplikować gotowej poprawki", "Wznowić tylko brakujący etap"],
            intent=decision.to_dict(),
        )
    if decision.intent == "autodev_cycle_cancel":
        return _thought(
            command,
            "autonomous_cycle_cancel",
            "Anulować niewdrożony cykl AutoDev 2.1",
            ["Odnaleźć aktywny cykl", "Usunąć tylko izolowany workspace", "Zwolnić dzierżawę zadania"],
            intent=decision.to_dict(),
        )
    return None


def execute_autonomous_cycle_command(
    brain: Any,
    thought: dict[str, Any],
) -> str:
    service = getattr(brain, "autonomous_backlog_cycle_service", None)
    if not isinstance(service, AutonomousBacklogCycleService):
        service = AutonomousBacklogCycleService(getattr(brain, "project_root", None))
        setattr(brain, "autonomous_backlog_cycle_service", service)
    handler = str(thought.get("handler", ""))
    if handler == "autonomous_cycle_run":
        result = service.run_one()
    elif handler == "autonomous_cycle_status":
        result = service.status()
    elif handler == "autonomous_cycle_resume":
        result = service.resume()
    elif handler == "autonomous_cycle_cancel":
        result = service.cancel()
    else:
        result = {"message": "Nie rozpoznałem operacji autonomicznego cyklu AutoDev."}
    message = str(result.get("message", "")).strip() or "Cykl AutoDev został obsłużony."
    remember = getattr(brain, "_remember_execution", None)
    if callable(remember):
        remember(str(thought.get("command", "")), message)
    return message


def _thought(
    command: str,
    handler: str,
    goal: str,
    plan: list[str],
    *,
    read_only: bool = False,
    intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "command": str(command),
        "goal": goal,
        "plan": plan,
        "actions": [],
        "can_execute": True,
        "handler": handler,
        "intent": dict(intent or {}),
        "requires_confirmation": False,
        "read_only": read_only,
        "workspace_only": not read_only,
        "project_write": False,
        "auto_approve": False,
        "auto_deploy": False,
    }
