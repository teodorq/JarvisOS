from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import ast
import shutil
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore


class SelfMaintenanceService:
    """B67 bounded project hygiene scanner and explicit safe cleanup."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store

    def scan(self) -> dict[str, Any]:
        policy = self.store.policy("B67")
        maximum = int(policy.get("max_scan_files", 5000))
        findings: list[dict[str, Any]] = []
        scanned = 0
        for path in self.project_root.rglob("*"):
            if scanned >= maximum:
                break
            if self._excluded(path):
                continue
            if path.is_dir():
                if path.name in {"__pycache__", ".pytest_cache"}:
                    findings.append(self._finding(
                        "SAFE_CACHE_DIRECTORY",
                        path,
                        severity="LOW",
                        safe_cleanup=True,
                    ))
                elif path.name.startswith("_B") and "INSTALLER" in path.name:
                    findings.append(self._finding(
                        "INSTALLER_LEFTOVER",
                        path,
                        severity="LOW",
                        safe_cleanup=True,
                    ))
                continue
            if not path.is_file():
                continue
            scanned += 1
            if path.suffix == ".pyc":
                findings.append(self._finding(
                    "PYTHON_CACHE_FILE", path, severity="LOW", safe_cleanup=True
                ))
                continue
            if path.parent == self.project_root and (
                path.name.startswith("APPLY_B") and path.suffix.casefold() == ".cmd"
            ):
                findings.append(self._finding(
                    "INSTALLER_COMMAND_LEFTOVER", path, severity="LOW", safe_cleanup=True
                ))
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > int(policy.get("large_file_mb", 20)) * 1024 * 1024:
                findings.append(self._finding(
                    "LARGE_FILE", path, severity="MEDIUM", safe_cleanup=False,
                    details={"size_bytes": size},
                ))
            if path.suffix == ".py":
                syntax_error = self._syntax_error(path)
                if syntax_error:
                    findings.append(self._finding(
                        "PYTHON_SYNTAX_ERROR", path, severity="HIGH", safe_cleanup=False,
                        details={"error": syntax_error},
                    ))
                warning = self._invalid_escape_hint(path)
                if warning:
                    findings.append(self._finding(
                        "INVALID_ESCAPE_HINT", path, severity="LOW", safe_cleanup=False,
                        details={"line": warning},
                    ))
        findings = findings[: int(policy.get("max_findings", 500))]
        existing = self.store.list_records("B67", limit=10000)
        signatures = {
            (str(item.get("category", "")), str(item.get("path", "")))
            for item in existing
        }
        fresh = [
            item for item in findings
            if (str(item.get("category", "")), str(item.get("path", "")))
            not in signatures
        ]
        for item in fresh:
            self.store.append_record("B67", item)
        return self._finish(
            "SELF_MAINTENANCE_SCAN_COMPLETED",
            success=True,
            phase="READY",
            decision="OBSERVE",
            findings=findings,
            new_findings=len(fresh),
            scanned_files=scanned,
        )

    def apply_safe_cleanup(self) -> dict[str, Any]:
        removed: list[str] = []
        errors: list[str] = []
        candidates = self.store.list_records("B67", limit=10000)
        for item in candidates:
            if not bool(item.get("safe_cleanup", False)):
                continue
            path = (self.project_root / str(item.get("path", ""))).resolve(strict=False)
            if not self._inside_root(path) or not path.exists():
                continue
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed.append(str(item.get("path", "")))
            except OSError as error:
                errors.append(f"{path}: {error}")
        status = (
            "SELF_MAINTENANCE_SAFE_CLEANUP_COMPLETED"
            if not errors else "SELF_MAINTENANCE_SAFE_CLEANUP_PARTIAL"
        )
        return self._finish(
            status,
            success=not errors,
            phase="READY" if not errors else "PARTIAL",
            decision="CLEANUP",
            removed=removed,
            errors=errors,
        )

    def status(self) -> dict[str, Any]:
        return self._response(
            "SELF_MAINTENANCE_STATUS",
            success=True,
            findings=self.store.list_records("B67", limit=30),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "SELF_MAINTENANCE_HISTORY",
            success=True,
            findings=self.store.list_records("B67", limit=limit),
            history=self.store.history(stage="B67", limit=limit),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy("B67", {
            **dict(updates),
            "auto_cleanup": False,
            "auto_approve": False,
        })
        return self._response(
            "SELF_MAINTENANCE_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        decision: str,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B67")
        runtime = self.store.update_runtime("B67", {
            "enabled": bool(self.store.policy("B67").get("enabled", True)),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_cycle_at": self._now(),
            "last_status": status,
            "last_decision": decision,
            "last_result": {"status": status, "success": success},
            "last_error": "; ".join(extra.get("errors", [])[:5]),
        })
        response = self._response(
            status,
            success=success,
            runtime=runtime,
            decision=decision,
            **extra,
        )
        self.store.record_history("B67", {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": decision,
            "reason": f"Znaleziska: {len(extra.get('findings', []))}",
            "error": "; ".join(extra.get("errors", [])[:5]),
        })
        return response

    def _response(
        self,
        status: str,
        *,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "autonomy_governance_suite",
            "stage": "B67",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B67"))),
            "policy": dict(extra.pop("policy", self.store.policy("B67"))),
            "summary": self.store.summary("B67"),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    def _finding(
        self,
        category: str,
        path: Path,
        *,
        severity: str,
        safe_cleanup: bool,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "finding_id": f"maintenance-{uuid4().hex}",
            "status": "OPEN",
            "category": category,
            "path": path.relative_to(self.project_root).as_posix(),
            "severity": severity,
            "safe_cleanup": safe_cleanup,
            "details": dict(details or {}),
            "created_at": self._now(),
        }

    @staticmethod
    def _syntax_error(path: Path) -> str:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            return ""
        except (OSError, UnicodeError):
            return ""
        except SyntaxError as error:
            return f"{error.msg} (linia {error.lineno})"

    @staticmethod
    def _invalid_escape_hint(path: Path) -> int | None:
        try:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "\\long_" in line or "app\\long_" in line:
                    return number
        except (OSError, UnicodeError):
            return None
        return None

    def _excluded(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.project_root)
        except ValueError:
            return True
        return bool(
            set(relative.parts)
            & {"archive", "AI_PLIKI", ".git", ".venv", "venv", "env"}
        )

    def _inside_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.project_root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
