from app.ai.system_state import SystemState
from app.skills.base_skill import BaseSkill


class SystemSkill(BaseSkill):

    name = "system"

    def __init__(self):
        self.state = SystemState()

    def can_handle(self, action: dict) -> bool:
        return action.get("action_type") == "SYSTEM_STATUS"

    def execute(self, action: dict):
        return self.state.summary()