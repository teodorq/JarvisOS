from __future__ import annotations

from typing import Any

from app.ai.unified_intent_router import DEFAULT_INTENT_ROUTER

from .autonomous_work_service import AutonomousWorkService


_HANDLERS = {
    "autodev_campaign_start": "autonomous_work_start",
    "autodev_campaign_status": "autonomous_work_status",
    "autodev_campaign_resume": "autonomous_work_resume",
    "autodev_campaign_cancel": "autonomous_work_cancel",
    "autodev_campaign_review": "autonomous_work_review",
    "autodev_campaign_discard_patch": "autonomous_work_discard_patch",
    "autodev_deployment_blocked": "autonomous_work_deployment_blocked",
}


def plan_autonomous_work_command(
    brain: Any,
    command: str,
) -> dict[str, Any] | None:
    """Plan multi-task AutoDev through the shared concept router."""
    decision = DEFAULT_INTENT_ROUTER.route(command)
    if decision is None or decision.intent not in _HANDLERS:
        return None
    handler = _HANDLERS[decision.intent]
    blocked = handler == "autonomous_work_deployment_blocked"
    read_only = handler in {"autonomous_work_status", "autonomous_work_review"}
    return {
        "command": str(command),
        "goal": (
            "Bezpiecznie zatrzymać automatyczne wdrożenie"
            if blocked
            else "Prowadzić wielozadaniową kampanię rozwoju na izolowanych kopiach"
        ),
        "plan": _plan(handler),
        "actions": [],
        "can_execute": True,
        "handler": handler,
        "intent": decision.to_dict(),
        "requires_confirmation": False,
        "read_only": read_only,
        "workspace_only": not read_only,
        "project_write": False,
        "background": bool(decision.entities.get("background", False)),
        "auto_approve": False,
        "auto_deploy": False,
    }


def execute_autonomous_work_command(
    brain: Any,
    thought: dict[str, Any],
) -> str:
    handler = str(thought.get("handler", ""))
    if handler == "autonomous_work_deployment_blocked":
        message = (
            "Nie uruchomiłem wdrożenia. Mogę samodzielnie analizować projekt, "
            "tworzyć backlog, przygotowywać patche i testować je na kopiach, "
            "ale każda zmiana zatrzyma się przed instalacją."
        )
        return _remember(brain, thought, message)
    service = getattr(brain, "autonomous_work_service", None)
    if not isinstance(service, AutonomousWorkService):
        service = AutonomousWorkService(getattr(brain, "project_root", None))
        setattr(brain, "autonomous_work_service", service)
    intent = dict(thought.get("intent", {}) or {})
    entities = dict(intent.get("entities", {}) or {})
    if handler == "autonomous_work_start":
        result = service.start(
            max_tasks=int(entities.get("max_tasks", 5) or 5),
            background=True,
        )
    elif handler == "autonomous_work_status":
        result = service.status()
    elif handler == "autonomous_work_resume":
        result = service.resume(background=True)
    elif handler == "autonomous_work_cancel":
        result = service.cancel()
    elif handler == "autonomous_work_review":
        patch_index = entities.get("patch_index")
        result = service.review(
            patch_index=int(patch_index) if patch_index is not None else None
        )
    elif handler == "autonomous_work_discard_patch":
        patch_index = entities.get("patch_index")
        result = service.discard_patch(
            patch_index=int(patch_index) if patch_index is not None else None
        )
    else:
        result = {
            "message": "Nie rozpoznałem operacji kampanii AutoDev 3."
        }
    message = str(result.get("message", "")).strip() or (
        f"Kampania AutoDev ma status {result.get('status', 'UNKNOWN')}."
    )
    return _remember(brain, thought, message)


def _plan(handler: str) -> list[str]:
    if handler == "autonomous_work_review":
        return [
            "Powiązać każdą poprawkę z dokładną sesją",
            "Sprawdzić aktualność źródła i integralność artefaktów",
            "Wykryć konflikty między poprawkami",
            "Pokazać wynik bez wdrażania",
        ]
    if handler == "autonomous_work_discard_patch":
        return [
            "Wskazać dokładnie jedną poprawkę kampanii",
            "Potwierdzić jej przynależność do kampanii",
            "Usunąć wyłącznie jej izolowany workspace",
        ]
    if handler == "autonomous_work_status":
        return ["Odczytać trwały checkpoint", "Pokazać postęp i ryzyko"]
    if handler == "autonomous_work_resume":
        return ["Odzyskać przerwany stan", "Wznowić bez duplikowania patcha"]
    if handler == "autonomous_work_cancel":
        return ["Zatrzymać kolejne zadania", "Pozostawić działający projekt bez zmian"]
    if handler == "autonomous_work_deployment_blocked":
        return ["Zablokować wdrożenie", "Pozostawić patche do osobnej decyzji"]
    return [
        "Przeskanować projekt i utworzyć wartościowy backlog",
        "Uszeregować zadania według wartości, ryzyka i pewności",
        "Przygotowywać kolejne patche na osobnych kopiach",
        "Uruchamiać walidację statyczną, importy i testy celowane",
        "Zapisywać checkpoint po każdym zadaniu",
        "Zatrzymać wszystkie patche przed wdrożeniem",
    ]


def _remember(brain: Any, thought: dict[str, Any], message: str) -> str:
    remember = getattr(brain, "_remember_execution", None)
    if callable(remember):
        remember(str(thought.get("command", "")), message)
    return message
