from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any
import uuid

from app.core.project_paths import resolve_project_root
from app.core.safe_process import SafeProcessRunner


_EXACT_DEVELOPMENT_HANDLERS = {
    "safe_development_prepare",
    "safe_development_deploy",
    "safe_development_rollback",
    "autonomous_autodev",
    "background_autodev",
    "autodev",
}


def is_real_development_thought(thought: object) -> bool:
    planned = dict(thought or {}) if isinstance(thought, dict) else {}
    if not bool(planned.get("can_execute", False)):
        return False
    handler = str(planned.get("handler", "")).casefold()
    if handler in _EXACT_DEVELOPMENT_HANDLERS:
        return True
    return bool(
        (planned.get("project_write") or planned.get("workspace_only"))
        and handler not in {
            "safe_development_status",
            "safe_development_discard",
            "self_improvement_advice",
        }
    )


class SelfDevelopmentConsoleSession:
    """Background Python monitor backed by truthful events from an actual run."""

    def __init__(self, project_root: object, thought: dict[str, Any]) -> None:
        self.project_root = resolve_project_root(project_root)
        session_id = uuid.uuid4().hex[:12]
        self.log_path = (
            self.project_root
            / "data"
            / "runtime"
            / "self_development_console"
            / f"{session_id}.jsonl"
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        plan = [str(item) for item in list(thought.get("plan", []) or [])]
        self.publish(
            "START",
            "Uruchamiam zatwierdzoną pracę w bezpiecznym środowisku Pythona.",
            details={
                "handler": str(thought.get("handler", "")),
                "plan": plan,
            },
        )
        self._launch_monitor()

    @classmethod
    def start(
        cls, project_root: object, thought: object
    ) -> SelfDevelopmentConsoleSession | None:
        planned = dict(thought or {}) if isinstance(thought, dict) else {}
        if not is_real_development_thought(planned):
            return None
        return cls(project_root, planned)

    def publish(
        self,
        stage: str,
        message: object,
        *,
        details: dict[str, Any] | None = None,
        terminal: bool = False,
    ) -> None:
        event = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "stage": str(stage or "PRACA").upper(),
            "message": " ".join(str(message or "").split())[:1200],
            "details": dict(details or {}),
            "terminal": bool(terminal),
        }
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()

    def _launch_monitor(self) -> None:
        if os.name != "nt":
            return
        if os.environ.get("QT_QPA_PLATFORM", "").casefold() == "offscreen":
            return
        script = self.project_root / "tools" / "self_development_console.py"
        if not script.is_file():
            return
        try:
            runner = SafeProcessRunner(
                project_root=self.project_root, allowed_executables=(sys.executable,)
            )
            runner.open(
                [sys.executable, str(script), str(self.log_path)],
                cwd=self.project_root,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, ValueError):
            return


__all__ = ["SelfDevelopmentConsoleSession", "is_real_development_thought"]
