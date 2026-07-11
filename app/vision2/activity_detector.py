class ActivityDetector:

    def detect(self, app_name: str, page_context: str, window_title: str) -> str:
        app = (app_name or "").lower()
        page = (page_context or "").lower()
        title = (window_title or "").lower()

        if app == "jarvis":
            return "talking_to_jarvis"

        if page == "youtube":
            if "youtube" in title:
                return "watching_or_browsing_youtube"
            return "using_youtube"

        if page == "chatgpt":
            return "using_chatgpt"

        if app in ["vscode", "pycharm"]:
            return "coding"

        if app in ["cmd", "powershell", "terminal"]:
            return "using_terminal"

        if app in ["opera", "chrome", "edge", "firefox"]:
            return "browsing_web"

        if app == "discord":
            return "chatting"

        if app == "minecraft":
            return "gaming"

        return "unknown"