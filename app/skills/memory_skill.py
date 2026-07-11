from app.ai.actions import ActionTypes
from app.memory.memory_engine import MemoryEngine
from app.skills.base_skill import BaseSkill


class MemorySkill(BaseSkill):

    name = "memory"

    def __init__(self):
        self.memory = MemoryEngine()

    def can_handle(self, action: dict) -> bool:
        return action.get("action_type") in [
            ActionTypes.REMEMBER,
            ActionTypes.ADD_TASK,
            ActionTypes.MEMORY_SUMMARY
        ]

    def execute(self, action: dict):
        action_type = action.get("action_type")

        if action_type == ActionTypes.REMEMBER:
            return self.memory.remember_note(action.get("text", ""))

        if action_type == ActionTypes.ADD_TASK:
            return self.memory.remember_task(action.get("text", ""))

        if action_type == ActionTypes.MEMORY_SUMMARY:
            return self.memory.get_memory_summary()

        return None