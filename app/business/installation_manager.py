from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable
import zipfile

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .access_control import BusinessAccessControl
from .business_config import BusinessConfigStore
from .installation_scripts import (
    START_SCRIPT,
    install_cmd,
    install_ps1,
    shortcut_ps1,
    uninstall_cmd,
    uninstall_ps1,
)
from .organization_profiles import OrganizationProfileStore


class BusinessInstallationManager:
    """B87 portable setup, first-run state, shortcut and safe uninstall kit."""

    VERSION = "1.0.0-rc.1"
    MAX_FILES = 10000
    REQUIRED_FILES = (
        "main.py",
        "requirements.txt",
        "start_jarvis.bat",
        "app/gui/main_window.py",
        "app/business/business_edition_service.py",
        "JARVIS_OS.ico",
        "JARVIS_OS.png",
    )
    EXCLUDED_PARTS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "AI_PLIKI",
        "archive",
        "logs",
        "screenshots",
        "update_staging",
        "change_campaign_snapshots",
    }
    EXCLUDED_SUFFIXES = {".pyc", ".tmp", ".log", ".bak"}
    EXCLUDED_ROOT_NAMES = {
        "CLEAN_AI_PLIKI.cmd",
        "RUN_JARVIS_AUDIT.cmd",
        "brain_test_base.py",
    }

    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "installation_manager.json"
        self.export_dir = self.paths.ai_files / "business_installation"
        self._store = JsonStore(self.path, self._default_payload)

    def status(self) -> dict[str, Any]:
        payload = self._normalize(self._store.load())
        self._store.save(payload)
        missing = [
            relative
            for relative in self.REQUIRED_FILES
            if not (self.paths.root / relative).is_file()
        ]
        packages = sorted(self.export_dir.glob("JARVIS_OS_BUSINESS_SETUP_*.zip"))
        latest = packages[-1] if packages else None
        ready = not missing
        return {
            "success": True,
            "status": "BUSINESS_INSTALLATION_MANAGER_STATUS",
            "operation": "business_installation",
            "stage": "B87",
            "runtime": {
                "phase": "READY" if ready else "ATTENTION_REQUIRED",
                "running": False,
                "paused": False,
                "cycles_completed": len(payload["history"]),
                "last_decision": "READY" if ready else "REVIEW",
            },
            "version": self.VERSION,
            "installation_ready": ready,
            "missing_required_files": missing,
            "first_run": payload["first_run"],
            "package_count": len(packages),
            "latest_setup_package": str(latest) if latest else None,
            "export_directory": str(self.export_dir),
            "decision": "READY" if ready else "REVIEW",
            "reason": (
                "Instalator, pierwsze uruchomienie i bezpieczna deinstalacja są dostępne."
                if ready
                else "Brakuje wymaganych plików instalacyjnych."
            ),
            "report_path": str(self.path),
            "errors": [f"Brak: {item}" for item in missing],
        }

    def initialize_first_run(self) -> dict[str, Any]:
        self.paths.ensure_runtime_directories()
        config = BusinessConfigStore(self.paths.root).ensure()
        profiles = OrganizationProfileStore(self.paths.root).ensure()
        access = BusinessAccessControl(self.paths.root).ensure()
        payload = self._normalize(self._store.load())
        payload["first_run"] = {
            "completed": True,
            "completed_at": self._now(),
            "version": self.VERSION,
            "organization": str(config.get("organization", "")),
            "active_profile_id": str(profiles.get("active_profile_id", "")),
            "active_role": str(access.get("active_role", "OWNER")),
        }
        self._append_history(payload, "FIRST_RUN_INITIALIZED", "COMPLETED")
        self._store.save(payload)
        response = self.status()
        response.update({
            "status": "BUSINESS_FIRST_RUN_INITIALIZED",
            "decision": "COMPLETED",
            "reason": "Przygotowano lokalne katalogi, profil i bezpieczne ustawienia.",
        })
        return response

    def export_setup_package(self) -> dict[str, Any]:
        current = self.status()
        if not current.get("installation_ready"):
            return self._error(
                "INSTALLATION_NOT_READY",
                "Nie można zbudować instalatora bez wymaganych plików.",
            )
        files = list(self._iter_release_files())
        if not files or len(files) > self.MAX_FILES:
            return self._error(
                "INSTALLATION_PAYLOAD_INVALID",
                "Pakiet instalacyjny jest pusty albo przekracza limit plików.",
            )
        self.export_dir.mkdir(parents=True, exist_ok=True)
        target = self.export_dir / "JARVIS_OS_BUSINESS_SETUP_1_0_0_RC1.zip"
        temporary_target = target.with_suffix(".zip.tmp")
        temporary_target.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(prefix="JARVIS_B87_SETUP_") as value:
            staging = Path(value)
            payload_dir = staging / "PAYLOAD"
            manifest_files: dict[str, str] = {}
            for source, relative in files:
                destination = payload_dir.joinpath(*relative.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                data = START_SCRIPT.encode("ascii") if relative == "start_jarvis.bat" else source.read_bytes()
                destination.write_bytes(data)
                manifest_files[relative] = hashlib.sha256(data).hexdigest()
            manifest = {
                "schema_version": 1,
                "type": "JARVIS_BUSINESS_SETUP",
                "version": self.VERSION,
                "created_at": self._now(),
                "file_count": len(manifest_files),
                "files": manifest_files,
                "safety": {
                    "overwrite_existing_installation": False,
                    "auto_approve": False,
                    "remote_code_execution": False,
                },
            }
            (staging / "JARVIS_BUSINESS_SETUP_MANIFEST.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._write_support_files(staging)
            with zipfile.ZipFile(
                temporary_target,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                for item in sorted(staging.rglob("*")):
                    if item.is_file():
                        archive.write(item, item.relative_to(staging).as_posix())
        temporary_target.replace(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        payload = self._normalize(self._store.load())
        payload["last_package"] = {
            "path": str(target),
            "sha256": digest,
            "created_at": self._now(),
            "file_count": len(files),
            "version": self.VERSION,
        }
        self._append_history(payload, "SETUP_PACKAGE_EXPORTED", "EXPORTED")
        self._store.save(payload)
        response = self.status()
        response.update({
            "status": "BUSINESS_SETUP_PACKAGE_EXPORTED",
            "setup_package": payload["last_package"],
            "decision": "EXPORTED",
            "reason": "Utworzono przenośny pakiet instalacyjny z manifestem SHA-256.",
        })
        return response

    def export_uninstaller(self) -> dict[str, Any]:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        directory = self.export_dir / "safe_uninstaller"
        directory.mkdir(parents=True, exist_ok=True)
        cmd = directory / "UNINSTALL_JARVIS_OS_BUSINESS.cmd"
        ps1 = directory / "UNINSTALL_JARVIS_OS_BUSINESS.ps1"
        cmd.write_text(uninstall_cmd(), encoding="utf-8", newline="\r\n")
        ps1.write_text(uninstall_ps1(), encoding="utf-8-sig", newline="\r\n")
        payload = self._normalize(self._store.load())
        self._append_history(payload, "UNINSTALLER_EXPORTED", "PREVIEW_READY")
        self._store.save(payload)
        response = self.status()
        response.update({
            "status": "BUSINESS_UNINSTALLER_EXPORTED",
            "uninstaller_cmd": str(cmd),
            "uninstaller_script": str(ps1),
            "decision": "PREVIEW_READY",
            "reason": "Deinstalator wymaga wpisania USUN i najpierw tworzy backup danych.",
        })
        return response

    def _iter_release_files(self) -> Iterable[tuple[Path, str]]:
        root = self.paths.root.resolve(strict=False)
        for candidate in sorted(root.rglob("*")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = candidate.relative_to(root)
            if any(part in self.EXCLUDED_PARTS for part in relative_path.parts):
                continue
            if candidate.suffix.lower() in self.EXCLUDED_SUFFIXES:
                continue
            relative = relative_path.as_posix()
            if relative.startswith("data/"):
                continue
            if len(relative_path.parts) == 1 and (
                candidate.name in self.EXCLUDED_ROOT_NAMES
                or candidate.name.startswith("APPLY_")
                or candidate.name.startswith("JARVIS_CHECKPOINT_")
            ):
                continue
            yield candidate, relative

    def _write_support_files(self, staging: Path) -> None:
        files = {
            "INSTALL_JARVIS_OS_BUSINESS.cmd": (install_cmd(), "utf-8"),
            "INSTALL_JARVIS_OS_BUSINESS.ps1": (install_ps1(), "utf-8-sig"),
            "CREATE_DESKTOP_SHORTCUT.ps1": (shortcut_ps1(), "utf-8-sig"),
            "UNINSTALL_JARVIS_OS_BUSINESS.cmd": (uninstall_cmd(), "utf-8"),
            "UNINSTALL_JARVIS_OS_BUSINESS.ps1": (uninstall_ps1(), "utf-8-sig"),
            "README_INSTALLATION.txt": (
                "JARVIS OS RC1\n\n"
                "Uruchom INSTALL_JARVIS_OS_BUSINESS.cmd.\n"
                "Domyślny katalog: folder JarvisAI na dysku systemowym.\n"
                "Instalator nie nadpisuje istniejącego projektu.\n"
                "Kod jest lokalny; pip może wymagać skonfigurowanego źródła bibliotek.\n",
                "utf-8",
            ),
        }
        for name, (content, encoding) in files.items():
            (staging / name).write_text(content, encoding=encoding, newline="\r\n")

    def _default_payload(self) -> dict[str, Any]:
        return {"schema_version": 1, "first_run": {}, "last_package": None, "history": []}

    def _normalize(self, value: Any) -> dict[str, Any]:
        payload = dict(value or {}) if isinstance(value, dict) else {}
        first_run = payload.get("first_run") if isinstance(payload.get("first_run"), dict) else {}
        last_package = payload.get("last_package") if isinstance(payload.get("last_package"), dict) else None
        history = [item for item in payload.get("history", []) if isinstance(item, dict)]
        return {
            "schema_version": 1,
            "first_run": first_run,
            "last_package": last_package,
            "history": history[-50:],
        }

    def _append_history(self, payload: dict[str, Any], action: str, decision: str) -> None:
        payload["history"].append({
            "timestamp": self._now(),
            "action": action,
            "decision": decision,
            "version": self.VERSION,
        })
        payload["history"] = payload["history"][-50:]

    def _error(self, status: str, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "operation": "business_installation",
            "stage": "B87",
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
            "errors": [message],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
