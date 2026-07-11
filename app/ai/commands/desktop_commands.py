from app.ai.actions import ActionTypes
from app.ai.commands.base_command import BaseCommand


class DesktopCommand(BaseCommand):

    def parse(self, command: str):
        if "historia pulpitu" in command or "historia akcji" in command:
            return self._action("DESKTOP_HISTORY")

        if "przewiń w dół" in command or "przewin w dol" in command:
            return self._action("SCROLL_DOWN")

        if "przewiń w górę" in command or "przewin w gore" in command:
            return self._action("SCROLL_UP")

        if command == "skopiuj":
            return self._action("COPY")

        if command == "wklej":
            return self._action("PASTE")

        if command == "wytnij":
            return self._action("CUT")

        if "zaznacz wszystko" in command:
            return self._action("SELECT_ALL")

        if command in ["enter", "naciśnij enter", "wciśnij enter"]:
            return self._action(ActionTypes.PRESS_ENTER)

        if command.startswith("wpisz "):
            text = command.replace("wpisz", "", 1).strip()
            return self._action(ActionTypes.TYPE_TEXT, text=text)

        if command.startswith("napisz "):
            text = command.replace("napisz", "", 1).strip()
            return self._action(ActionTypes.TYPE_TEXT, text=text)

        if command.startswith("wyszukaj "):
            query = command.replace("wyszukaj", "", 1).strip()
            return self._action(ActionTypes.TYPE_TEXT, text=query)

        if command.startswith("szukaj "):
            query = command.replace("szukaj", "", 1).strip()
            return self._action(ActionTypes.TYPE_TEXT, text=query)

        return None

    def _action(self, action_type, target="", text="", url="", query=""):
        return {
            "action_type": action_type,
            "target": target,
            "text": text,
            "url": url,
            "query": query
        }