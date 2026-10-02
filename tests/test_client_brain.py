from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from app.ai.client_brain import ClientBrain


class _Assistant:
    memory = None

    @staticmethod
    def matches(_command: object) -> bool:
        return True

    @staticmethod
    def resolve_command(_command: str) -> SimpleNamespace:
        return SimpleNamespace(intent="current_time")

    @staticmethod
    def plan(command: str) -> dict:
        return {
            "command": command,
            "handler": "personal_assistant",
            "plan": ["Odpowiedzieć lokalnie"],
            "actions": [],
            "can_execute": True,
        }


def test_client_brain_plans_without_loading_owner_graph() -> None:
    with TemporaryDirectory() as temporary:
        brain = ClientBrain(Path(temporary))
        brain.personal_assistant_controller = _Assistant()
        thought = brain.think("Jaka jest godzina?")
    assert thought["handler"] == "personal_assistant"
    assert thought["can_execute"] is True
    assert brain.background_status()["status"] == "DEFERRED_CLIENT_MODE"


def test_client_brain_creates_fallback_components_only_on_demand() -> None:
    with TemporaryDirectory() as temporary:
        brain = ClientBrain(Path(temporary))
        assert brain._planner is None
        assert brain._executor is None
        assert brain._task_planner is None
        assert brain._agent_loop is None
