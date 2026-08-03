from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import time
import tempfile
from typing import Any

from app.core.project_paths import default_project_root


class BackupBundleManager:

    MANIFEST_VERSION = 2

    def __init__(
        self,
        project_root: str | Path | None = None,
        backup_root: str | Path | None = None,
    ) -> None:
        self.project_root = Path(
            project_root or default_project_root()
        ).expanduser().resolve(
            strict=False
        )

        selected_root = (
            Path(backup_root).expanduser()
            if backup_root is not None
            else self.project_root
            / "data/backups/autodev"
        )

        if not selected_root.is_absolute():
            selected_root = (
                self.project_root
                / selected_root
            )

        self.backup_root = selected_root.resolve(
            strict=False
        )
        self._require_within(
            self.backup_root,
            self.project_root,
            "Katalog backupów znajduje się poza projektem.",
        )
        self.backup_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.last_bundle_path: str | None = None

    def create_bundle(
        self,
        files: list[str],
        goal: str = "",
    ) -> dict[str, Any]:
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )
        bundle_path = self.backup_root / timestamp
        files_path = bundle_path / "files"
        files_path.mkdir(
            parents=True,
            exist_ok=False,
        )

        manifest: dict[str, Any] = {
            "version": self.MANIFEST_VERSION,
            "created_at": datetime.now().isoformat(),
            "goal": str(goal),
            "project_root": str(self.project_root),
            "bundle_path": str(bundle_path),
            "files": [],
            "errors": [],
        }

        seen: set[str] = set()

        for raw_path in files:
            if not str(raw_path).strip():
                manifest["errors"].append(
                    "Pominięto pustą ścieżkę pliku."
                )
                continue

            try:
                source = self._resolve_project_file(
                    raw_path,
                    must_exist=True,
                )
                normalized = os.path.normcase(
                    str(source)
                )

                if normalized in seen:
                    continue

                seen.add(normalized)
                relative = source.relative_to(
                    self.project_root
                )
                backup_path = (
                    files_path / relative
                )
                backup_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    source,
                    backup_path,
                )

                source_hash = self._hash_file(
                    source
                )
                backup_hash = self._hash_file(
                    backup_path
                )

                if source_hash != backup_hash:
                    backup_path.unlink(
                        missing_ok=True
                    )
                    raise OSError(
                        "Suma kontrolna backupu "
                        "nie zgadza się ze źródłem."
                    )

                manifest["files"].append(
                    {
                        "source": str(source),
                        "relative_path": (
                            relative.as_posix()
                        ),
                        "backup": str(backup_path),
                        "backup_relative": str(
                            backup_path.relative_to(
                                bundle_path
                            )
                        ).replace("\\", "/"),
                        "sha256": backup_hash,
                        "size_bytes": (
                            backup_path.stat().st_size
                        ),
                    }
                )

            except Exception as error:
                manifest["errors"].append(
                    "Nie udało się zapisać "
                    f"{raw_path}: "
                    f"{type(error).__name__}: {error}"
                )

        self._write_manifest(
            bundle_path / "manifest.json",
            manifest,
        )
        self.last_bundle_path = str(
            bundle_path
        )

        return manifest

    def restore_bundle(
        self,
        bundle_path: str | None = None,
    ) -> dict[str, Any]:
        selected_path = (
            bundle_path
            or self.last_bundle_path
        )
        result: dict[str, Any] = {
            "success": False,
            "bundle_path": selected_path or "",
            "restored": [],
            "verified": [],
            "errors": [],
        }

        if not selected_path:
            result["errors"].append(
                "Nie wskazano backupu "
                "do przywrócenia."
            )
            return result

        try:
            bundle = self._resolve_bundle(
                selected_path
            )
            manifest = self._load_manifest(
                bundle
            )
            restore_plan = self._build_restore_plan(
                bundle,
                manifest,
            )
        except Exception as error:
            result["errors"].append(
                "Backup nie przeszedł walidacji: "
                f"{type(error).__name__}: {error}"
            )
            return result

        if not restore_plan:
            result["errors"].append(
                "Manifest nie zawiera plików "
                "do przywrócenia."
            )
            return result

        result["verified"] = [
            str(item["target"])
            for item in restore_plan
        ]

        staged: list[dict[str, Any]] = []
        applied: list[dict[str, Any]] = []

        try:
            for item in restore_plan:
                target: Path = item["target"]
                backup: Path = item["backup"]

                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                self._validate_target_parent(
                    target
                )

                staged_path = self._stage_copy(
                    backup,
                    target.parent,
                    prefix=(
                        f".{target.name}."
                        "restore."
                    ),
                )
                emergency_path = None

                if target.exists():
                    if target.is_symlink():
                        raise OSError(
                            "Odmowa przywrócenia "
                            f"przez dowiązanie: {target}"
                        )
                    emergency_path = self._stage_copy(
                        target,
                        target.parent,
                        prefix=(
                            f".{target.name}."
                            "before-restore."
                        ),
                    )

                staged.append(
                    {
                        **item,
                        "staged": staged_path,
                        "emergency": emergency_path,
                    }
                )

            for item in staged:
                target = item["target"]
                self._replace_with_retry(
                    item["staged"],
                    target,
                )
                item["staged"] = None
                applied.append(item)
                result["restored"].append(
                    str(target)
                )

        except Exception as error:
            result["errors"].append(
                "Przywracanie zostało przerwane: "
                f"{type(error).__name__}: {error}"
            )
            self._undo_partial_restore(
                applied,
                result["errors"],
            )
            result["restored"] = []
            return result

        finally:
            self._cleanup_staged(
                staged
            )

        result["success"] = (
            len(result["restored"])
            == len(restore_plan)
            and not result["errors"]
        )
        return result

    def list_bundles(
        self,
    ) -> list[dict[str, Any]]:
        bundles: list[dict[str, Any]] = []

        for path in self.backup_root.iterdir():
            if (
                not path.is_dir()
                or path.is_symlink()
            ):
                continue

            try:
                manifest = self._load_manifest(
                    path
                )
                bundles.append(
                    {
                        "path": str(path),
                        "created_at": manifest.get(
                            "created_at",
                            "",
                        ),
                        "goal": manifest.get(
                            "goal",
                            "",
                        ),
                        "files_count": len(
                            manifest.get(
                                "files",
                                [],
                            )
                        ),
                        "errors_count": len(
                            manifest.get(
                                "errors",
                                [],
                            )
                        ),
                        "version": manifest.get(
                            "version",
                            1,
                        ),
                    }
                )
            except Exception:
                continue

        bundles.sort(
            key=lambda item: item.get(
                "created_at",
                "",
            ),
            reverse=True,
        )
        return bundles

    def summary(
        self,
    ) -> str:
        bundles = self.list_bundles()

        if not bundles:
            return "Brak backupów AutoDev."

        lines = ["AUTODEV BACKUPS"]

        for item in bundles[:20]:
            lines.append(
                f"- {item['created_at']} | "
                f"pliki: {item['files_count']} | "
                f"błędy: {item['errors_count']} | "
                f"{item['goal']}"
            )
            lines.append(
                f"  {item['path']}"
            )

        return "\n".join(lines)

    def _resolve_project_file(
        self,
        raw_path: str | Path,
        *,
        must_exist: bool,
    ) -> Path:
        candidate = Path(
            raw_path
        ).expanduser()

        if not candidate.is_absolute():
            candidate = (
                self.project_root
                / candidate
            )

        if candidate.is_symlink():
            raise OSError(
                f"Dowiązanie nie jest dozwolone: {candidate}"
            )

        resolved = candidate.resolve(
            strict=must_exist
        )
        self._require_within(
            resolved,
            self.project_root,
            "Plik znajduje się poza projektem.",
        )

        if must_exist and not resolved.is_file():
            raise FileNotFoundError(
                f"To nie jest plik: {resolved}"
            )

        return resolved

    def _resolve_bundle(
        self,
        selected_path: str | Path,
    ) -> Path:
        candidate = Path(
            selected_path
        ).expanduser()

        if not candidate.is_absolute():
            candidate = (
                self.backup_root
                / candidate
            )

        if candidate.is_symlink():
            raise OSError(
                "Dowiązanie do katalogu backupu "
                "nie jest dozwolone."
            )

        bundle = candidate.resolve(
            strict=True
        )
        self._require_within(
            bundle,
            self.backup_root,
            "Backup znajduje się poza "
            "katalogiem backupów.",
        )

        if not bundle.is_dir():
            raise NotADirectoryError(
                f"To nie jest katalog backupu: {bundle}"
            )

        return bundle

    def _load_manifest(
        self,
        bundle: Path,
    ) -> dict[str, Any]:
        manifest_path = (
            bundle / "manifest.json"
        )

        if (
            manifest_path.is_symlink()
            or not manifest_path.is_file()
        ):
            raise FileNotFoundError(
                f"Brak bezpiecznego manifestu: "
                f"{manifest_path}"
            )

        with manifest_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            manifest = json.load(file)

        if not isinstance(
            manifest,
            dict,
        ):
            raise ValueError(
                "Manifest nie jest obiektem JSON."
            )

        files = manifest.get(
            "files",
            [],
        )

        if not isinstance(files, list):
            raise ValueError(
                "Pole files w manifeście "
                "nie jest listą."
            )

        return manifest

    def _build_restore_plan(
        self,
        bundle: Path,
        manifest: dict[str, Any],
    ) -> list[dict[str, Any]]:
        plan: list[dict[str, Any]] = []
        seen_targets: set[str] = set()
        files_root = (
            bundle / "files"
        ).resolve(
            strict=True
        )

        self._require_within(
            files_root,
            bundle,
            "Katalog plików backupu "
            "jest niepoprawny.",
        )

        for index, item in enumerate(
            manifest.get("files", []),
            start=1,
        ):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Niepoprawny wpis manifestu: {index}"
                )

            target = self._manifest_target(
                item
            )
            backup = self._manifest_backup(
                bundle,
                files_root,
                item,
            )
            expected_hash = str(
                item.get(
                    "sha256",
                    "",
                )
            ).strip()

            if expected_hash:
                actual_hash = self._hash_file(
                    backup
                )

                if actual_hash != expected_hash:
                    raise ValueError(
                        "Naruszona suma kontrolna "
                        f"backupu: {backup}"
                    )

            normalized = os.path.normcase(
                str(target)
            )

            if normalized in seen_targets:
                raise ValueError(
                    "Manifest zawiera duplikat celu: "
                    f"{target}"
                )

            seen_targets.add(normalized)
            plan.append(
                {
                    "target": target,
                    "backup": backup,
                }
            )

        return plan

    def _manifest_target(
        self,
        item: dict[str, Any],
    ) -> Path:
        relative_value = str(
            item.get(
                "relative_path",
                "",
            )
        ).strip()

        if relative_value:
            relative = Path(
                relative_value
            )

            if (
                relative.is_absolute()
                or ".." in relative.parts
            ):
                raise ValueError(
                    "Niebezpieczna ścieżka względna "
                    f"w manifeście: {relative_value}"
                )

            candidate = (
                self.project_root
                / relative
            )
        else:
            source_value = str(
                item.get(
                    "source",
                    "",
                )
            ).strip()

            if not source_value:
                raise ValueError(
                    "Wpis manifestu nie ma celu."
                )

            candidate = Path(
                source_value
            ).expanduser()

            if not candidate.is_absolute():
                candidate = (
                    self.project_root
                    / candidate
                )

        if candidate.is_symlink():
            raise OSError(
                "Cel rollbacku jest dowiązaniem: "
                f"{candidate}"
            )

        target = candidate.resolve(
            strict=False
        )
        self._require_within(
            target,
            self.project_root,
            "Cel rollbacku znajduje się "
            "poza projektem.",
        )
        return target

    def _manifest_backup(
        self,
        bundle: Path,
        files_root: Path,
        item: dict[str, Any],
    ) -> Path:
        relative_value = str(
            item.get(
                "backup_relative",
                "",
            )
        ).strip()

        if relative_value:
            relative = Path(
                relative_value
            )

            if (
                relative.is_absolute()
                or ".." in relative.parts
            ):
                raise ValueError(
                    "Niebezpieczna ścieżka backupu "
                    f"w manifeście: {relative_value}"
                )

            candidate = bundle / relative
        else:
            backup_value = str(
                item.get(
                    "backup",
                    "",
                )
            ).strip()

            if not backup_value:
                raise ValueError(
                    "Wpis manifestu nie ma pliku backupu."
                )

            candidate = Path(
                backup_value
            ).expanduser()

            if not candidate.is_absolute():
                candidate = bundle / candidate

        if candidate.is_symlink():
            raise OSError(
                "Plik backupu jest dowiązaniem: "
                f"{candidate}"
            )

        backup = candidate.resolve(
            strict=True
        )
        self._require_within(
            backup,
            files_root,
            "Plik backupu znajduje się poza "
            "katalogiem files.",
        )

        if not backup.is_file():
            raise FileNotFoundError(
                f"Brak pliku backupu: {backup}"
            )

        return backup

    def _validate_target_parent(
        self,
        target: Path,
    ) -> None:
        parent = target.parent.resolve(
            strict=True
        )
        self._require_within(
            parent,
            self.project_root,
            "Katalog docelowy znajduje się "
            "poza projektem.",
        )

    def _stage_copy(
        self,
        source: Path,
        directory: Path,
        *,
        prefix: str,
    ) -> Path:
        descriptor, raw_path = tempfile.mkstemp(
            dir=directory,
            prefix=prefix,
            suffix=".tmp",
        )
        os.close(descriptor)
        staged = Path(raw_path)

        try:
            shutil.copy2(
                source,
                staged,
            )
            with staged.open("rb") as file:
                os.fsync(
                    file.fileno()
                )
            return staged
        except Exception:
            staged.unlink(
                missing_ok=True
            )
            raise

    def _undo_partial_restore(
        self,
        applied: list[dict[str, Any]],
        errors: list[str],
    ) -> None:
        for item in reversed(applied):
            target: Path = item["target"]
            emergency: Path | None = item.get(
                "emergency"
            )

            try:
                if (
                    emergency is not None
                    and emergency.exists()
                ):
                    self._replace_with_retry(
                        emergency,
                        target,
                    )
                    item["emergency"] = None
                else:
                    target.unlink(
                        missing_ok=True
                    )
            except Exception as error:
                errors.append(
                    "Nie udało się cofnąć "
                    f"częściowego rollbacku {target}: "
                    f"{type(error).__name__}: {error}"
                )

    @staticmethod
    def _replace_with_retry(
        source: Path,
        destination: Path,
        *,
        attempts: int = 6,
    ) -> None:
        last_error: OSError | None = None

        for attempt in range(
            max(
                1,
                attempts,
            )
        ):
            try:
                if destination.exists():
                    try:
                        current_mode = stat.S_IMODE(
                            destination.stat().st_mode
                        )
                        os.chmod(
                            destination,
                            current_mode
                            | stat.S_IWRITE,
                        )
                    except OSError:
                        raise RuntimeError("AutoDev: przechwycony wyjątek")

                os.replace(
                    source,
                    destination,
                )
                return

            except OSError as error:
                last_error = error

                if attempt + 1 >= attempts:
                    break

                time.sleep(
                    0.02
                    * (attempt + 1)
                )

        if last_error is not None:
            raise last_error

    def _cleanup_staged(
        self,
        staged: list[dict[str, Any]],
    ) -> None:
        for item in staged:
            for key in (
                "staged",
                "emergency",
            ):
                path = item.get(key)

                if isinstance(path, Path):
                    path.unlink(
                        missing_ok=True
                    )

    def _write_manifest(
        self,
        manifest_path: Path,
        manifest: dict[str, Any],
    ) -> None:
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=manifest_path.parent,
                prefix=".manifest.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                json.dump(
                    manifest,
                    temporary_file,
                    ensure_ascii=False,
                    indent=4,
                )
                temporary_file.flush()
                os.fsync(
                    temporary_file.fileno()
                )
                temporary_path = Path(
                    temporary_file.name
                )

            os.replace(
                temporary_path,
                manifest_path,
            )
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(
                    missing_ok=True
                )

    @staticmethod
    def _hash_file(
        path: Path,
    ) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(
                lambda: file.read(
                    1024 * 1024
                ),
                b"",
            ):
                digest.update(chunk)

        return digest.hexdigest()

    @staticmethod
    def _require_within(
        candidate: Path,
        root: Path,
        message: str,
    ) -> None:
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ValueError(message) from error
