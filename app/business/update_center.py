from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Any
import uuid
import zipfile

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class BusinessUpdateCenter:
    """B86 local signed-by-hash update staging with offline installer export."""

    MANIFEST = "JARVIS_UPDATE_MANIFEST.json"
    PAYLOAD_PREFIX = "PAYLOAD/"
    MAX_HISTORY = 50

    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "update_center.json"
        self.inbox = self.paths.ai_files / "updates"
        self.staging = self.paths.data / "business" / "update_staging"
        self.export_dir = self.paths.ai_files / "updates" / "prepared"
        self._store = JsonStore(self.path, self._default_payload)

    def status(self) -> dict[str, Any]:
        payload = self._normalize(self._store.load())
        self._store.save(payload)
        candidates = self._candidate_statuses()
        valid = [item for item in candidates if item.get("valid")]
        staged = payload.get("staged")
        return {
            "success": True,
            "status": "BUSINESS_UPDATE_CENTER_STATUS",
            "operation": "business_update_center",
            "stage": "B86",
            "runtime": {
                "phase": "READY",
                "running": False,
                "paused": False,
                "cycles_completed": len(payload["history"]),
                "last_decision": "READY",
            },
            "package_count": len(candidates),
            "valid_package_count": len(valid),
            "packages": candidates,
            "staged_update": staged,
            "history": payload["history"][-10:][::-1],
            "inbox_directory": str(self.inbox),
            "staging_directory": str(self.staging),
            "decision": "READY",
            "reason": "Aktualizacje są lokalne, weryfikowane i instalowane offline.",
            "report_path": str(self.path),
            "errors": [],
        }

    def scan(self) -> dict[str, Any]:
        response = self.status()
        response["status"] = "BUSINESS_UPDATE_SCAN_COMPLETED"
        response["decision"] = "VALID_PACKAGES" if response["valid_package_count"] else "NO_VALID_PACKAGE"
        return response

    def stage_latest(self) -> dict[str, Any]:
        valid = [item for item in self._candidate_statuses() if item.get("valid")]
        if not valid:
            return self._error("NO_VALID_UPDATE_PACKAGE", "Brak poprawnego pakietu aktualizacji.")
        selected = max(valid, key=lambda item: Path(str(item["path"])).stat().st_mtime)
        package_path = Path(str(selected["path"]))
        manifest = dict(selected["manifest"])
        update_id = str(manifest.get("update_id") or f"update-{uuid.uuid4().hex[:12]}")
        destination = self.staging / update_id
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package_path) as archive:
            for name in archive.namelist():
                if not name.startswith(self.PAYLOAD_PREFIX) or name.endswith("/"):
                    continue
                relative = PurePosixPath(name[len(self.PAYLOAD_PREFIX) :])
                if relative.is_absolute() or ".." in relative.parts:
                    shutil.rmtree(destination, ignore_errors=True)
                    return self._error("UNSAFE_UPDATE_PATH", f"Niebezpieczna ścieżka: {name}")
                target = destination.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
        (destination / self.MANIFEST).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        staged = {
            "update_id": update_id,
            "version": str(manifest.get("version", "UNKNOWN")),
            "staged_at": self._now(),
            "source_path": str(package_path),
            "staging_path": str(destination),
            "file_count": len(dict(manifest.get("files", {}))),
            "status": "STAGED",
        }
        payload = self._normalize(self._store.load())
        payload["staged"] = staged
        payload["history"].append({**staged, "action": "STAGE"})
        payload["history"] = payload["history"][-self.MAX_HISTORY :]
        self._store.save(payload)
        response = self.status()
        response.update({
            "status": "BUSINESS_UPDATE_STAGED",
            "staged_update": staged,
            "decision": "STAGED",
            "reason": "Pakiet zweryfikowano i rozpakowano do izolowanego stagingu.",
        })
        return response

    def export_installer(self) -> dict[str, Any]:
        staged = self._normalize(self._store.load()).get("staged")
        if not isinstance(staged, dict):
            return self._error("NO_STAGED_UPDATE", "Najpierw przygotuj aktualizację w stagingu.")
        staging_path = Path(str(staged.get("staging_path", "")))
        manifest_path = staging_path / self.MANIFEST
        if not staging_path.is_dir() or not manifest_path.is_file():
            return self._error("STAGED_UPDATE_MISSING", "Brak plików staged update.")
        self.export_dir.mkdir(parents=True, exist_ok=True)
        cmd = self.export_dir / "APPLY_STAGED_JARVIS_UPDATE.cmd"
        ps1 = self.export_dir / "APPLY_STAGED_JARVIS_UPDATE.ps1"
        ps1.write_text(self._installer_ps1(), encoding="utf-8-sig", newline="\r\n")
        cmd.write_text(
            self._installer_cmd(staging_path), encoding="utf-8", newline="\r\n"
        )
        payload = self._normalize(self._store.load())
        payload["history"].append({
            **staged,
            "action": "INSTALLER_EXPORTED",
            "exported_at": self._now(),
            "installer": str(cmd),
        })
        payload["history"] = payload["history"][-self.MAX_HISTORY :]
        self._store.save(payload)
        response = self.status()
        response.update({
            "status": "BUSINESS_UPDATE_INSTALLER_EXPORTED",
            "installer_cmd": str(cmd),
            "installer_script": str(ps1),
            "decision": "PREVIEW_READY",
            "reason": "Przygotowano offline installer z testami i rollbackiem.",
        })
        return response

    def _candidate_statuses(self) -> list[dict[str, Any]]:
        self.inbox.mkdir(parents=True, exist_ok=True)
        results: list[dict[str, Any]] = []
        for package in sorted(self.inbox.glob("*.zip")):
            results.append(self._validate_package(package))
        return results[-30:]

    def _validate_package(self, package: Path) -> dict[str, Any]:
        errors: list[str] = []
        manifest: dict[str, Any] = {}
        try:
            with zipfile.ZipFile(package) as archive:
                damaged = archive.testzip()
                if damaged:
                    errors.append(f"Uszkodzony element: {damaged}")
                manifest = json.loads(archive.read(self.MANIFEST).decode("utf-8"))
                if manifest.get("type") != "JARVIS_BUSINESS_UPDATE":
                    errors.append("Nieprawidłowy typ manifestu.")
                files = manifest.get("files", {})
                if not isinstance(files, dict) or not files:
                    errors.append("Manifest nie zawiera plików.")
                else:
                    for relative, expected in files.items():
                        safe = PurePosixPath(str(relative))
                        if safe.is_absolute() or ".." in safe.parts:
                            errors.append(f"Niebezpieczna ścieżka: {relative}")
                            break
                        name = self.PAYLOAD_PREFIX + safe.as_posix()
                        digest = hashlib.sha256(archive.read(name)).hexdigest()
                        if digest != str(expected):
                            errors.append(f"Niezgodny SHA-256: {relative}")
                            break
        except (OSError, KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
            errors.append(str(error))
        return {
            "path": str(package),
            "name": package.name,
            "valid": not errors,
            "manifest": manifest,
            "errors": errors,
        }

    def _installer_cmd(self, staging_path: Path) -> str:
        root = str(self.paths.root)
        return (
            f'@echo off\nsetlocal\ncd /d "{root}"\n'
            'echo Zamknij JARVIS OS przed instalacja.\npause\n'
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0APPLY_STAGED_JARVIS_UPDATE.ps1" -Root "{root}" -Staging "{staging_path}"\n'
            'if errorlevel 1 (echo Aktualizacja wycofana. & pause & exit /b 1)\n'
            'echo Aktualizacja zakonczona poprawnie.\npause\n'
        )

    @staticmethod
    def _installer_ps1() -> str:
        return r'''param([Parameter(Mandatory=$true)][string]$Root,[Parameter(Mandatory=$true)][string]$Staging)
$ErrorActionPreference='Stop'
$manifest=Get-Content -LiteralPath (Join-Path $Staging 'JARVIS_UPDATE_MANIFEST.json') -Raw | ConvertFrom-Json
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$backup=Join-Path $Root ('archive\update_backups\UPDATE_'+$stamp+'.zip')
$backupWork=Join-Path $env:TEMP ('JARVIS_UPDATE_BACKUP_'+$stamp)
$newFiles=Join-Path $backupWork 'NEW_FILES.txt'
$pushed=$false
New-Item -ItemType Directory -Force -Path (Split-Path $backup -Parent),$backupWork|Out-Null
try {
  foreach($property in $manifest.files.PSObject.Properties){
    $relative=$property.Name
    if([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\/])\.\.([\/]|$)'){throw ('Niebezpieczna sciezka: '+$relative)}
    $source=Join-Path $Staging $relative
    if(-not (Test-Path -LiteralPath $source -PathType Leaf)){throw ('Brak pliku staged update: '+$relative)}
    $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    if($actual -ne ([string]$property.Value).ToLowerInvariant()){throw ('Niezgodny SHA-256: '+$relative)}
    $current=Join-Path $Root $relative
    if(Test-Path -LiteralPath $current -PathType Leaf){
      $copy=Join-Path $backupWork $relative
      New-Item -ItemType Directory -Force -Path (Split-Path $copy -Parent)|Out-Null
      Copy-Item -LiteralPath $current -Destination $copy -Force
    } else {Add-Content -LiteralPath $newFiles -Value $relative -Encoding UTF8}
  }
  Push-Location $backupWork
  tar.exe -a -c -f $backup .
  if($LASTEXITCODE -ne 0){throw 'Nie udalo sie utworzyc backupu aktualizacji.'}
  Pop-Location
  foreach($property in $manifest.files.PSObject.Properties){
    $relative=$property.Name
    $source=Join-Path $Staging $relative
    $target=Join-Path $Root $relative
    New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent)|Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
  }
  Push-Location $Root
  $pushed=$true
  python -m compileall -q app tests
  if($LASTEXITCODE -ne 0){throw 'Kontrola skladni nie przeszla.'}
  python -m unittest discover -s tests -p 'test_*.py'
  if($LASTEXITCODE -ne 0){throw 'Testy aktualizacji nie przeszly.'}
  Pop-Location
  $pushed=$false
} catch {
  if($pushed){Pop-Location; $pushed=$false}
  if(Test-Path -LiteralPath $newFiles){
    Get-Content -LiteralPath $newFiles | Where-Object{$_ -and $_.Trim()} | ForEach-Object{
      $target=Join-Path $Root $_
      if(Test-Path -LiteralPath $target -PathType Leaf){Remove-Item -LiteralPath $target -Force}
    }
  }
  Get-ChildItem -LiteralPath $backupWork -Recurse -File | Where-Object{$_.Name -ne 'NEW_FILES.txt'} | ForEach-Object{
    $relative=$_.FullName.Substring($backupWork.Length).TrimStart('\','/')
    $target=Join-Path $Root $relative
    New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent)|Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $target -Force
  }
  throw
} finally {
  if($pushed){Pop-Location}
  Remove-Item $backupWork -Recurse -Force -ErrorAction SilentlyContinue
}
'''

    def _default_payload(self) -> dict[str, Any]:
        return {"schema_version": 1, "staged": None, "history": []}

    def _normalize(self, payload: Any) -> dict[str, Any]:
        value = dict(payload or {}) if isinstance(payload, dict) else {}
        staged = value.get("staged") if isinstance(value.get("staged"), dict) else None
        history = [item for item in value.get("history", []) if isinstance(item, dict)]
        return {"schema_version": 1, "staged": staged, "history": history[-self.MAX_HISTORY :]}

    def _error(self, status: str, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "operation": "business_update_center",
            "stage": "B86",
            "runtime": {"phase": "ATTENTION_REQUIRED", "running": False, "paused": False, "cycles_completed": 0, "last_decision": "REJECT"},
            "decision": "REJECT",
            "reason": message,
            "report_path": str(self.path),
            "errors": [message],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
