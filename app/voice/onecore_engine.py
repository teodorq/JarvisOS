from __future__ import annotations

import base64
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import threading
from typing import Any

from app.core.safe_process import SafeProcessRunner


@dataclass(frozen=True)
class OneCoreVoice:
    id: str
    name: str
    languages: list[str]
    gender: str


class WindowsOneCoreEngine:
    """Small pyttsx3-compatible adapter for native Windows OneCore voices."""

    REGISTRY_PATH = r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens"
    supports_pitch = True

    def __init__(self) -> None:
        self.script = Path(__file__).with_name("onecore_speak.ps1")
        self._process_runner = SafeProcessRunner(
            project_root=Path(__file__).resolve().parents[2],
            allowed_executables=("powershell.exe",),
        )
        self._voices = self.available_voices()
        self._voice = self._voices[0].id if self._voices else ""
        self._rate = 158
        self._volume = 0.92
        self._pitch = 0.88
        self._message = ""
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.RLock()

    @classmethod
    def is_available(cls) -> bool:
        return os.name == "nt" and any(
            voice.languages == ["pl-PL"] for voice in cls.available_voices()
        ) and Path(__file__).with_name("onecore_speak.ps1").is_file()

    @classmethod
    def available_voices(cls) -> list[OneCoreVoice]:
        if os.name != "nt":
            return []
        try:
            import winreg
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cls.REGISTRY_PATH)
        except OSError:
            return []
        voices: list[OneCoreVoice] = []
        try:
            index = 0
            while True:
                try:
                    token = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                token_path = cls.REGISTRY_PATH + "\\" + token
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE, token_path
                    ) as key:
                        name = str(winreg.QueryValue(key, None) or token)
                        with winreg.OpenKey(key, "Attributes") as attributes:
                            gender = str(
                                winreg.QueryValueEx(attributes, "Gender")[0]
                            )
                except OSError:
                    name, gender = token, ""
                match = re.search(r"_([a-z]{2})([A-Z]{2})_", token)
                language = (
                    f"{match.group(1).lower()}-{match.group(2).upper()}"
                    if match else ""
                )
                voices.append(OneCoreVoice(
                    id=("HKEY_LOCAL_MACHINE\\" + token_path),
                    name=name,
                    languages=[language] if language else [],
                    gender=gender,
                ))
        finally:
            root.Close()
        return voices

    def setProperty(self, name: str, value: Any) -> None:  # noqa: N802
        if name == "rate":
            self._rate = max(100, min(int(value), 240))
        elif name == "volume":
            self._volume = max(0.25, min(float(value), 1.0))
        elif name == "pitch":
            self._pitch = max(0.7, min(float(value), 1.2))
        elif name == "voice":
            self._voice = str(value or "")

    def getProperty(self, name: str) -> Any:  # noqa: N802
        return {
            "voices": list(self._voices),
            "voice": self._voice,
            "rate": self._rate,
            "volume": self._volume,
            "pitch": self._pitch,
        }.get(name)

    def say(self, message: object) -> None:
        self._message = str(message or "").strip()

    def runAndWait(self) -> None:  # noqa: N802
        if not self._message:
            return
        encoded = base64.b64encode(self._message.encode("utf-8")).decode("ascii")
        command = [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(self.script),
            "-TextBase64", encoded, "-VoiceId", self._voice,
            "-Rate", str(self._rate), "-Volume", str(self._volume),
            "-Pitch", str(self._pitch),
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = self._process_runner.open(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        with self._lock:
            self._process = process
        try:
            if process.wait() != 0:
                raise RuntimeError("Natywny polski głos Windows nie odpowiedział.")
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
            self._message = ""

    def stop(self) -> None:
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=0.8)
        except subprocess.TimeoutExpired:
            process.kill()

