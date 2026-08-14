from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
from typing import Any
from uuid import uuid4
import zipfile

from .autonomy_governance_store import AutonomyGovernanceStore


_ALLOWED_TOP_LEVEL = {
    "app", "tests", "tools", "assets", "config", "software_engineer",
}
_ALLOWED_ROOT_FILES = {
    "main.py", "requirements.txt", "start_jarvis.bat", "start_jarvis.vbs", "install.bat",
    "JARVIS_OS.ico", "JARVIS_OS.png", ".gitignore",
}


class AutonomousReleaseService:
    """B66 bounded source snapshots and manually activated release records."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        strategic_execution: Any,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.strategic_execution = strategic_execution
        self.release_dir = self.project_root / "archive" / "autonomous_releases"

    def run_cycle(self) -> dict[str, Any]:
        policy = self.store.policy("B66")
        completed = int(self.strategic_execution.store.summary().get("completed", 0))
        minimum = int(policy.get("min_completed_executions", 1))
        if completed < minimum:
            return self._finish(
                "AUTONOMOUS_RELEASE_INSUFFICIENT_EVIDENCE",
                success=True,
                phase="READY",
                decision="HOLD",
                reason=f"Ukończone wykonania B58: {completed}/{minimum}.",
            )
        manifest = self._manifest()
        latest = self._latest_release()
        if latest and str(latest.get("manifest_hash", "")) == manifest["manifest_hash"]:
            return self._finish(
                "AUTONOMOUS_RELEASE_NO_CHANGES",
                success=True,
                phase="READY",
                decision="HOLD",
                release=latest,
            )
        return self.create_candidate(manifest=manifest)

    def create_candidate(
        self,
        *,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        policy = self.store.policy("B66")
        manifest = dict(manifest or self._manifest())
        release_id = f"jarvis-release-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:12]}"
        snapshot_path = ""
        if bool(policy.get("create_source_snapshot", True)):
            snapshot_path = str(self._create_snapshot(release_id, manifest))
        release = self.store.append_record("B66", {
            "release_id": release_id,
            "status": "READY_FOR_APPROVAL",
            "manifest_hash": manifest.get("manifest_hash", ""),
            "file_count": manifest.get("file_count", 0),
            "total_bytes": manifest.get("total_bytes", 0),
            "snapshot_path": snapshot_path,
            "requires_approval": True,
            "auto_approve": False,
            "created_at": self._now(),
        })
        return self._finish(
            "AUTONOMOUS_RELEASE_CANDIDATE_READY",
            success=True,
            phase="WAITING_APPROVAL",
            decision="WAITING_APPROVAL",
            release=release,
        )

    def activate(self, release_id: str = "") -> dict[str, Any]:
        release = self._release(release_id)
        if not release or str(release.get("status", "")) != "READY_FOR_APPROVAL":
            return self._response(
                "AUTONOMOUS_RELEASE_ACTIVATION_UNAVAILABLE",
                success=False,
                errors=["Brak kandydata wydania oczekującego na zgodę."],
            )
        releases = list(reversed(self.store.list_records("B66", limit=1000)))
        for item in releases:
            if str(item.get("status", "")) == "ACTIVE":
                item["status"] = "SUPERSEDED"
        release["status"] = "ACTIVE"
        release["activated_at"] = self._now()
        for index, item in enumerate(releases):
            if str(item.get("release_id", "")) == str(release.get("release_id", "")):
                releases[index] = release
                break
        self.store.replace_records("B66", releases)
        return self._finish(
            "AUTONOMOUS_RELEASE_ACTIVATED",
            success=True,
            phase="ACTIVE",
            decision="ACTIVATE",
            release=release,
        )

    def prepare_rollback(self) -> dict[str, Any]:
        active = self._active_release()
        previous = self._previous_release()
        if not active or not previous:
            return self._response(
                "AUTONOMOUS_RELEASE_ROLLBACK_UNAVAILABLE",
                success=False,
                errors=["Brak aktywnego i poprzedniego wydania B66."],
            )
        return self._finish(
            "AUTONOMOUS_RELEASE_ROLLBACK_READY",
            success=True,
            phase="WAITING_APPROVAL",
            decision="WAITING_APPROVAL",
            release=active,
            rollback_target=previous,
            reason="Przywrócenie plików wymaga jawnego potwierdzenia użytkownika.",
        )

    def restore_previous(self) -> dict[str, Any]:
        active = self._active_release()
        previous = self._previous_release()
        if not active or not previous:
            return self._response(
                "AUTONOMOUS_RELEASE_ROLLBACK_UNAVAILABLE",
                success=False,
                errors=["Brak poprzedniego snapshotu B66."],
            )
        snapshot = Path(str(previous.get("snapshot_path", "")))
        if not snapshot.is_file():
            return self._response(
                "AUTONOMOUS_RELEASE_SNAPSHOT_MISSING",
                success=False,
                errors=["Snapshot poprzedniego wydania nie istnieje."],
            )
        rollback_backup = self.release_dir / "rollback_backups" / (
            f"before_{previous.get('release_id', 'unknown')}_{uuid4().hex[:8]}.zip"
        )
        rollback_backup.parent.mkdir(parents=True, exist_ok=True)
        current_manifest = self._manifest()
        self._zip_files(rollback_backup, current_manifest["files"])
        self._safe_extract(snapshot)
        active["status"] = "ROLLED_BACK"
        active["rolled_back_at"] = self._now()
        previous["status"] = "ACTIVE"
        previous["restored_at"] = self._now()
        previous["rollback_backup"] = str(rollback_backup)
        releases = list(reversed(self.store.list_records("B66", limit=1000)))
        for index, item in enumerate(releases):
            release_id = str(item.get("release_id", ""))
            if release_id == str(active.get("release_id", "")):
                releases[index] = active
            elif release_id == str(previous.get("release_id", "")):
                releases[index] = previous
        self.store.replace_records("B66", releases)
        return self._finish(
            "AUTONOMOUS_RELEASE_ROLLED_BACK",
            success=True,
            phase="ACTIVE",
            decision="ROLLBACK",
            release=previous,
            rollback_backup=str(rollback_backup),
        )

    def status(self) -> dict[str, Any]:
        return self._response(
            "AUTONOMOUS_RELEASE_STATUS",
            success=True,
            release=self._active_release() or self._latest_release() or {},
            releases=self.store.list_records("B66", limit=10),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "AUTONOMOUS_RELEASE_HISTORY",
            success=True,
            releases=self.store.list_records("B66", limit=limit),
            history=self.store.history(stage="B66", limit=limit),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy("B66", {
            **dict(updates),
            "require_manual_activation": True,
            "auto_approve": False,
        })
        return self._response(
            "AUTONOMOUS_RELEASE_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def _manifest(self) -> dict[str, Any]:
        policy = self.store.policy("B66")
        max_files = int(policy.get("max_snapshot_files", 5000))
        files: list[dict[str, Any]] = []
        total_bytes = 0
        for path in self._source_paths():
            try:
                size = path.stat().st_size
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
            relative = path.relative_to(self.project_root).as_posix()
            files.append({"path": relative, "sha256": digest, "size": size})
            total_bytes += size
            if len(files) >= max_files:
                break
        compact = [[item["path"], item["sha256"], item["size"]] for item in files]
        manifest_hash = hashlib.sha256(
            json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "manifest_hash": manifest_hash,
            "file_count": len(files),
            "total_bytes": total_bytes,
            "files": files,
        }

    def _source_paths(self) -> list[Path]:
        values: list[Path] = []
        for name in sorted(_ALLOWED_TOP_LEVEL):
            directory = self.project_root / name
            if not directory.is_dir():
                continue
            for path in directory.rglob("*"):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts or path.suffix in {".pyc", ".tmp"}:
                    continue
                values.append(path)
        for name in sorted(_ALLOWED_ROOT_FILES):
            path = self.project_root / name
            if path.is_file():
                values.append(path)
        return sorted(set(values))

    def _create_snapshot(self, release_id: str, manifest: dict[str, Any]) -> Path:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        destination = self.release_dir / f"{release_id}.zip"
        maximum = int(self.store.policy("B66").get("max_snapshot_size_mb", 250)) * 1024 * 1024
        if int(manifest.get("total_bytes", 0)) > maximum:
            raise ValueError("Snapshot B66 przekracza dozwolony limit rozmiaru.")
        self._zip_files(destination, manifest.get("files", []))
        return destination

    def _zip_files(self, destination: Path, files: list[dict[str, Any]]) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in files:
                relative = str(item.get("path", ""))
                source = (self.project_root / relative).resolve(strict=False)
                if not self._inside_root(source) or not source.is_file():
                    continue
                archive.write(source, relative)

    def _safe_extract(self, snapshot: Path) -> None:
        with zipfile.ZipFile(snapshot) as archive:
            for member in archive.infolist():
                target = (self.project_root / member.filename).resolve(strict=False)
                if not self._inside_root(target):
                    raise ValueError("Niebezpieczna ścieżka w snapshocie B66.")
            archive.extractall(self.project_root)

    def _inside_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.project_root)
            return True
        except ValueError:
            return False

    def _release(self, release_id: str) -> dict[str, Any] | None:
        target = str(release_id).strip()
        if not target:
            return self._latest_release()
        for item in self.store.list_records("B66", limit=1000):
            if str(item.get("release_id", "")) == target:
                return item
        return None

    def _latest_release(self) -> dict[str, Any] | None:
        values = self.store.list_records("B66", limit=1)
        return values[0] if values else None

    def _active_release(self) -> dict[str, Any] | None:
        for item in self.store.list_records("B66", limit=1000):
            if str(item.get("status", "")).upper() == "ACTIVE":
                return item
        return None

    def _previous_release(self) -> dict[str, Any] | None:
        active = self._active_release()
        if not active:
            return None
        found = False
        for item in self.store.list_records("B66", limit=1000):
            if str(item.get("release_id", "")) == str(active.get("release_id", "")):
                found = True
                continue
            if found and str(item.get("snapshot_path", "")):
                return item
        return None

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        decision: str,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B66")
        release = extra.get("release", {})
        release = release if isinstance(release, dict) else {}
        runtime = self.store.update_runtime("B66", {
            "enabled": bool(self.store.policy("B66").get("enabled", True)),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_cycle_at": self._now(),
            "last_status": status,
            "last_decision": decision,
            "last_record_id": str(release.get("release_id", "")),
            "last_result": {"status": status, "success": success},
            "last_error": "" if success else str(extra.get("reason", "")),
        })
        response = self._response(
            status,
            success=success,
            runtime=runtime,
            decision=decision,
            **extra,
        )
        self.store.record_history("B66", {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": decision,
            "reason": str(extra.get("reason", "")),
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
            "stage": "B66",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B66"))),
            "policy": dict(extra.pop("policy", self.store.policy("B66"))),
            "summary": self.store.summary("B66"),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
