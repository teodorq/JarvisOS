from app.agent.app_manager import AppManager
from app.agent.file_manager import FileManager
from app.agent.window_manager import WindowManager
from app.skills.base_skill import BaseSkill


class WindowsSkill(BaseSkill):

    name = "windows"

    def __init__(self):
        self.windows = WindowManager()
        self.files = FileManager()
        self.apps = AppManager()

    def can_handle(self, action: dict) -> bool:
        return action.get("action_type") in [
            "WINDOWS_LIST",
            "WINDOW_FOCUS",
            "WINDOW_CLOSE",
            "FILE_LIST",
            "FOLDER_CREATE",
            "APP_OPEN"
        ]

    def execute(self, action: dict):
        action_type = action.get("action_type")
        target = action.get("target", "")

        if action_type == "WINDOWS_LIST":
            return self.windows.summary()

        if action_type == "WINDOW_FOCUS":
            return self.windows.focus_window(target)

        if action_type == "WINDOW_CLOSE":
            return self.windows.close_window(target)

        if action_type == "FILE_LIST":
            return self.files.list_folder(target)

        if action_type == "FOLDER_CREATE":
            return self.files.create_folder(target)

        if action_type == "APP_OPEN":
            return self.apps.open_app(target)

        return None