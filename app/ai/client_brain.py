from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.ai.cognitive_engine import CognitiveEngine
from app.core.project_paths import resolve_project_root
from app.memory.memory import Memory


class ClientBrain:
    """Small command core; owner development graph is loaded only on demand."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = str(resolve_project_root(project_root))
        self.runtime_profile = "client"
        self.memory = Memory(self.project_root)
        self.cognitive = CognitiveEngine()
        self.personal_assistant_controller: Any | None = None
        self.background_autodev_start_result = {
            "success": True,
            "running": False,
            "status": "DEFERRED_CLIENT_MODE",
        }
        self._planner: Any | None = None
        self._executor: Any | None = None
        self._task_planner: Any | None = None
        self._agent_loop: Any | None = None

    def think(self, command: str) -> dict[str, Any]:
        from app.assistant.natural_language import normalize_user_command

        original = str(command)
        normalized = normalize_user_command(original)
        self.cognitive.before_think(normalized)
        assistant = self.personal_assistant_controller
        if assistant is not None:
            resolved = assistant.resolve_command(normalized)
            matches = getattr(type(assistant), "matches", lambda _value: False)
            if resolved.intent != "standard" or matches(normalized):
                thought = assistant.plan(normalized)
                thought["original_command"] = original
                self.cognitive.after_plan(thought)
                return thought
        plan = self._get_planner().create_plan(normalized)
        self.cognitive.after_plan(plan)
        return {
            "command": normalized,
            "goal": plan.get("goal", ""),
            "plan": plan.get("steps", []),
            "actions": plan.get("actions", []),
            "can_execute": plan.get("execute", False),
            "handler": "standard",
        }

    def execute(self, thought: dict[str, Any]) -> Any:
        command = str(thought.get("command", ""))
        assistant = self.personal_assistant_controller
        if thought.get("handler") == "personal_assistant":
            from app.natural_actions.planned_execution import PlannedNaturalActionExecutor

            result = PlannedNaturalActionExecutor.execute(assistant, thought)
            self._remember_execution(command, result)
            return result
        actions = list(thought.get("actions", []) or [])
        if actions:
            results = []
            for action in actions:
                result = (
                    assistant.execute_standard_action(action, self._get_executor())
                    if assistant is not None
                    else self._get_executor().execute_action(action)
                )
                results.append(str(result))
                if action.get("action_type") == "OPEN_APP":
                    time.sleep(2)
            final = " | ".join(results)
            self._remember_execution(command, final)
            return final
        result = self._get_agent_loop().run(
            self._get_task_planner().create_task(command)
        )
        self._remember_execution(command, result)
        return result

    def background_status(self) -> dict[str, Any]:
        return dict(self.background_autodev_start_result)

    def shutdown(self) -> None:
        return None

    def _remember_execution(self, command: str, result: Any) -> None:
        result_text = str(result)
        self.memory.add_history(command, result_text)
        self.cognitive.after_execute(command, result_text)

    def _get_planner(self) -> Any:
        if self._planner is None:
            from app.cloud.hybrid_planner import HybridPlanner
            self._planner = HybridPlanner()
        return self._planner

    def _get_executor(self) -> Any:
        if self._executor is None:
            from app.automation.command_executor import CommandExecutor
            self._executor = CommandExecutor()
        return self._executor

    def _get_task_planner(self) -> Any:
        if self._task_planner is None:
            from app.agent.task_planner import TaskPlanner
            self._task_planner = TaskPlanner()
        return self._task_planner

    def _get_agent_loop(self) -> Any:
        if self._agent_loop is None:
            from app.agent.loop import AgentLoop
            self._agent_loop = AgentLoop()
        return self._agent_loop


def ensure_owner_brain(
    brain: Any | None,
    assistant: Any | None = None,
    project_root: str | Path | None = None,
) -> Any:
    """Upgrade the light client core while preserving conversation memory."""
    if brain is not None and not isinstance(brain, ClientBrain):
        enable = getattr(brain, "enable_owner_runtime", None)
        if callable(enable):
            enable()
        return brain
    from app.ai.brain import Brain

    root = project_root or getattr(brain, "project_root", None)
    owner = Brain(project_root=str(root) if root else None, runtime_profile="owner")
    if isinstance(brain, ClientBrain):
        owner.memory = brain.memory
    if assistant is not None:
        assistant.memory = owner.memory
        owner.personal_assistant_controller = assistant
    return owner
