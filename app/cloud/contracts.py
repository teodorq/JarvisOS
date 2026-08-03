from __future__ import annotations

from typing import Any


SCHEMA_VERSION = 1
MAX_COMMAND_CHARS = 4_000
MAX_PLAN_STEPS = 20
MAX_PLAN_ACTIONS = 10
MAX_FIELD_CHARS = 4_000

# Phase one deliberately permits only low-risk, read-oriented plans. If the
# cloud proposes anything else, the desktop client rejects it and plans the
# command locally instead.
SAFE_REMOTE_ACTION_TYPES = frozenset(
    {
        "open_website",
        "open_app",
        "google_search",
        "youtube_search",
        "screenshot",
        "vision_analyze",
        "memory_summary",
        "SYSTEM_STATUS",
        "DESKTOP_HISTORY",
        "WINDOWS_LIST",
        "FILE_LIST",
        "PROJECT_SUMMARY",
        "CODE_MEMORY",
        "LIST_BACKUPS",
        "SHOW_PATCH",
        "FIND_FILE",
        "FIND_CODE",
        "FIND_CLASS",
        "FIND_FUNCTION",
        "SHOW_CLASS",
        "SHOW_FUNCTION",
        "ANALYZE_FUNCTION",
        "BUILD_DEPENDENCY_GRAPH",
        "ANALYZE_MODULE_IMPACT",
        "ANALYZE_SYMBOL_IMPACT",
        "PLAN_SYMBOL_CHANGE",
    }
)


class CloudContractError(ValueError):
    """Raised when a cloud request or response violates the safe contract."""


def normalize_command(value: Any) -> str:
    if not isinstance(value, str):
        raise CloudContractError("command must be a string")
    command = " ".join(value.split())
    if not command:
        raise CloudContractError("command cannot be empty")
    if len(command) > MAX_COMMAND_CHARS:
        raise CloudContractError("command is too long")
    return command


def validate_cloud_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CloudContractError("plan must be an object")

    handler_hint = value.get("handler_hint", "standard")
    if handler_hint != "standard":
        raise CloudContractError("only standard plans can run remotely")

    goal = _bounded_text(value.get("goal", ""), "goal")
    steps_value = value.get("steps", [])
    if not isinstance(steps_value, list) or len(steps_value) > MAX_PLAN_STEPS:
        raise CloudContractError("invalid plan steps")
    steps = [_bounded_text(step, "step") for step in steps_value]

    actions_value = value.get("actions", [])
    if not isinstance(actions_value, list) or len(actions_value) > MAX_PLAN_ACTIONS:
        raise CloudContractError("invalid plan actions")
    actions = [_validate_action(action) for action in actions_value]

    execute = value.get("execute", False)
    if not isinstance(execute, bool) or execute != bool(actions):
        raise CloudContractError("execute flag does not match the action list")

    first_action = actions[0] if actions else {}
    return {
        "goal": goal,
        "steps": steps,
        "execute": execute,
        "actions": actions,
        "action_type": first_action.get("action_type", "unknown"),
        "target": first_action.get("target", ""),
        "text": first_action.get("text", ""),
        "url": first_action.get("url", ""),
        "query": first_action.get("query", ""),
        "handler_hint": "standard",
        "planner_version": _bounded_text(
            value.get("planner_version", "cloud-1"),
            "planner_version",
            allow_empty=False,
        ),
    }


def _validate_action(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise CloudContractError("action must be an object")
    allowed_keys = {"action_type", "target", "text", "url", "query"}
    if set(value) - allowed_keys:
        raise CloudContractError("action contains unsupported fields")

    action_type = _bounded_text(
        value.get("action_type", ""), "action_type", allow_empty=False
    )
    if action_type not in SAFE_REMOTE_ACTION_TYPES:
        raise CloudContractError("action is not allowed in the cloud phase")

    return {
        "action_type": action_type,
        "target": _bounded_text(value.get("target", ""), "target"),
        "text": _bounded_text(value.get("text", ""), "text"),
        "url": _bounded_text(value.get("url", ""), "url"),
        "query": _bounded_text(value.get("query", ""), "query"),
    }


def _bounded_text(
    value: Any,
    field: str,
    *,
    allow_empty: bool = True,
) -> str:
    if not isinstance(value, str):
        raise CloudContractError(f"{field} must be a string")
    if not allow_empty and not value:
        raise CloudContractError(f"{field} cannot be empty")
    if len(value) > MAX_FIELD_CHARS:
        raise CloudContractError(f"{field} is too long")
    return value
