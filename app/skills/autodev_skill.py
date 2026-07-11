from app.autodev.developer_agent import DeveloperAgent
from app.skills.base_skill import BaseSkill


class AutoDevSkill(BaseSkill):

    name = "autodev"

    def __init__(self):
        self.developer = DeveloperAgent()

    def can_handle(self, action: dict) -> bool:
        return action.get("action_type") in [
            "BUILD_DEPENDENCY_GRAPH",
            "ANALYZE_SYMBOL_IMPACT",
            "ANALYZE_MODULE_IMPACT",
            "PLAN_SYMBOL_CHANGE",
            "PREPARE_DEVELOPER_TASK"
        ]

    def execute(self, action: dict):
        action_type = action.get("action_type")
        target = action.get("target", "")
        text = action.get("text", "")

        if action_type == "BUILD_DEPENDENCY_GRAPH":
            return self.developer.build_dependency_graph()

        if action_type == "ANALYZE_SYMBOL_IMPACT":
            return self.developer.analyze_symbol_impact(target)

        if action_type == "ANALYZE_MODULE_IMPACT":
            return self.developer.analyze_module_impact(target)

        if action_type == "PLAN_SYMBOL_CHANGE":
            return self.developer.plan_symbol_change(target)

        if action_type == "PREPARE_DEVELOPER_TASK":
            goal_text = text or f"Zmienić symbol {target}"

            return self.developer.prepare_developer_task(
                goal_text=goal_text,
                target=target
            )

        return None