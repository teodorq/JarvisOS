from app.ai.commands.base_command import BaseCommand


class SystemCommand(BaseCommand):

    def parse(self, command: str):
        if (
            "status systemu" in command
            or "stan systemu" in command
            or "status chmury" in command
            or "stan chmury" in command
            or "jak działa system" in command
        ):
            return self._action("SYSTEM_STATUS")

        return None

    def _action(self, action_type, target="", text="", url="", query=""):
        return {
            "action_type": action_type,
            "target": target,
            "text": text,
            "url": url,
            "query": query
        }