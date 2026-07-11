from app.ai.actions import ActionTypes
from app.ai.commands.base_command import BaseCommand


class VisionCommand(BaseCommand):

    def parse(self, command: str):
        if (
            "kliknij pierwszy film" in command
            or "odpal pierwszy film" in command
            or "włącz pierwszy film" in command
            or "wlacz pierwszy film" in command
            or "wybierz pierwszy film" in command
        ):
            return self._action(ActionTypes.YOUTUBE_FIRST_VIDEO)

        if command.startswith("kliknij ") or command.startswith("naciśnij ") or command.startswith("wybierz "):
            target = command
            target = target.replace("kliknij", "", 1)
            target = target.replace("naciśnij", "", 1)
            target = target.replace("wybierz", "", 1)
            target = target.strip()

            return self._action(
                ActionTypes.VISION_CLICK,
                target=target,
                text=target,
                query=target
            )

        if (
            "co widzisz" in command
            or "przeanalizuj ekran" in command
            or "co jest na ekranie" in command
        ):
            return self._action(ActionTypes.VISION_ANALYZE)

        if "zrób screen" in command or "zrzut ekranu" in command:
            return self._action(ActionTypes.SCREENSHOT)

        return None

    def _action(self, action_type, target="", text="", url="", query=""):
        return {
            "action_type": action_type,
            "target": target,
            "text": text,
            "url": url,
            "query": query
        }