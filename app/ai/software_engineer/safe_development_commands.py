from __future__ import annotations

import unicodedata
from typing import Any

from .safe_autonomous_development_service import SafeAutonomousDevelopmentService


_PREPARE_MARKERS = (
    "przygotuj bezpieczna poprawke",
    "przygotuj jedna bezpieczna poprawke",
    "przygotuj poprawke na kopii",
    "przygotuj poprawke w izolowanej kopii",
    "przygotuj przetestowana poprawke",
    "zbuduj bezpieczny patch",
    "przygotuj patch ale go nie wdrazaj",
    "przygotuj realna poprawke ale niczego nie wdrazaj",
)
_PREPARE_ACTIONS = ("przygotuj", "zbuduj", "stworz")
_PREPARE_OBJECTS = ("poprawke", "patch", "zmiane")
_PREPARE_ISOLATION = (
    "izolowanej kopii",
    "izolowanej kopii roboczej",
    "na kopii",
    "w bezpiecznym workspace",
)
_PREPARE_NO_DEPLOY = (
    "nie wdrazaj",
    "niczego jeszcze nie wdrazaj",
    "bez wdrazania",
    "zostaw do decyzji",
)
_DEPLOY_MARKERS = (
    "wdroz przygotowana poprawke",
    "wdroz ten patch",
    "zastosuj przygotowana poprawke",
    "wgraj przygotowana poprawke",
)
_STATUS_MARKERS = (
    "status przygotowanej poprawki",
    "jaki jest status poprawki autodev",
    "pokaz przygotowana poprawke",
    "co przygotowal autodev",
)
_DISCARD_MARKERS = (
    "odrzuc przygotowana poprawke",
    "usun przygotowany patch",
    "anuluj przygotowana poprawke",
)
_ROLLBACK_MARKERS = (
    "cofnij ostatnia poprawke autodev",
    "cofnij ostatnia poprawke projektu",
    "cofnij ostatnia poprawke",
    "cofnij wdrozona poprawke",
    "wycofaj ostatnia poprawke autodev",
    "wycofaj ostatnia poprawke projektu",
    "przywroc wersje sprzed poprawki autodev",
    "przywroc projekt sprzed ostatniej poprawki",
)
_ROLLBACK_ACTIONS = ("cofnij", "wycofaj", "przywroc")
_ROLLBACK_OBJECTS = (
    "ostatnia poprawke", "wdrozona poprawke", "poprawke projektu",
    "poprawke autodev", "patch autodev",
)
_ROLLBACK_EXCLUSIONS = ("kalendarz", "spotkanie", "wydarzenie", "termin")


def plan_safe_development_command(
    brain: Any,
    command: str,
) -> dict[str, Any] | None:
    """Return an exact B201-B210 thought before broad legacy AutoDev routes."""
    normalized = _normalize(command)
    if _is_prepare_command(normalized):
        return {
            "command": str(command),
            "goal": "Przygotować i sprawdzić jedną zmianę na izolowanej kopii",
            "plan": [
                "Wybrać jedną deterministyczną poprawkę",
                "Utworzyć izolowaną kopię roboczą projektu",
                "Wygenerować dokładny diff dla jednego pliku",
                "Sprawdzić składnię, import, API i niedozwolone operacje",
                "Uruchomić ukierunkowane testy na kopii",
                "Zapisać gotową poprawkę bez wdrażania",
            ],
            "actions": [],
            "can_execute": True,
            "handler": "safe_development_prepare",
            "safe_preparation": True,
            "workspace_only": True,
            "project_write": False,
            "requires_confirmation": False,
        }
    if _contains(normalized, _DEPLOY_MARKERS):
        planned = _service(brain).plan_deploy()
        return _confirmed_thought(
            command,
            "safe_development_deploy",
            planned,
            [
                "Sprawdzić tożsamość i aktualność przygotowanego patcha",
                "Utworzyć zweryfikowaną kopię źródła",
                "Wdrożyć atomowo dokładnie jeden plik",
                "Uruchomić walidację po wdrożeniu",
                "Automatycznie cofnąć zmianę przy błędzie",
            ],
        )
    if _is_rollback_command(normalized):
        planned = _service(brain).plan_rollback()
        return _confirmed_thought(
            command,
            "safe_development_rollback",
            planned,
            [
                "Sprawdzić dokładną sesję wdrożenia",
                "Zweryfikować, że plik nie ma nowszych zmian",
                "Przywrócić kopię sprzed wdrożenia",
                "Potwierdzić hash przywróconego pliku",
            ],
        )
    if _contains(normalized, _DISCARD_MARKERS):
        return {
            "command": str(command),
            "goal": "Odrzucić niewdrożoną poprawkę z izolowanego workspace",
            "plan": [
                "Odnaleźć najnowszą niewdrożoną sesję",
                "Usunąć wyłącznie jej izolowany workspace",
                "Pozostawić działający projekt bez zmian",
            ],
            "actions": [],
            "can_execute": True,
            "handler": "safe_development_discard",
            "safe_preparation": True,
            "workspace_only": True,
            "project_write": False,
            "requires_confirmation": False,
        }
    if _contains(normalized, _STATUS_MARKERS):
        return {
            "command": str(command),
            "goal": "Pokazać status bezpiecznej sesji AutoDev",
            "plan": ["Odczytać rejestr sesji", "Pokazać aktualny stan i plik"],
            "actions": [],
            "can_execute": True,
            "handler": "safe_development_status",
            "read_only": True,
            "requires_confirmation": False,
        }
    return None


def execute_safe_development_command(
    brain: Any,
    thought: dict[str, Any],
) -> str:
    """Execute one exact B201-B210 operation and remember a safe message."""
    service = _service(brain)
    handler = str(thought.get("handler", ""))
    if handler == "safe_development_prepare":
        preview = getattr(brain, "last_safe_autodev_preview", None)
        result = service.prepare(preview=preview if isinstance(preview, dict) else None)
    elif handler == "safe_development_status":
        result = service.status()
    elif handler == "safe_development_discard":
        result = service.discard()
    elif handler == "safe_development_deploy":
        result = service.deploy(
            str(thought.get("safe_session_id", "")),
            str(thought.get("operation_fingerprint", "")),
        )
    elif handler == "safe_development_rollback":
        result = service.rollback(
            str(thought.get("safe_session_id", "")),
            str(thought.get("operation_fingerprint", "")),
        )
    else:
        result = {
            "message": "Nie rozpoznałem operacji bezpiecznego AutoDev.",
        }
    message = str(result.get("message", "")).strip() or (
        "Operacja bezpiecznego AutoDev została zakończona."
    )
    remember = getattr(brain, "_remember_execution", None)
    if callable(remember):
        remember(str(thought.get("command", "")), message)
    return message


def _confirmed_thought(
    command: str,
    handler: str,
    planned: dict[str, Any],
    steps: list[str],
) -> dict[str, Any]:
    success = bool(planned.get("success", False))
    session = dict(planned.get("session", {}) or {})
    return {
        "command": str(command),
        "goal": "Wykonać dokładnie przygotowaną i zweryfikowaną operację AutoDev",
        "plan": steps if success else [str(planned.get("message", "Brak operacji."))],
        "actions": [],
        "can_execute": success,
        "handler": handler,
        "safe_session_id": str(session.get("session_id", "")),
        "operation_fingerprint": str(planned.get("operation_fingerprint", "")),
        "confirmation_message": str(planned.get("confirmation_message", "")),
        "requires_confirmation": success,
        "project_write": success,
        "exact_prepared_operation": success,
    }


def _service(brain: Any) -> SafeAutonomousDevelopmentService:
    service = getattr(brain, "safe_autonomous_development_service", None)
    if service is None:
        service = SafeAutonomousDevelopmentService(
            getattr(brain, "project_root", None)
        )
        setattr(brain, "safe_autonomous_development_service", service)
    return service


def _is_rollback_command(value: str) -> bool:
    if _contains(value, _ROLLBACK_EXCLUSIONS):
        return False
    if _contains(value, _ROLLBACK_MARKERS):
        return True
    has_action = _contains(value, _ROLLBACK_ACTIONS)
    has_object = _contains(value, _ROLLBACK_OBJECTS)
    return has_action and has_object


def _is_prepare_command(value: str) -> bool:
    if _contains(value, _PREPARE_MARKERS):
        return True
    has_action = _contains(value, _PREPARE_ACTIONS)
    has_object = _contains(value, _PREPARE_OBJECTS)
    isolated = _contains(value, _PREPARE_ISOLATION)
    no_deploy = _contains(value, _PREPARE_NO_DEPLOY)
    return has_action and has_object and isolated and no_deploy


def _contains(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold())
    plain = "".join(
        char for char in text if not unicodedata.combining(char)
    )
    return " ".join(
        "".join(char if char.isalnum() else " " for char in plain).split()
    )
