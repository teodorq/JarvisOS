from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.safe_process import ProcessResult, SafeProcessRunner


TASK_NAME = "JARVIS OS Autostart"


def autostart_status() -> dict[str, Any]:
    """Return a small, locale-independent Windows task summary."""
    if os.name != "nt":
        return {"supported": False, "installed": False, "state": "UNSUPPORTED"}
    script = (
        "$task=Get-ScheduledTask -TaskName 'JARVIS OS Autostart' "
        "-ErrorAction SilentlyContinue;"
        "if($null -eq $task){"
        "[ordered]@{installed=$false;state='NOT_INSTALLED'}|"
        "ConvertTo-Json -Compress"
        "}else{[ordered]@{installed=$true;state=[string]$task.State}|"
        "ConvertTo-Json -Compress}"
    )
    result = _powershell(["-Command", script], timeout=12)
    if result.returncode:
        raise RuntimeError("Nie udało się odczytać stanu autostartu.")
    value = _json_line(result.stdout)
    return {
        "supported": True,
        "installed": bool(value.get("installed")),
        "state": str(value.get("state") or "UNKNOWN").upper(),
    }


def set_autostart(project_root: str | Path, *, enabled: bool) -> dict[str, Any]:
    """Install or remove the existing limited-user scheduled task."""
    root = Path(project_root).resolve()
    installer = root / "tools" / "install_jarvis_autostart.ps1"
    if not (root / "main.py").is_file() or not installer.is_file():
        raise RuntimeError("Brakuje plików potrzebnych do ustawienia autostartu.")
    arguments = [
        "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(installer), "-ProjectRoot", str(root),
    ]
    arguments.append("-NoStart" if enabled else "-Remove")
    result = _powershell(arguments, timeout=30)
    if result.returncode:
        raise RuntimeError("Nie udało się zmienić autostartu JARVIS OS.")
    status = autostart_status()
    status["changed"] = True
    status["enabled"] = bool(enabled)
    return status


def _powershell(arguments: list[str], *, timeout: int) -> ProcessResult:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    executable = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    command = str(executable) if executable.is_file() else "powershell.exe"
    project_root = Path(__file__).resolve().parents[2]
    runner = SafeProcessRunner(
        project_root=project_root,
        allowed_executables=(command,),
        max_timeout_seconds=60,
        max_output_chars=4000,
    )
    return runner.run([command, *arguments], timeout=timeout)


def _json_line(output: str) -> dict[str, Any]:
    for line in reversed(str(output or "").splitlines()):
        try:
            value = json.loads(line.strip())
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    raise RuntimeError("Autostart zwrócił nieprawidłową odpowiedź.")


__all__ = ["TASK_NAME", "autostart_status", "set_autostart"]
