from app.ai.actions import ActionTypes
from app.ai.planner_llm import PlannerLLM
from app.automation.command_executor import CommandExecutor
from app.memory.memory import Memory


class Brain:
    def __init__(self):
        self.planner = PlannerLLM()
        self.executor = CommandExecutor()
        self.memory = Memory()

    def think(self, command: str) -> dict:
        plan_data = self.planner.create_plan(command)

        action = {
            "action_type": plan_data.get("action_type", ActionTypes.UNKNOWN),
            "target": plan_data.get("target", ""),
            "text": plan_data.get("text", ""),
            "url": plan_data.get("url", ""),
            "query": plan_data.get("query", "")
        }

        steps = plan_data.get("steps", [])

        can_execute = (
            bool(plan_data.get("execute", False))
            and action["action_type"] != ActionTypes.UNKNOWN
        )

        return {
            "command": command,
            "goal": plan_data.get("goal", ""),
            "action": action,
            "plan": steps,
            "can_execute": can_execute
        }

    def execute(self, thought: dict) -> str:
        action = thought["action"]
        action_type = action["action_type"]

        if action_type == ActionTypes.REMEMBER:
            response = self.memory.remember_note(action["text"])
            self.memory.add_history(thought["command"], response)
            return response

        if action_type == ActionTypes.ADD_TASK:
            response = self.memory.add_task(action["text"])
            self.memory.add_history(thought["command"], response)
            return response

        if action_type == ActionTypes.MEMORY_SUMMARY:
            response = self.memory.get_summary()
            self.memory.add_history(thought["command"], response)
            return response

        response = self.executor.execute_action(action)
        self.memory.add_history(thought["command"], response)
        return response