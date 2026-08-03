from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any
import zipfile

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .audit_center import BusinessAuditCenter
from .business_config import BusinessConfigStore
from .business_license import BusinessLicenseManager
from .disaster_recovery import BusinessDisasterRecovery
from .installation_manager import BusinessInstallationManager
from .update_center import BusinessUpdateCenter


class BusinessReleaseCandidate:
    """B88 RC1 readiness gates, signed-by-hash export and verification."""

    VERSION = "1.0.0-rc.1"
    RELEASE_NAME = "JARVIS OS RC1"
    VALIDATION_MAX_AGE_DAYS = 30

    def __init__(
        self,
        project_root: str | Path,
        *,
        installation_manager: BusinessInstallationManager | None = None,
        disaster_recovery: BusinessDisasterRecovery | None = None,
        audit_center: BusinessAuditCenter | None = None,
        update_center: BusinessUpdateCenter | None = None,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "release_candidate.json"
        self.validation_path = self.paths.data / "business" / "release_validation.json"
        self.export_dir = self.paths.ai_files / "business_release"
        self.integrity_path = self.paths.root / "config" / "business_integrity_manifest.json"
        self.installation_manager = installation_manager or BusinessInstallationManager(self.paths.root)
        self.disaster_recovery = disaster_recovery or BusinessDisasterRecovery(self.paths.root)
        self.audit_center = audit_center or BusinessAuditCenter(self.paths.root)
        self.update_center = update_center or BusinessUpdateCenter(self.paths.root)
        self.config_store = BusinessConfigStore(self.paths.root)
        self.license_manager = BusinessLicenseManager(self.paths.root)
        self._store = JsonStore(self.path, self._default_payload)

    def status(self) -> dict[str, Any]:
        config = self.config_store.ensure()
        installation = self.installation_manager.status()
        license_status = self.license_manager.status(config)
        integrity = self._verify_integrity()
        recovery = self.disaster_recovery.status()
        audit = self.audit_center.status()
        updates = self.update_center.status()
        validation = self._validation_status()
        latest_checkpoint = dict(recovery.get("latest_checkpoint", {}) or {})
        packages = list(updates.get("packages", []) or [])
        invalid_updates = [item for item in packages if not item.get("valid")]
        gates = {
            "installation_ready": bool(installation.get("installation_ready")),
            "license_active": bool(license_status.get("active")),
            "integrity_verified": integrity.get("status") == "VERIFIED",
            "checkpoint_verified": self._checkpoint_after_validation(
                latest_checkpoint,
                validation,
            ),
            "test_matrix_passed": validation.get("status") == "PASSED",
            "audit_available": bool(audit.get("success")),
            "updates_clean": not invalid_updates,
            "safety_locked": self._safety_locked(config),
        }
        ready = all(gates.values())
        payload = self._normalize(self._store.load())
        self._store.save(payload)
        releases = sorted(self.export_dir.glob("JARVIS_OS_BUSINESS_RC1_*.zip"))
        return {
            "success": True,
            "status": "BUSINESS_RELEASE_CANDIDATE_STATUS",
            "operation": "business_release_candidate",
            "stage": "B88",
            "runtime": {
                "phase": "READY" if ready else "ATTENTION_REQUIRED",
                "running": False,
                "paused": False,
                "cycles_completed": len(payload["history"]),
                "last_decision": "RC_READY" if ready else "GATES_PENDING",
            },
            "version": self.VERSION,
            "release_name": self.RELEASE_NAME,
            "release_ready": ready,
            "gates": gates,
            "validation": validation,
            "installation": installation,
            "license": license_status,
            "integrity": integrity,
            "latest_checkpoint": latest_checkpoint,
            "invalid_update_count": len(invalid_updates),
            "release_count": len(releases),
            "latest_release": str(releases[-1]) if releases else None,
            "decision": "RC_READY" if ready else "GATES_PENDING",
            "reason": (
                "Wszystkie bramki RC1 są spełnione."
                if ready
                else "Release Candidate wymaga domknięcia wskazanych bramek."
            ),
            "report_path": str(self.path),
            "errors": [name for name, passed in gates.items() if not passed],
        }

    def record_validation(self, suites: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "schema_version": 1,
            "type": "JARVIS_BUSINESS_RELEASE_VALIDATION",
            "version": self.VERSION,
            "status": "PASSED",
            "validated_at": self._now(),
            "platform": "WINDOWS",
            "suites": dict(suites or {}),
            "safety": {
                "auto_approve": False,
                "max_active_executions": 1,
                "remote_code_execution": False,
            },
        }
        self.validation_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.validation_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.validation_path)
        state = self._normalize(self._store.load())
        self._append_history(state, "VALIDATION_RECORDED", "PASSED")
        self._store.save(state)
        response = self.status()
        response["status"] = "BUSINESS_RELEASE_VALIDATION_RECORDED"
        response["decision"] = "PASSED"
        return response

    def export_release_candidate(self) -> dict[str, Any]:
        current = self.status()
        if not current.get("release_ready"):
            return self._error(
                "RELEASE_GATES_NOT_READY",
                "Nie wszystkie bramki B88 są spełnione.",
                list(current.get("errors", [])),
            )
        setup = self.installation_manager.export_setup_package()
        setup_record = dict(setup.get("setup_package", {}) or {})
        setup_path = Path(str(setup_record.get("path", "")))
        if not setup.get("success") or not setup_path.is_file():
            return self._error("SETUP_PACKAGE_MISSING", "Nie udało się utworzyć pakietu B87.")
        self.export_dir.mkdir(parents=True, exist_ok=True)
        target = self.export_dir / "JARVIS_OS_BUSINESS_RC1_1_0_0.zip"
        temporary_target = target.with_suffix(".zip.tmp")
        temporary_target.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(prefix="JARVIS_B88_RC1_") as value:
            staging = Path(value)
            setup_name = setup_path.name
            shutil.copy2(setup_path, staging / setup_name)
            setup_digest = hashlib.sha256(setup_path.read_bytes()).hexdigest()
            release_manifest = {
                "schema_version": 1,
                "type": "JARVIS_BUSINESS_RELEASE_CANDIDATE",
                "release_name": self.RELEASE_NAME,
                "version": self.VERSION,
                "created_at": self._now(),
                "artifacts": {setup_name: setup_digest},
                "gates": current["gates"],
                "validation": current["validation"],
                "safety": {
                    "auto_approve": False,
                    "confirmation_required": True,
                    "max_active_executions": 1,
                    "remote_code_execution": False,
                },
            }
            (staging / "JARVIS_RC1_RELEASE_MANIFEST.json").write_text(
                json.dumps(release_manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (staging / "RELEASE_NOTES_RC1.txt").write_text(
                self._release_notes(), encoding="utf-8", newline="\r\n"
            )
            (staging / "SHA256SUMS.txt").write_text(
                f"{setup_digest}  {setup_name}\n", encoding="utf-8"
            )
            with zipfile.ZipFile(
                temporary_target,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                for item in sorted(staging.iterdir()):
                    archive.write(item, item.name)
        temporary_target.replace(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        state = self._normalize(self._store.load())
        state["last_release"] = {
            "path": str(target),
            "sha256": digest,
            "version": self.VERSION,
            "created_at": self._now(),
            "verification": "VERIFIED",
        }
        self._append_history(state, "RC1_EXPORTED", "VERIFIED")
        self._store.save(state)
        response = self.status()
        response.update({
            "status": "BUSINESS_RELEASE_CANDIDATE_EXPORTED",
            "release": state["last_release"],
            "decision": "EXPORTED",
            "reason": "RC1 zawiera zweryfikowany instalator B87 i manifest SHA-256.",
        })
        return response

    def verify_release_candidate(self) -> dict[str, Any]:
        state = self._normalize(self._store.load())
        record = dict(state.get("last_release", {}) or {})
        path = Path(str(record.get("path", "")))
        errors: list[str] = []
        if not path.is_file():
            errors.append("Brak wyeksportowanego RC1.")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != str(record.get("sha256", "")):
            errors.append("Niezgodny SHA-256 archiwum RC1.")
        if not errors:
            errors.extend(self._verify_release_archive(path))
        response = self.status()
        response.update({
            "success": not errors,
            "status": "BUSINESS_RELEASE_CANDIDATE_VERIFIED",
            "verification": "VERIFIED" if not errors else "FAILED",
            "decision": "VERIFIED" if not errors else "REJECT",
            "reason": "Pakiet RC1 jest spójny." if not errors else "Pakiet RC1 wymaga uwagi.",
            "errors": errors,
        })
        return response

    def _verify_release_archive(self, path: Path) -> list[str]:
        errors: list[str] = []
        try:
            with zipfile.ZipFile(path) as archive:
                damaged = archive.testzip()
                if damaged:
                    errors.append(f"Uszkodzony element: {damaged}")
                manifest = json.loads(
                    archive.read("JARVIS_RC1_RELEASE_MANIFEST.json").decode("utf-8")
                )
                if manifest.get("type") != "JARVIS_BUSINESS_RELEASE_CANDIDATE":
                    errors.append("Nieprawidłowy typ manifestu RC1.")
                for name, expected in dict(manifest.get("artifacts", {})).items():
                    safe = PurePosixPath(str(name))
                    if safe.is_absolute() or ".." in safe.parts:
                        errors.append(f"Niebezpieczna nazwa artefaktu: {name}")
                        continue
                    actual = hashlib.sha256(archive.read(str(name))).hexdigest()
                    if actual != str(expected):
                        errors.append(f"Niezgodny SHA-256 artefaktu: {name}")
        except (OSError, KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
            errors.append(str(error))
        return errors

    def _validation_status(self) -> dict[str, Any]:
        if not self.validation_path.is_file():
            return {"status": "PENDING", "version": self.VERSION, "validated_at": None}
        try:
            value = json.loads(self.validation_path.read_text(encoding="utf-8"))
            validated_at = datetime.fromisoformat(str(value.get("validated_at", "")).replace("Z", "+00:00"))
            if validated_at.tzinfo is None:
                validated_at = validated_at.replace(tzinfo=timezone.utc)
            fresh = validated_at >= datetime.now(timezone.utc) - timedelta(days=self.VALIDATION_MAX_AGE_DAYS)
            passed = (
                value.get("type") == "JARVIS_BUSINESS_RELEASE_VALIDATION"
                and value.get("version") == self.VERSION
                and value.get("status") == "PASSED"
                and fresh
            )
            return {**value, "status": "PASSED" if passed else "STALE_OR_INVALID"}
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return {"status": "INVALID", "version": self.VERSION, "validated_at": None}

    def _verify_integrity(self) -> dict[str, Any]:
        if not self.integrity_path.is_file():
            return {"status": "MISSING", "files_checked": 0, "changed": [], "missing": []}
        changed: list[str] = []
        missing: list[str] = []
        checked = 0
        try:
            payload = json.loads(self.integrity_path.read_text(encoding="utf-8"))
            files = dict(payload.get("files", {}) or {})
            root = self.paths.root.resolve(strict=False)
            for relative, expected in files.items():
                candidate = (root / str(relative)).resolve(strict=False)
                try:
                    candidate.relative_to(root)
                except ValueError:
                    changed.append(str(relative))
                    continue
                if not candidate.is_file():
                    missing.append(str(relative))
                    continue
                checked += 1
                if hashlib.sha256(candidate.read_bytes()).hexdigest() != str(expected):
                    changed.append(str(relative))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return {"status": "INVALID", "files_checked": 0, "changed": [], "missing": []}
        return {
            "status": "VERIFIED" if not changed and not missing else "CHANGED",
            "files_checked": checked,
            "changed": changed[:50],
            "missing": missing[:50],
        }

    @staticmethod
    def _checkpoint_after_validation(
        checkpoint: dict[str, Any],
        validation: dict[str, Any],
    ) -> bool:
        if checkpoint.get("verification") != "VERIFIED":
            return False
        try:
            checkpoint_at = datetime.fromisoformat(
                str(checkpoint.get("created_at", "")).replace("Z", "+00:00")
            )
            validated_at = datetime.fromisoformat(
                str(validation.get("validated_at", "")).replace("Z", "+00:00")
            )
            if checkpoint_at.tzinfo is None:
                checkpoint_at = checkpoint_at.replace(tzinfo=timezone.utc)
            if validated_at.tzinfo is None:
                validated_at = validated_at.replace(tzinfo=timezone.utc)
            return checkpoint_at >= validated_at
        except ValueError:
            return False

    @staticmethod
    def _safety_locked(config: dict[str, Any]) -> bool:
        safety = dict(config.get("safety", {}) or {})
        return (
            safety.get("auto_approve") is False
            and safety.get("require_confirmation") is True
            and int(safety.get("max_active_executions", 0)) == 1
            and safety.get("allow_remote_code_execution") is False
        )

    def _release_notes(self) -> str:
        return (
            "JARVIS OS RC1\n"
            "Version: 1.0.0-rc.1\n\n"
            "Zakres: B80-B88 Business Edition.\n"
            "Instalacja: uruchom pakiet B87 znajdujący się w tym archiwum.\n"
            "Bezpieczeństwo: auto-approve OFF, potwierdzenia wymagane, maks. 1 wykonanie, kod zdalny OFF.\n"
            "RC1 jest kandydatem do testów wdrożeniowych, nie finalnym wydaniem sprzedażowym.\n"
        )

    def _default_payload(self) -> dict[str, Any]:
        return {"schema_version": 1, "last_release": None, "history": []}

    def _normalize(self, value: Any) -> dict[str, Any]:
        payload = dict(value or {}) if isinstance(value, dict) else {}
        last_release = payload.get("last_release") if isinstance(payload.get("last_release"), dict) else None
        history = [item for item in payload.get("history", []) if isinstance(item, dict)]
        return {"schema_version": 1, "last_release": last_release, "history": history[-50:]}

    def _append_history(self, payload: dict[str, Any], action: str, decision: str) -> None:
        payload["history"].append({
            "timestamp": self._now(),
            "action": action,
            "decision": decision,
            "version": self.VERSION,
        })
        payload["history"] = payload["history"][-50:]

    def _error(self, status: str, message: str, errors: list[str] | None = None) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "operation": "business_release_candidate",
            "stage": "B88",
            "runtime": {
                "phase": "ATTENTION_REQUIRED",
                "running": False,
                "paused": False,
                "cycles_completed": 0,
                "last_decision": "REJECT",
            },
            "decision": "REJECT",
            "reason": message,
            "report_path": str(self.path),
            "errors": list(errors or [message]),
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
