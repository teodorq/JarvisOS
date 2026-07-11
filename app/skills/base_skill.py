class BaseSkill:

    name = "base"

    def can_handle(self, action: dict) -> bool:
        return False

    def execute(self, action: dict):
        raise NotImplementedError()