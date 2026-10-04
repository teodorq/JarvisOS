from __future__ import annotations

from typing import Any

from app.assistant.free_conversation import FreeConversationService


_ATTRIBUTE = "_free_conversation_service"


def plan_free_conversation(brain: Any, command: object) -> dict[str, Any] | None:
    service = _service(brain)
    return service.plan(command) if service.matches(command) else None


def execute_free_conversation(brain: Any, command: object) -> str:
    return _service(brain).reply(command)


def _service(brain: Any) -> FreeConversationService:
    service = getattr(brain, _ATTRIBUTE, None)
    if service is None:
        service = FreeConversationService(getattr(brain, "project_root", None))
        setattr(brain, _ATTRIBUTE, service)
    return service


__all__ = ["execute_free_conversation", "plan_free_conversation"]
