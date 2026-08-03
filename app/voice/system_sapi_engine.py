"""Persistent Windows SAPI output using the user's default system voice."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import queue
import subprocess
import threading
from typing import Any

from app.core.safe_process import SafeProcessRunner


class WindowsSystemSapiEngine:
    """pyttsx3-compatible speech engine isolated from pythonw audio routing."""

    cross_thread_stop_safe = False
    supports_pitch = False

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        process_runner: SafeProcessRunner | None = None,
    ) -> None:
        self.project_root = Path(
            project_root or Path(__file__).resolve().parents[2]
        ).resolve()
        self.script = Path(__file__).with_name("system_sapi_worker.ps1")
        self._process_runner = process_runner or SafeProcessRunner(
            project_root=self.project_root,
            allowed_executables=("powershell.exe",),
        )
        self._rate = 170
        self._volume = 1.0
        self._message = ""
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._responses: queue.Queue[str] = queue.Queue()
        self._lock = threading.RLock()
        self._request_number = 0
        self._ensure_process()

    @classmethod
    def is_available(cls) -> bool:
        return (
            os.name == "nt"
            and Path(__file__).with_name("system_sapi_worker.ps1").is_file()
        )

    def setProperty(self, name: str, value: Any) -> None:  # noqa: N802
        if name == "rate":
            self._rate = max(100, min(int(value), 240))
        elif name == "volume":
            self._volume = max(0.0, min(float(value), 1.0))

    def getProperty(self, name: str) -> Any:  # noqa: N802
        return {
            "voices": [],
            "voice": "SYSTEM_DEFAULT",
            "rate": self._rate,
            "volume": self._volume,
        }.get(name)

    def say(self, message: object) -> None:
        self._message = " ".join(str(message or "").split()).strip()

    def runAndWait(self) -> None:  # noqa: N802
        message = self._message
        self._message = ""
        if not message:
            return

        last_error = "Systemowy głos Windows nie odpowiedział."
        for attempt in range(2):
            process = self._ensure_process()
            with self._lock:
                self._request_number += 1
                request_id = str(self._request_number)
            encoded = base64.b64encode(message.encode("utf-8")).decode("ascii")
            payload = (
                f"{request_id}\t{self._rate}\t{self._volume:.3f}\t{encoded}\n"
            )
            try:
                if process.stdin is None:
                    raise RuntimeError("Kanał wejściowy głosu jest niedostępny.")
                process.stdin.write(payload)
                process.stdin.flush()
                timeout = max(8.0, min(90.0, len(message) / 7.0 + 8.0))
                response = self._responses.get(timeout=timeout)
                if response == f"OK\t{request_id}":
                    return
                if response.startswith(f"ERROR\t{request_id}\t"):
                    last_error = response.split("\t", 2)[-1]
                else:
                    last_error = "Proces głosu zakończył się przed odpowiedzią."
            except (BrokenPipeError, OSError, queue.Empty, RuntimeError) as error:
                last_error = str(error) or last_error
            self._drop_process(process)
            if attempt == 0:
                continue
        raise RuntimeError(last_error)

    def stop(self) -> None:
        with self._lock:
            process = self._process
        if process is not None:
            self._drop_process(process)

    def close(self) -> None:
        self.stop()

    def _ensure_process(self) -> subprocess.Popen[str]:
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                return process

            self._drain_responses()
            command = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.script),
            ]
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = self._process_runner.open(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
            )
            self._process = process
            self._reader = threading.Thread(
                target=self._read_responses,
                args=(process,),
                name="jarvis-system-sapi-reader",
                daemon=True,
            )
            self._reader.start()

        try:
            ready = self._responses.get(timeout=5.0)
        except queue.Empty as error:
            self._drop_process(process)
            raise RuntimeError("Systemowy głos Windows nie uruchomił się.") from error
        if ready != "READY":
            self._drop_process(process)
            raise RuntimeError("Systemowy głos Windows zwrócił błąd startu.")
        return process

    def _read_responses(self, process: subprocess.Popen[str]) -> None:
        stdout = process.stdout
        if stdout is None:
            self._responses.put("__EOF__")
            return
        try:
            for line in stdout:
                self._responses.put(line.rstrip("\r\n"))
        finally:
            self._responses.put("__EOF__")

    def _drop_process(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            if self._process is process:
                self._process = None
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)

    def _drain_responses(self) -> None:
        while True:
            try:
                self._responses.get_nowait()
            except queue.Empty:
                return


__all__ = ["WindowsSystemSapiEngine"]
