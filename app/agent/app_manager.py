from __future__ import annotations

import os
from pathlib import Path
import shutil

from app.core.project_paths import (
    default_project_root,
)
from app.core.safe_process import (
    ProcessPolicyError,
    SafeProcessRunner,
)


class AppManager:
    """Launches only known desktop applications."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        process_runner: SafeProcessRunner | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
            or default_project_root()
        ).expanduser().resolve(
            strict=False
        )
        self.process_runner = (
            process_runner
            or SafeProcessRunner(
                project_root=self.project_root,
                max_timeout_seconds=30,
            )
        )

    def open_notepad(self) -> str:
        executable = self._notepad_path()

        if executable is None:
            return "Nie znaleziono pliku Notatnika."

        return self._spawn(
            [str(executable)],
            success_message="Otwieram Notatnik.",
            failure_label="Notatnika",
        )

    def open_steam(self) -> str:
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
                "Nie udało się otworzyć Steam: "
                f"{error}"
            )

    def open_discord(self) -> str:
        executable = self._first_existing(
            self._discord_candidates()
        )

        if executable is None:
            return (
                "Nie znaleziono pliku "
                "Discord Update.exe."
            )

        return self._spawn(
            [
                str(executable),
                "--processStart",
                "Discord.exe",
            ],
            success_message="Otwieram Discord.",
            failure_label="Discorda",
        )

    def open_opera(self) -> str:
        executable = self._first_existing(
            self._opera_candidates()
        )

        if executable is None:
            return (
                "Nie znaleziono pliku Opera GX."
            )

        return self._spawn(
            [str(executable)],
            success_message="Otwieram Opera GX.",
            failure_label="Opera GX",
        )

    def open_app(
        self,
        name: str,
    ) -> str:
        normalized = str(
            name
        ).casefold().strip()

        if normalized in {
            "opera",
            "opera gx",
            "chrome",
            "gx",
        }:
            return self.open_opera()

        if normalized in {
            "notatnik",
            "notepad",
        }:
            return self.open_notepad()

        if normalized == "steam":
            return self.open_steam()

        if normalized == "discord":
            return self.open_discord()

        return (
            f"Nie znam aplikacji: {normalized}"
        )

    def _spawn(
        self,
        command: list[str],
        *,
        success_message: str,
        failure_label: str,
    ) -> str:
        try:
            self.process_runner.spawn(
                command,
                cwd=self.project_root,
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
            ).resolve(
                strict=False
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
                return candidate.resolve(
                    strict=False
                )

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
