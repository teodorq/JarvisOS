from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Any, Iterable
import uuid
import zipfile

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class BusinessDisasterRecovery:
    """B85 verified checkpoints and offline restore preparation."""

    MAX_RECORDS = 30
    MAX_RETAINED = 10
    MAX_FILES = 6000
    DEFAULT_TARGETS = (
        "app", "tests", "config", "assets", "main.py", "requirements.txt",
        "start_jarvis.bat", "start_jarvis.vbs", "install.bat", "JARVIS_OS.ico", "JARVIS_OS.png",
    )
    EXCLUDED_PARTS = {
        "__pycache__", ".pytest_cache", ".git", ".venv", "venv",
        "AI_PLIKI", "archive", "logs", "screenshots",
    }

    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "disaster_recovery.json"
        self.checkpoint_dir = self.paths.archive / "business_checkpoints"
        self.restore_dir = self.paths.ai_files / "disaster_recovery"
        self._store = JsonStore(self.path, self._default_payload)

    def status(self) -> dict[str, Any]:
        payload = self._normalize(self._store.load())
        self._store.save(payload)
        records = list(payload["checkpoints"])
        latest = records[-1] if records else None
        return {
            "success": True,
            "status": "BUSINESS_DISASTER_RECOVERY_STATUS",
            "operation": "business_disaster_recovery",
            "stage": "B85",
            "runtime": {
                "phase": "READY",
                "running": False,
                "paused": False,
                "cycles_completed": len(records),
                "last_decision": "READY",
            },
            "checkpoint_count": len(records),
            "latest_checkpoint": latest,
            "checkpoints": records[-10:][::-1],
            "checkpoint_directory": str(self.checkpoint_dir),
            "restore_directory": str(self.restore_dir),
            "decision": "READY",
            "reason": "Checkpointy są lokalne, wersjonowane i weryfikowane SHA-256.",
            "report_path": str(self.path),
            "errors": [],
        }

    def create_checkpoint(self, targets: Iterable[str] | None = None) -> dict[str, Any]:
        selected = tuple(targets or self.DEFAULT_TARGETS)
        files = list(self._iter_files(selected))
        if not files:
            return self._error("NO_CHECKPOINT_FILES", "Brak plików do checkpointu.")
        if len(files) > self.MAX_FILES:
            return self._error("CHECKPOINT_TOO_LARGE", "Checkpoint przekracza limit plików.")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_id = f"checkpoint-{uuid.uuid4().hex[:12]}"
        target = self.checkpoint_dir / f"JARVIS_BUSINESS_CHECKPOINT_{stamp}.zip"
        temporary = target.with_suffix(".zip.tmp")
        manifest_files: dict[str, str] = {}
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path, relative in files:
                data = file_path.read_bytes()
                manifest_files[relative] = hashlib.sha256(data).hexdigest()
                archive.writestr(relative, data)
            manifest = {
                "schema_version": 1,
                "type": "JARVIS_BUSINESS_CHECKPOINT",
                "checkpoint_id": checkpoint_id,
                "created_at": self._now(),
                "file_count": len(manifest_files),
                "files": manifest_files,
            }
            archive.writestr(
                "JARVIS_CHECKPOINT_MANIFEST.json",
                json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
            )
        temporary.replace(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        record = {
            "checkpoint_id": checkpoint_id,
            "created_at": manifest["created_at"],
            "path": str(target),
            "sha256": digest,
            "file_count": len(manifest_files),
            "size_bytes": target.stat().st_size,
            "verification": "VERIFIED",
        }
        payload = self._normalize(self._store.load())
        payload["checkpoints"].append(record)
        payload["checkpoints"] = payload["checkpoints"][-self.MAX_RECORDS :]
        self._store.save(payload)
        self._prune(payload)
        response = self.status()
        response.update({
            "status": "BUSINESS_CHECKPOINT_CREATED",
            "checkpoint": record,
            "decision": "CREATED",
            "reason": "Utworzono i zweryfikowano checkpoint projektu.",
        })
        return response

    def verify_latest(self) -> dict[str, Any]:
        record = self._latest_record()
        if record is None:
            return self._error("NO_CHECKPOINT", "Brak checkpointu do weryfikacji.")
        result = self._verify(Path(str(record.get("path", ""))), record)
        payload = self._normalize(self._store.load())
        for item in payload["checkpoints"]:
            if item.get("checkpoint_id") == record.get("checkpoint_id"):
                item["verification"] = result["verification"]
                item["verified_at"] = self._now()
        self._store.save(payload)
        response = self.status()
        response.update({
            "success": result["verification"] == "VERIFIED",
            "status": "BUSINESS_CHECKPOINT_VERIFIED",
            "verification": result,
            "decision": result["verification"],
            "reason": result["reason"],
            "errors": result["errors"],
        })
        return response

    def export_restore_package(self) -> dict[str, Any]:
        verified = self.verify_latest()
        if not verified.get("success"):
            return verified
        latest = verified.get("latest_checkpoint") or self._latest_record()
        checkpoint = Path(str(dict(latest or {}).get("path", "")))
        if not checkpoint.is_file():
            return self._error("CHECKPOINT_MISSING", "Plik checkpointu nie istnieje.")
        self.restore_dir.mkdir(parents=True, exist_ok=True)
        ps1 = self.restore_dir / "RESTORE_LATEST_JARVIS_CHECKPOINT.ps1"
        cmd = self.restore_dir / "RESTORE_LATEST_JARVIS_CHECKPOINT.cmd"
        ps1.write_text(self._restore_ps1(), encoding="utf-8-sig", newline="\r\n")
        cmd.write_text(
            self._restore_cmd(checkpoint), encoding="utf-8", newline="\r\n"
        )
        response = self.status()
        response.update({
            "status": "BUSINESS_RESTORE_PACKAGE_EXPORTED",
            "restore_cmd": str(cmd),
            "restore_script": str(ps1),
            "checkpoint_path": str(checkpoint),
            "decision": "PREVIEW_READY",
            "reason": "Przygotowano offline restore z backupem i rollbackiem.",
        })
        return response

    def _iter_files(self, targets: Iterable[str]) -> Iterable[tuple[Path, str]]:
        root = self.paths.root.resolve(strict=False)
        seen: set[str] = set()
        for value in targets:
            candidate = (root / str(value)).resolve(strict=False)
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            paths = candidate.rglob("*") if candidate.is_dir() else (candidate,)
            for path in paths:
                if not path.is_file() or any(part in self.EXCLUDED_PARTS for part in path.parts):
                    continue
                if path.suffix.lower() in {".pyc", ".tmp", ".log"}:
                    continue
                relative = path.relative_to(root).as_posix()
                if relative not in seen:
                    seen.add(relative)
                    yield path, relative

    def _verify(self, path: Path, record: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        if not path.is_file():
            errors.append("Brak pliku checkpointu.")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != str(record.get("sha256", "")):
            errors.append("Niezgodny SHA-256 archiwum.")
        if not errors:
            try:
                with zipfile.ZipFile(path) as archive:
                    damaged = archive.testzip()
                    if damaged:
                        errors.append(f"Uszkodzony element: {damaged}")
                    manifest = json.loads(
                        archive.read("JARVIS_CHECKPOINT_MANIFEST.json").decode("utf-8")
                    )
                    for name, expected in dict(manifest.get("files", {})).items():
                        safe = PurePosixPath(name)
                        if safe.is_absolute() or ".." in safe.parts:
                            errors.append(f"Niebezpieczna ścieżka: {name}")
                            break
                        digest = hashlib.sha256(archive.read(name)).hexdigest()
                        if digest != str(expected):
                            errors.append(f"Niezgodny plik: {name}")
                            break
            except (OSError, KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
                errors.append(str(error))
        return {
            "verification": "VERIFIED" if not errors else "FAILED",
            "reason": "Checkpoint jest poprawny." if not errors else "Checkpoint wymaga uwagi.",
            "errors": errors,
        }

    def _latest_record(self) -> dict[str, Any] | None:
        records = self._normalize(self._store.load())["checkpoints"]
        return dict(records[-1]) if records else None

    def _prune(self, payload: dict[str, Any]) -> None:
        retained = payload["checkpoints"][-self.MAX_RETAINED :]
        retained_paths = {str(item.get("path", "")) for item in retained}
        for path in self.checkpoint_dir.glob("JARVIS_BUSINESS_CHECKPOINT_*.zip"):
            if str(path) not in retained_paths:
                path.unlink(missing_ok=True)
        payload["checkpoints"] = retained
        self._store.save(payload)

    def _restore_cmd(self, checkpoint: Path) -> str:
        root = str(self.paths.root)
        return (
            f'@echo off\nsetlocal\ncd /d "{root}"\n'
            'echo Zamknij JARVIS OS przed kontynuacja.\npause\n'
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RESTORE_LATEST_JARVIS_CHECKPOINT.ps1" -Root "{root}" -Checkpoint "{checkpoint}"\n'
            'if errorlevel 1 (echo Restore nie powiodl sie. & pause & exit /b 1)\n'
            'echo Restore zakonczony poprawnie.\npause\n'
        )

    @staticmethod
    def _restore_ps1() -> str:
        return r'''param([Parameter(Mandatory=$true)][string]$Root,[Parameter(Mandatory=$true)][string]$Checkpoint)
$ErrorActionPreference='Stop'
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$temp=Join-Path $env:TEMP ('JARVIS_RESTORE_'+$stamp)
$backupWork=Join-Path $env:TEMP ('JARVIS_RESTORE_BACKUP_'+$stamp)
$backup=Join-Path $Root ('archive\disaster_restore_backups\RESTORE_'+$stamp+'.zip')
$newFiles=Join-Path $backupWork 'NEW_FILES.txt'
$pushed=$false
New-Item -ItemType Directory -Force -Path (Split-Path $backup -Parent),$temp,$backupWork|Out-Null
try {
  Expand-Archive -LiteralPath $Checkpoint -DestinationPath $temp -Force
  $manifest=Get-Content -LiteralPath (Join-Path $temp 'JARVIS_CHECKPOINT_MANIFEST.json') -Raw | ConvertFrom-Json
  foreach($property in $manifest.files.PSObject.Properties){
    $relative=$property.Name
    if([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\/])\.\.([\/]|$)'){throw ('Niebezpieczna sciezka: '+$relative)}
    $source=Join-Path $temp $relative
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
  if($LASTEXITCODE -ne 0){throw 'Nie udalo sie utworzyc backupu restore.'}
  Pop-Location
  foreach($property in $manifest.files.PSObject.Properties){
    $relative=$property.Name
    $source=Join-Path $temp $relative
    $target=Join-Path $Root $relative
    New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent)|Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
  }
  Push-Location $Root
  $pushed=$true
  python -m compileall -q app tests
  if($LASTEXITCODE -ne 0){throw 'Kontrola skladni po restore nie przeszla.'}
  python -m unittest discover -s tests -p 'test_*.py'
  if($LASTEXITCODE -ne 0){throw 'Testy po restore nie przeszly.'}
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
  Remove-Item $temp,$backupWork -Recurse -Force -ErrorAction SilentlyContinue
}
'''

    def _default_payload(self) -> dict[str, Any]:
        return {"schema_version": 1, "checkpoints": []}

    def _normalize(self, payload: Any) -> dict[str, Any]:
        value = dict(payload or {}) if isinstance(payload, dict) else {}
        records = [item for item in value.get("checkpoints", []) if isinstance(item, dict)]
        return {"schema_version": 1, "checkpoints": records[-self.MAX_RECORDS :]}

    def _error(self, status: str, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "operation": "business_disaster_recovery",
            "stage": "B85",
            "runtime": {"phase": "ATTENTION_REQUIRED", "running": False, "paused": False, "cycles_completed": 0, "last_decision": "REJECT"},
            "decision": "REJECT",
            "reason": message,
            "report_path": str(self.path),
            "errors": [message],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
