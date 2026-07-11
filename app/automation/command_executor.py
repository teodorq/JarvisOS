from __future__ import annotations

import os
import subprocess

from app.ai.actions import ActionTypes
from app.browser.browser import BrowserAgent
from app.skills.skill_manager import SkillManager


class CommandExecutor:

    def __init__(
        self,
    ) -> None:

        self.skill_manager = SkillManager()
        self.browser = BrowserAgent()

    def execute_action(
        self,
        action: dict,
    ):

        if not isinstance(
            action,
            dict,
        ):
            return (
                "Nieprawidłowa akcja."
            )

        action_type = action.get(
            "action_type",
            ActionTypes.UNKNOWN,
        )

        if (
            action_type
            == ActionTypes.OPEN_APP
        ):
            return self.open_app(
                action.get(
                    "target",
                    "",
                )
            )

        if (
            action_type
            == ActionTypes.OPEN_WEBSITE
        ):
            return self.open_website(
                action.get(
                    "target",
                    "",
                )
            )

        if (
            action_type
            == ActionTypes.GOOGLE_SEARCH
        ):
            return self.browser.google_search(
                action.get(
                    "query",
                    "",
                )
            )

        if (
            action_type
            == ActionTypes.YOUTUBE_SEARCH
        ):
            return self.browser.youtube_search(
                action.get(
                    "query",
                    "",
                )
            )

        if (
            action_type
            == ActionTypes.OPEN_URL
        ):
            return self.browser.open_url(
                action.get(
                    "url",
                    action.get(
                        "target",
                        "",
                    ),
                )
            )

        skill_result = (
            self.skill_manager.execute(
                action
            )
        )

        if skill_result is not None:
            return skill_result

        return (
            f"Nieznana akcja: "
            f"{action_type}"
        )

    def normalize_target(
        self,
        target,
    ) -> str:

        normalized = str(
            target
        ).lower().strip()

        normalized = normalized.replace(
            "https://",
            "",
        )

        normalized = normalized.replace(
            "http://",
            "",
        )

        normalized = normalized.replace(
            "www.",
            "",
        )

        normalized = normalized.rstrip(
            "/"
        )

        if normalized.endswith(
            ".pl"
        ):
            normalized = normalized[:-3]

        if normalized.endswith(
            ".com"
        ):
            normalized = normalized[:-4]

        return normalized

    def open_website(
        self,
        target,
    ) -> str:

        normalized_target = (
            self.normalize_target(
                target
            )
        )

        if normalized_target == "youtube":
            return self.browser.open_youtube()

        if normalized_target == "google":
            return self.browser.open_google()

        websites = {
            "facebook": (
                "https://www.facebook.com"
            ),
            "github": (
                "https://github.com"
            ),
            "gmail": (
                "https://mail.google.com"
            ),
            "chatgpt": (
                "https://chatgpt.com"
            ),
        }

        url = websites.get(
            normalized_target
        )

        if not url:
            return (
                "Nie znam strony: "
                f"{normalized_target}"
            )

        return self.browser.open_url(
            url
        )

    def open_app(
        self,
        target,
    ) -> str:

        normalized_target = (
            self.normalize_target(
                target
            )
        )

        if normalized_target in {
            "chrome",
            "opera",
            "opera gx",
            "operagx",
            "gx",
        }:
            opera_path = (
                r"C:\Users\Kacperek"
                r"\AppData\Local\Programs"
                r"\Opera GX\opera.exe"
            )

            if not os.path.exists(
                opera_path
            ):
                return (
                    "Nie znaleziono pliku "
                    "Opera GX."
                )

            try:
                subprocess.Popen(
                    [opera_path]
                )

                return (
                    "Otwieram Opera GX."
                )

            except OSError as error:
                return (
                    "Nie udało się otworzyć "
                    f"Opera GX: {error}"
                )

        if normalized_target in {
            "notatnik",
            "notepad",
        }:
            try:
                subprocess.Popen(
                    ["notepad.exe"]
                )

                return (
                    "Otwieram Notatnik."
                )

            except OSError as error:
                return (
                    "Nie udało się otworzyć "
                    f"Notatnika: {error}"
                )

        if normalized_target == "steam":
            try:
                os.startfile(
                    "steam://open/main"
                )

                return "Otwieram Steam."

            except OSError as error:
                return (
                    "Nie udało się otworzyć "
                    f"Steam: {error}"
                )

        if normalized_target == "discord":
            discord_path = (
                r"C:\Users\Kacperek"
                r"\AppData\Local\Discord"
                r"\Update.exe"
            )

            if not os.path.exists(
                discord_path
            ):
                return (
                    "Nie znaleziono pliku "
                    "Discord Update.exe."
                )

            try:
                subprocess.Popen(
                    [
                        discord_path,
                        "--processStart",
                        "Discord.exe",
                    ]
                )

                return (
                    "Otwieram Discord."
                )

            except OSError as error:
                return (
                    "Nie udało się otworzyć "
                    f"Discorda: {error}"
                )

        return (
            "Nie znam aplikacji: "
            f"{normalized_target}"
        )