from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any, Callable

from app.ai.actions import ActionTypes
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


_IDEMPOTENT_ACTIONS = {
    ActionTypes.OPEN_APP,
    ActionTypes.OPEN_WEBSITE,
    ActionTypes.OPEN_URL,
    ActionTypes.GOOGLE_SEARCH,
    ActionTypes.YOUTUBE_SEARCH,
    ActionTypes.SCREENSHOT,
    ActionTypes.VISION_ANALYZE,
}
_FAILURE_MARKERS = (
    "nie udało",
    "nie udalo",
    "nie znaleziono",
    "błąd",
    "blad",
    "failed",
    "error",
    "odmowa",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReliableDesktopService:
    """B97 bounded execution, observation and retry for desktop actions."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        max_attempts: int = 2,
        retry_delay: float = 0.35,
        window_probe: Callable[[], list[str]] | None = None,
    ) -> None:
        root = resolve_project_root(project_root)
        self.max_attempts = max(1, min(int(max_attempts), 3))
        self.retry_delay = max(0.0, min(float(retry_delay), 2.0))
        self.window_probe = window_probe or self._window_titles
        self.store = JsonStore(
            root / "data" / "assistant" / "desktop_reliability.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "executions": [],
            "success_count": 0,
            "failure_count": 0,
            "unverified_count": 0,
        }


    @staticmethod
    def supports(action: dict[str, Any]) -> bool:
        return str(action.get("action_type", "")) not in {
            ActionTypes.REMEMBER,
            ActionTypes.ADD_TASK,
            ActionTypes.MEMORY_SUMMARY,
            ActionTypes.UNKNOWN,
        }

    def execute_action(self, action: dict[str, Any], executor: Any) -> str:
        action_type = str(action.get("action_type", "unknown"))
        attempts_allowed = (
            self.max_attempts
            if action_type in _IDEMPOTENT_ACTIONS
            else 1
        )
        result_text = ""
        verification = "FAILED"
        error_text = ""
        attempts = 0

        for attempt in range(1, attempts_allowed + 1):
            attempts = attempt
            before = self._safe_windows()
            try:
                result = executor.execute_action(action)
                result_text = str(result)
                error_text = ""
            except Exception as error:  # safety boundary around legacy skills
                result_text = ""
                error_text = f"{type(error).__name__}: {error}"

            after = self._safe_windows()
            verification = self._verify(
                action=action,
                result=result_text,
                error=error_text,
                before=before,
                after=after,
            )
            if verification in {"VERIFIED", "UNVERIFIED"}:
                break
            if attempt < attempts_allowed:
                time.sleep(self.retry_delay)

        self._record(
            action=action,
            result=result_text,
            error=error_text,
            verification=verification,
            attempts=attempts,
        )
        if verification == "VERIFIED":
            return f"{result_text} [B97: potwierdzono, próby {attempts}]"
        if verification == "UNVERIFIED":
            return f"{result_text} [B97: wykonano, brak twardego sygnału]"
        detail = error_text or result_text or "brak wyniku"
        return f"Akcja nie została potwierdzona po {attempts} próbie/próbach: {detail}"

    def status(self) -> dict[str, Any]:
        data = self.store.load()
        if not isinstance(data, dict):
            data = self._default()
        executions = list(data.get("executions", []) or [])
        return {
            "status": "DESKTOP_RELIABILITY_READY",
            "max_attempts": self.max_attempts,
            "executions": len(executions),
            "success_count": int(data.get("success_count", 0)),
            "failure_count": int(data.get("failure_count", 0)),
            "unverified_count": int(data.get("unverified_count", 0)),
            "last": executions[-1] if executions else None,
        }

    @staticmethod
    def _verify(
        *,
        action: dict[str, Any],
        result: str,
        error: str,
        before: list[str],
        after: list[str],
    ) -> str:
        if error:
            return "FAILED"
        folded = result.casefold()
        if not result or any(marker in folded for marker in _FAILURE_MARKERS):
            return "FAILED"

        action_type = str(action.get("action_type", ""))
        target = str(action.get("target", action.get("url", ""))).casefold()
        if action_type == ActionTypes.OPEN_APP and target:
            normalized = target.replace("opera gx", "opera")
            if any(normalized in title.casefold() for title in after):
                return "VERIFIED"
            if before != after and after:
                return "VERIFIED"
            return "UNVERIFIED"

        if action_type in {
            ActionTypes.OPEN_WEBSITE,
            ActionTypes.OPEN_URL,
            ActionTypes.GOOGLE_SEARCH,
            ActionTypes.YOUTUBE_SEARCH,
        }:
            return "VERIFIED" if before != after and after else "UNVERIFIED"

        return "VERIFIED"

    def _record(
        self,
        *,
        action: dict[str, Any],
        result: str,
        error: str,
        verification: str,
        attempts: int,
    ) -> None:
        data = self.store.load()
        if not isinstance(data, dict):
            data = self._default()
        executions = list(data.get("executions", []) or [])
        executions.append({
            "created_at": utc_now(),
            "action_type": str(action.get("action_type", "unknown")),
            "target": str(action.get("target", action.get("url", "")))[:200],
            "result": result[:500],
            "error": error[:500],
            "verification": verification,
            "attempts": attempts,
        })
        data["executions"] = executions[-200:]
        if verification == "VERIFIED":
            data["success_count"] = int(data.get("success_count", 0)) + 1
        elif verification == "UNVERIFIED":
            data["unverified_count"] = int(data.get("unverified_count", 0)) + 1
        else:
            data["failure_count"] = int(data.get("failure_count", 0)) + 1
        self.store.save(data)

    def _safe_windows(self) -> list[str]:
        try:
            return [str(item) for item in self.window_probe() if str(item).strip()]
        except Exception:
            return []

    @staticmethod
    def _window_titles() -> list[str]:
        try:
            import pygetwindow as gw
            return [
                str(window.title).strip()
                for window in gw.getAllWindows()
                if str(window.title or "").strip()
            ]
        except Exception:
            return []
