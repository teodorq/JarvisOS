import os
import subprocess
import webbrowser

from app.ai.actions import ActionTypes
from app.skills.skill_manager import SkillManager


class CommandExecutor:

    def __init__(self):
        self.skill_manager = SkillManager()

    def execute_action(self, action: dict):
        action_type = action.get("action_type", ActionTypes.UNKNOWN)

        skill_result = self.skill_manager.execute(action)

        if skill_result is not None:
            return skill_result

        if action_type == ActionTypes.OPEN_APP:
            return self.open_app(action.get("target", ""))

        if action_type == ActionTypes.OPEN_WEBSITE:
            return self.open_website(action.get("target", ""))

        return "Nieznana akcja."

    def normalize_target(self, target):
        target = target.lower().strip()

        target = target.replace("https://", "")
        target = target.replace("http://", "")
        target = target.replace("www.", "")

        if target.endswith(".pl"):
            target = target[:-3]

        if target.endswith(".com"):
            target = target[:-4]

        return target

    def open_website(self, target):
        target = self.normalize_target(target)

        websites = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "facebook": "https://www.facebook.com",
            "github": "https://github.com",
            "gmail": "https://mail.google.com",
            "chatgpt": "https://chatgpt.com"
        }

        if target not in websites:
            return f"Nie znam strony: {target}"

        webbrowser.open(websites[target])

        return f"Otwieram {target}."

    def open_app(self, target):
        target = self.normalize_target(target)

        if target in [
            "chrome",
            "opera",
            "opera gx",
            "operagx",
            "gx"
        ]:
            opera = (
                r"C:\Users\Kacperek\AppData\Local\Programs"
                r"\Opera GX\opera.exe"
            )

            subprocess.Popen([opera])

            return "Otwieram Opera GX."

        if target == "notatnik":
            os.system("notepad")
            return "Otwieram Notatnik."

        if target == "steam":
            os.system("start steam://open/main")
            return "Otwieram Steam."

        if target == "discord":
            try:
                subprocess.Popen(
                    r"C:\Users\Kacperek\AppData\Local\Discord\Update.exe --processStart Discord.exe"
                )
                return "Otwieram Discord."
            except Exception:
                return "Nie udało się otworzyć Discorda."

        return f"Nie znam aplikacji: {target}"