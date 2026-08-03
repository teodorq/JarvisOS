from __future__ import annotations

from pathlib import Path
import time
from typing import Iterable, Sequence

import pyautogui

from app.core.project_paths import (
    default_project_root,
)
from app.core.safe_process import (
    ProcessPolicyError,
    SafeProcessRunner,
)


class DesktopController:

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        process_runner: SafeProcessRunner | None = None,
        allowed_programs: Iterable[str | Path] = (),
    ) -> None:
        self.project_root = Path(
            project_root
            or default_project_root()
        ).expanduser().resolve(
            strict=False
        )
        self.allowed_programs = tuple(
            str(item)
            for item in allowed_programs
            if str(item).strip()
        )
        self.process_runner = (
            process_runner
            or SafeProcessRunner(
                project_root=self.project_root,
                allowed_executables=(
                    self.allowed_programs
                ),
                max_timeout_seconds=30,
            )
        )

    def move_mouse(
        self,
        x,
        y,
        duration=0.5,
    ) -> None:
        pyautogui.moveTo(
            int(x),
            int(y),
            duration=duration,
        )

    def click(
        self,
    ) -> None:
        time.sleep(0.15)
        pyautogui.click(
            button="left"
        )
        time.sleep(0.15)

    def double_click(
        self,
    ) -> None:
        time.sleep(0.15)
        pyautogui.doubleClick(
            button="left"
        )
        time.sleep(0.15)

    def right_click(
        self,
    ) -> None:
        time.sleep(0.15)
        pyautogui.rightClick()
        time.sleep(0.15)

    def write(
        self,
        text,
    ) -> None:
        pyautogui.write(
            text,
            interval=0.03,
        )

    def press(
        self,
        key,
    ) -> None:
        pyautogui.press(
            key
        )

    def hotkey(
        self,
        *keys,
    ) -> None:
        pyautogui.hotkey(
            *keys
        )

    def open_program(
        self,
        program: Sequence[str],
    ) -> bool:
        if isinstance(
            program,
            (str, bytes),
        ):
            return False

        command = [
            str(item)
            for item in program
        ]

        if not command:
            return False

        try:
            self.process_runner.spawn(
                command,
                cwd=self.project_root,
                allowed_executables=(
                    self.allowed_programs
                ),
            )
            return True

        except (
            OSError,
            ProcessPolicyError,
        ):
            return False

    def wait(
        self,
        seconds,
    ) -> None:
        time.sleep(
            max(
                0.0,
                float(seconds),
            )
        )
