from app.ai.commands.base_command import BaseCommand


class WindowsCommand(BaseCommand):

    def parse(self, command: str):
        if command == "lista okien":
            return self._action("WINDOWS_LIST")

        if command.startswith("aktywuj okno "):
            target = command.replace("aktywuj okno", "", 1).strip()
            return self._action("WINDOW_FOCUS", target=target)

        if command.startswith("zamknij okno "):
            target = command.replace("zamknij okno", "", 1).strip()
            return self._action("WINDOW_CLOSE", target=target)

        if command.startswith("otwórz folder "):
            target = command.replace("otwórz folder", "", 1).strip()
            return self._action("FILE_LIST", target=target)

        if command.startswith("pokaż folder "):
            target = command.replace("pokaż folder", "", 1).strip()
            return self._action("FILE_LIST", target=target)

        if command.startswith("utwórz folder "):
            target = command.replace("utwórz folder", "", 1).strip()
            return self._action("FOLDER_CREATE", target=target)

        if command.startswith("stwórz folder "):
            target = command.replace("stwórz folder", "", 1).strip()
            return self._action("FOLDER_CREATE", target=target)

        if command.startswith("uruchom aplikację "):
            target = command.replace("uruchom aplikację", "", 1).strip()
            return self._action("APP_OPEN", target=target)

        if command.startswith("uruchom aplikacje "):
            target = command.replace("uruchom aplikacje", "", 1).strip()
            return self._action("APP_OPEN", target=target)

        if "zamknij okno" in command:
            return self._action("CLOSE_WINDOW")

        if "przełącz okno" in command or "przelacz okno" in command:
            return self._action("SWITCH_WINDOW")

        if "zminimalizuj okno" in command:
            return self._action("MINIMIZE_WINDOW")

        if "zmaksymalizuj okno" in command:
            return self._action("MAXIMIZE_WINDOW")

        if "menu start" in command:
            return self._action("OPEN_START_MENU")

        return None

    def _action(self, action_type, target="", text="", url="", query=""):
        return {
            "action_type": action_type,
            "target": target,
            "text": text,
            "url": url,
            "query": query
        }