from datetime import datetime


class ActionHistory:

    def __init__(self):
        self.actions = []

    def add(self, action_type, description, success=True):

        self.actions.append({
            "time": datetime.now().isoformat(),
            "action": action_type,
            "description": description,
            "success": success
        })

        if len(self.actions) > 500:
            self.actions = self.actions[-500:]

    def last(self):

        if not self.actions:
            return None

        return self.actions[-1]

    def summary(self):

        lines = []

        for action in self.actions[-20:]:

            status = "OK" if action["success"] else "FAIL"

            lines.append(
                f"[{status}] "
                f"{action['action']} -> "
                f"{action['description']}"
            )

        return "\n".join(lines)

    def clear(self):
        self.actions.clear()