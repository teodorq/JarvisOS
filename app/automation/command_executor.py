import os
import subprocess
import webbrowser

from app.ai.actions import ActionTypes
from app.browser.browser import BrowserAgent
from app.desktop.controller import DesktopController
from app.vision.screen import ScreenVision


class CommandExecutor:
    def __init__(self):
        self.desktop = DesktopController()
        self.vision = ScreenVision()
        self.browser = BrowserAgent()

    def execute_action(self, action: dict) -> str:
        action_type = action.get("action_type")
        target = action.get("target", "")
        text = action.get("text", "")
        url = action.get("url", "")
        query = action.get("query", "")

        if action_type == ActionTypes.OPEN_URL:
            return self.browser.open_url(url)

        if action_type == ActionTypes.GOOGLE_SEARCH:
            return self.browser.google_search(query)

        if action_type == ActionTypes.YOUTUBE_SEARCH:
            return self.browser.youtube_search(query)

        if action_type == ActionTypes.PRESS_ENTER:
            return self.browser.press_enter()

        if action_type == ActionTypes.OPEN_WEBSITE:
            return self.open_website(target)

        if action_type == ActionTypes.OPEN_APP:
            return self.open_app(target)

        if action_type == ActionTypes.TYPE_TEXT:
            self.desktop.write(text)
            return f"Piszę: {text}"

        if action_type == ActionTypes.CLICK:
            self.desktop.click()
            return "Klikam."

        if action_type == ActionTypes.SCREENSHOT:
            path = self.vision.take_screenshot()
            return f"Zrobiłem zrzut ekranu: {path}"

        return "Nie znam jeszcze tej akcji."

    def normalize_target(self, target: str) -> str:
        target = target.lower().strip()

        target = target.replace("https://", "")
        target = target.replace("http://", "")
        target = target.replace("www.", "")

        if target.endswith(".com"):
            target = target[:-4]

        if target.endswith(".pl"):
            target = target[:-3]

        return target

    def open_website(self, target: str) -> str:
        target = self.normalize_target(target)

        websites = {
            "youtube": "https://youtube.com",
            "google": "https://google.com",
            "facebook": "https://facebook.com",
            "github": "https://github.com",
            "gmail": "https://mail.google.com",
            "chatgpt": "https://chat.openai.com",
        }

        url = websites.get(target)

        if url:
            webbrowser.open(url)
            return f"Otwieram {target}."

        return f"Nie znam strony: {target}"

    def open_app(self, target: str):
        target = self.normalize_target(target)

        if target == "chrome":
            subprocess.Popen(
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            )
            return "Otwieram Chrome."

        if target == "notatnik":
            os.system("notepad")
            return "Otwieram Notatnik."

        if target == "steam":
            os.system("start steam://open/main")
            return "Otwieram Steam."

        if target == "discord":
            try:
                subprocess.Popen(
                    r"C:\Users\Kacper\AppData\Local\Discord\Update.exe --processStart Discord.exe"
                )
                return "Otwieram Discord."
            except Exception:
                return "Nie udało się otworzyć Discorda."

        return f"Nie znam aplikacji: {target}"