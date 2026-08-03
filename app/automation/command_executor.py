from __future__ import annotations

import os
from pathlib import Path
import shutil

from app.ai.actions import ActionTypes
from app.browser.browser import BrowserAgent
from app.core.project_paths import default_project_root
from app.core.safe_process import (
    ProcessPolicyError,
    SafeProcessRunner,
)
from app.skills.skill_manager import SkillManager


class CommandExecutor:

    def __init__(
        self,
        *,
        process_runner: SafeProcessRunner | None = None,
    ) -> None:

        self.skill_manager = SkillManager()
        self.browser = BrowserAgent()
        self.process_runner = (
            process_runner
            or SafeProcessRunner(
                project_root=default_project_root(),
                max_timeout_seconds=30,
            )
        )

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
            opera_path = self._first_existing(
                self._opera_candidates()
            )

            if opera_path is None:
                return (
                    "Nie znaleziono pliku "
                    "Opera GX."
                )

            return self._spawn_known_app(
                [str(opera_path)],
                success_message=(
                    "Otwieram Opera GX."
                ),
                failure_label="Opera GX",
            )

        if normalized_target in {
            "notatnik",
            "notepad",
        }:
            notepad_path = self._notepad_path()

            if notepad_path is None:
                return (
                    "Nie znaleziono pliku "
                    "Notatnika."
                )

            return self._spawn_known_app(
                [str(notepad_path)],
                success_message=(
                    "Otwieram Notatnik."
                ),
                failure_label="Notatnika",
            )

        if normalized_target == "steam":
            try:
                os.startfile(
                    "steam://open/main"
                )

                return "Otwieram Steam."

            except (
                AttributeError,
                OSError,
            ) as error:
                return (
                    "Nie udało się otworzyć "
                    f"Steam: {error}"
                )

        if normalized_target == "discord":
            discord_path = self._first_existing(
                self._discord_candidates()
            )

            if discord_path is None:
                return (
                    "Nie znaleziono pliku "
                    "Discord Update.exe."
                )

            return self._spawn_known_app(
                [
                    str(discord_path),
                    "--processStart",
                    "Discord.exe",
                ],
                success_message=(
                    "Otwieram Discord."
                ),
                failure_label="Discorda",
            )

        return (
            "Nie znam aplikacji: "
            f"{normalized_target}"
        )

    def _spawn_known_app(
        self,
        command: list[str],
        *,
        success_message: str,
        failure_label: str,
    ) -> str:
        try:
            self.process_runner.spawn(
                command,
                allowed_executables=[
                    command[0],
                ],
            )

            return success_message

        except (
            OSError,
            ProcessPolicyError,
        ) as error:
            return (
                "Nie udało się otworzyć "
                f"{failure_label}: {error}"
            )

    def _opera_candidates(
        self,
    ) -> list[Path]:
        local = Path(
            os.getenv(
                "LOCALAPPDATA",
                "",
            )
        )

        candidates = [
            local
            / "Programs/Opera GX/opera.exe",
            local
            / "Programs/Opera/opera.exe",
        ]
        discovered = shutil.which(
            "opera.exe"
        )

        if discovered:
            candidates.append(
                Path(discovered)
            )

        return candidates

    def _discord_candidates(
        self,
    ) -> list[Path]:
        local = Path(
            os.getenv(
                "LOCALAPPDATA",
                "",
            )
        )

        return [
            local
            / "Discord/Update.exe",
        ]

    def _notepad_path(
        self,
    ) -> Path | None:
        discovered = shutil.which(
            "notepad.exe"
        )

        if discovered:
            return Path(
                discovered
            )

        windows_root = os.getenv(
            "WINDIR",
            "",
        )

        if windows_root:
            candidate = (
                Path(windows_root)
                / "System32/notepad.exe"
            )

            if candidate.is_file():
                return candidate

        return None

    @staticmethod
    def _first_existing(
        candidates: list[Path],
    ) -> Path | None:
        for candidate in candidates:
            if (
                str(candidate).strip()
                and candidate.is_file()
            ):
                return candidate.resolve(
                    strict=False
                )

        return None
