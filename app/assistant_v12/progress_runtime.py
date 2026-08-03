from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.assistant_v12.context_hub import utc_now
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


ProgressCallback = Callable[[dict[str, Any]], None]


class AssistantProgressRuntime:
    """B124 durable progress, explicit phases and bounded retry evidence."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "assistant_v12" / "progress_runtime.json",
            self._default,
        )
        self.callback: ProgressCallback | None = None

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.2",
            "active": {},
            "history": [],
            "updated_at": "",
        }

    def set_callback(self, callback: ProgressCallback | None) -> None:
        self.callback = callback

    def start(self, *, command: str, intent: str) -> dict[str, Any]:
        operation = {
            "operation_id": uuid4().hex[:16],
            "command": str(command)[:500],
            "intent": str(intent),
            "status": "RUNNING",
            "phase": "ROZUMIENIE",
            "progress_percent": 5,
            "retry_count": 0,
            "message": "Rozpoznaję intencję.",
            "started_at": utc_now(),
            "updated_at": utc_now(),
        }
        data = self._load()
        data["active"] = operation
        data["updated_at"] = operation["updated_at"]
        self.store.save(data)
        self._emit(operation)
        return operation

    def phase(self, phase: str, percent: int, message: str) -> dict[str, Any]:
        data = self._load()
        operation = dict(data.get("active", {}) or {})
        if not operation:
            return {}
        operation.update({
            "phase": str(phase).upper(),
            "progress_percent": max(0, min(int(percent), 100)),
            "message": str(message)[:500],
            "updated_at": utc_now(),
        })
        data["active"] = operation
        data["updated_at"] = operation["updated_at"]
        self.store.save(data)
        self._emit(operation)
        return operation

    def retry(self, message: str) -> dict[str, Any]:
        data = self._load()
        operation = dict(data.get("active", {}) or {})
        operation["retry_count"] = int(operation.get("retry_count", 0)) + 1
        operation.update({
            "phase": "RETRY",
            "message": str(message)[:500],
            "updated_at": utc_now(),
        })
        data["active"] = operation
        self.store.save(data)
        self._emit(operation)
        return operation

    def complete(self, response: str) -> dict[str, Any]:
        return self._finish("COMPLETED", "GOTOWE", 100, str(response)[:500])

    def fail(self, error: Exception | str) -> dict[str, Any]:
        return self._finish("FAILED", "BŁĄD", 100, str(error)[:500])

    def status(self) -> dict[str, Any]:
        data = self._load()
        active = dict(data.get("active", {}) or {})
        history = list(data.get("history", []) or [])
        latest = dict(history[-1]) if history else {}
        return {
            "status": "ASSISTANT_PROGRESS_RUNTIME_READY",
            "active": active,
            "operation_count": len(history) + (1 if active else 0),
            "completed_count": sum(item.get("status") == "COMPLETED" for item in history),
            "failed_count": sum(item.get("status") == "FAILED" for item in history),
            "retry_count": sum(int(item.get("retry_count", 0)) for item in history),
            "latest": latest,
        }

    def _finish(self, status: str, phase: str, percent: int, message: str) -> dict[str, Any]:
        data = self._load()
        operation = dict(data.get("active", {}) or {})
        if not operation:
            return {}
        operation.update({
            "status": status,
            "phase": phase,
            "progress_percent": percent,
            "message": message,
            "finished_at": utc_now(),
            "updated_at": utc_now(),
        })
        history = list(data.get("history", []) or [])
        history.append(operation)
        data["history"] = history[-200:]
        data["active"] = {}
        data["updated_at"] = operation["updated_at"]
        self.store.save(data)
        self._emit(operation)
        return operation

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

    def _emit(self, operation: dict[str, Any]) -> None:
        if self.callback is None:
            return
        try:
            self.callback(dict(operation))
        except Exception:
            return
