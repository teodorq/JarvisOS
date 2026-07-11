from app.memory.memory_engine import MemoryEngine


class CognitiveEngine:

    def __init__(self):
        self.memory = MemoryEngine()
        self.current_context = {}
        self.last_command = ""
        self.last_plan = None
        self.last_result = ""

    def before_think(self, command: str):
        self.last_command = command
        self.update_context("last_command", command)

    def after_plan(self, plan: dict):
        self.last_plan = plan
        self.update_context("last_plan", plan)

    def after_execute(self, command: str, result: str):
        self.last_result = result

        self.update_context("last_result", result)

        self.memory.remember_history(
            command,
            result
        )

    def update_context(self, key, value):
        self.current_context[key] = value

    def get_context(self):
        return self.current_context

    def summary(self):
        return {
            "last_command": self.last_command,
            "last_result": self.last_result,
            "context": self.current_context,
            "memory": self.memory.summary()
        }