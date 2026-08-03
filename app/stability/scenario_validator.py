from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.stability.common import bounded, utc_iso


class ScenarioValidationCenter:
    """B111 deterministic local scenario checks for a real JARVIS workspace."""

    REQUIRED_PATHS = (
        "main.py",
        "app/ai/brain.py",
        "app/gui/main_window.py",
        "app/assistant/controller.py",
        "tests",
    )

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.project_root / "data" / "stability" / "scenario_validation.json",
            lambda: {"runs": []},
        )

    def run(self, runtime_status: dict[str, Any] | None = None) -> dict[str, Any]:
        checks = [
            self._layout_check(),
            self._integrity_check(),
            self._report_directory_check(),
            self._runtime_check(runtime_status or {}),
            self._safe_defaults_check(runtime_status or {}),
        ]
        passed = sum(item["passed"] for item in checks)
        result = {
            "run_id": uuid4().hex[:16],
            "created_at": utc_iso(),
            "status": "PASSED" if passed == len(checks) else "FAILED",
            "passed": passed,
            "failed": len(checks) - passed,
            "total": len(checks),
            "checks": checks,
        }
        state = self.store.load()
        state["runs"] = bounded(list(state.get("runs", [])) + [result], 40)
        self.store.save(state)
        return result

    def status(self) -> dict[str, Any]:
        runs = list(self.store.load().get("runs", []))
        latest = dict(runs[-1]) if runs else {}
        return {
            "status": "REAL_SCENARIO_VALIDATION_READY",
            "run_count": len(runs),
            "latest_status": latest.get("status", "NOT_RUN"),
            "latest_passed": latest.get("passed", 0),
            "latest_total": latest.get("total", 0),
            "latest_run": latest,
        }

    def _layout_check(self) -> dict[str, Any]:
        missing = [item for item in self.REQUIRED_PATHS if not (self.project_root / item).exists()]
        return self._result("PROJECT_LAYOUT", not missing, "brak: " + ", ".join(missing) if missing else "układ projektu poprawny")

    def _integrity_check(self) -> dict[str, Any]:
        path = self.project_root / "config" / "business_integrity_manifest.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            file_count = len(dict(data.get("files", {}) or {}))
            passed = file_count > 0
            detail = f"manifest zawiera {file_count} plików"
        except (OSError, UnicodeError, json.JSONDecodeError):
            passed, detail = False, "manifest niedostępny lub nieprawidłowy"
        return self._result("INTEGRITY_MANIFEST", passed, detail)

    def _report_directory_check(self) -> dict[str, Any]:
        target = self.project_root / "AI_PLIKI" / "reports"
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".b111_write_probe"
            probe.write_text("JARVIS B111", encoding="utf-8")
            probe.unlink()
            passed, detail = True, str(target)
        except OSError as error:
            passed, detail = False, type(error).__name__
        return self._result("LOCAL_REPORT_STORAGE", passed, detail)

    def _runtime_check(self, status: dict[str, Any]) -> dict[str, Any]:
        required = ("conversation", "intelligence", "productivity")
        missing = [key for key in required if not status.get(key)]
        return self._result("RUNTIME_SERVICES", not missing, "brak: " + ", ".join(missing) if missing else "usługi odpowiadają")

    def _safe_defaults_check(self, status: dict[str, Any]) -> dict[str, Any]:
        safety = dict(status.get("safety", {}) or {})
        passed = safety.get("auto_approve") is False and safety.get("remote_code_execution") is False
        return self._result("SAFE_DEFAULTS", passed, "auto-approve OFF, kod zdalny OFF" if passed else "naruszone bezpieczne ustawienia")

    @staticmethod
    def _result(name: str, passed: bool, detail: str) -> dict[str, Any]:
        return {"name": name, "passed": bool(passed), "detail": str(detail)}
