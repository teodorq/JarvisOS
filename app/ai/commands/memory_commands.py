from app.ai.actions import ActionTypes
from app.ai.commands.base_command import BaseCommand


class MemoryCommand(BaseCommand):

    def parse(self, command: str):
        if command.startswith("zapamiętaj "):
            text = command.replace("zapamiętaj", "", 1).strip()
            return self._action(ActionTypes.REMEMBER, text=text)

        if command.startswith("zadanie "):
            text = command.replace("zadanie", "", 1).strip()
            return self._action(ActionTypes.ADD_TASK, text=text)

        if "co pamiętasz" in command or "pamięć" in command:
            return self._action(ActionTypes.MEMORY_SUMMARY)

        return None

    def _action(self, action_type, target="", text="", url="", query=""):
        return {
            "action_type": action_type,
            "target": target,
            "text": text,
            "url": url,
            "query": query
        }