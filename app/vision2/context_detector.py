class ContextDetector:

    def detect_app(self, window_title: str) -> str:
        title = (window_title or "").lower()

        # ===== Jarvis =====

        if "jarvis os" in title:
            return "jarvis"

        # ===== Browsers =====

        if "opera gx" in title or "opera" in title:
            return "opera"

        if "chrome" in title:
            return "chrome"

        if "edge" in title:
            return "edge"

        if "firefox" in title:
            return "firefox"

        # ===== IDE =====

        if "visual studio code" in title or "vscode" in title:
            return "vscode"

        if "pycharm" in title:
            return "pycharm"

        # ===== Terminal =====

        if "wiersz polecenia" in title:
            return "cmd"

        if "command prompt" in title:
            return "cmd"

        if "powershell" in title:
            return "powershell"

        if "terminal" in title:
            return "terminal"

        # ===== Windows =====

        if "eksplorator" in title or "explorer" in title:
            return "explorer"

        if "notatnik" in title or "notepad" in title:
            return "notepad"

        # ===== Apps =====

        if "discord" in title:
            return "discord"

        if "steam" in title:
            return "steam"

        if "minecraft" in title:
            return "minecraft"

        return "unknown"

    def detect_page_context(self, window_title: str, raw_text: str = "") -> str:
        title = (window_title or "").lower()
        text = (raw_text or "").lower()

        combined = title + " " + text

        if "youtube" in combined:
            return "youtube"

        if "chatgpt" in combined:
            return "chatgpt"

        if "google" in combined:
            return "google"

        if "gmail" in combined:
            return "gmail"

        if "facebook" in combined:
            return "facebook"

        if "discord" in combined:
            return "discord"

        if "jarvis os" in combined:
            return "jarvis"

        return "unknown"