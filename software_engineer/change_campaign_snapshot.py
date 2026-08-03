from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import time
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class ChangeCampaignSnapshotManager:
    """Persistent verified snapshot for campaign-wide rollback."""

    def __init__(
        self,
        project_root: str | Path,
    ) -> None:
        self.paths = ProjectPaths.from_value(
            project_root
        )
        self.project_root = (
            self.paths.root
        )
        self.snapshots_root = (
            self.paths.autodev_data
            / "change_campaign_snapshots"
        )

    def create(
        self,
        campaign_id: str,
        targets: list[str],
    ) -> dict[str, Any]:
        snapshot_dir = self._snapshot_dir(
            campaign_id
        )
        manifest_path = (
            snapshot_dir
            / "manifest.json"
        )

        if manifest_path.is_file():
            return self.manifest(
                campaign_id
            )

        snapshot_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        files_dir = snapshot_dir / "files"
        files_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        entries: list[
            dict[str, Any]
        ] = []

        for relative in list(
            dict.fromkeys(
                str(item)
                for item in targets
            )
        ):
            target = self._target(
                relative
            )
            existed = target.exists()

            if existed and not target.is_file():
                raise ValueError(
                    "Target snapshotu nie jest "
                    f"plikiem: {relative}"
                )

            entry: dict[str, Any] = {
                "relative_path": relative,
                "existed": existed,
                "backup_file": "",
                "sha256": "",
                "mode": 0,
            }

            if existed:
                content = target.read_bytes()
                name = (
                    hashlib.sha256(
                        relative.encode(
                            "utf-8"
                        )
                    ).hexdigest()
                    + ".bin"
                )
                backup = files_dir / name
                backup.write_bytes(
                    content
                )
                entry.update(
                    {
                        "backup_file": (
                            f"files/{name}"
                        ),
                        "sha256": hashlib.sha256(
                            content
                        ).hexdigest(),
                        "mode": stat.S_IMODE(
                            target.stat().st_mode
                        ),
                    }
                )

            entries.append(entry)

        manifest = {
            "version": 1,
            "campaign_id": self._safe_id(
                campaign_id
            ),
            "project_root": str(
                self.project_root
            ),
            "entries": entries,
        }
        JsonStore(
            manifest_path,
            dict,
        ).save(manifest)

        return manifest

    def exists(
        self,
        campaign_id: str,
    ) -> bool:
        return (
            self._snapshot_dir(
                campaign_id
            )
            / "manifest.json"
        ).is_file()

    def manifest(
        self,
        campaign_id: str,
    ) -> dict[str, Any]:
        path = (
            self._snapshot_dir(
                campaign_id
            )
            / "manifest.json"
        )
        value = JsonStore(
            path,
            dict,
        ).load()

        if not isinstance(
            value,
            dict,
        ) or not isinstance(
            value.get(
                "entries"
            ),
            list,
        ):
            raise ValueError(
                "Snapshot kampanii jest "
                "nieprawidłowy."
            )

        return dict(value)

    def restore(
        self,
        campaign_id: str,
    ) -> dict[str, Any]:
        snapshot_dir = self._snapshot_dir(
            campaign_id
        )

        try:
            manifest = self.manifest(
                campaign_id
            )
            prepared: list[
                tuple[
                    dict[str, Any],
                    Path,
                    bytes | None,
                ]
            ] = []

            for raw in manifest["entries"]:
                if not isinstance(
                    raw,
                    dict,
                ):
                    raise ValueError(
                        "Nieprawidłowy wpis snapshotu."
                    )

                entry = dict(raw)
                target = self._target(
                    entry.get(
                        "relative_path",
                        "",
                    )
                )
                content: bytes | None = None

                if bool(
                    entry.get(
                        "existed",
                        False,
                    )
                ):
                    backup = (
                        snapshot_dir
                        / str(
                            entry.get(
                                "backup_file",
                                "",
                            )
                        )
                    ).resolve(
                        strict=False
                    )

                    try:
                        backup.relative_to(
                            snapshot_dir
                        )
                    except ValueError as error:
                        raise ValueError(
                            "Backup snapshotu wychodzi "
                            "poza katalog kampanii."
                        ) from error

                    content = backup.read_bytes()
                    digest = hashlib.sha256(
                        content
                    ).hexdigest()

                    if digest != str(
                        entry.get(
                            "sha256",
                            "",
                        )
                    ):
                        raise ValueError(
                            "Hash backupu snapshotu "
                            "jest niezgodny."
                        )

                prepared.append(
                    (
                        entry,
                        target,
                        content,
                    )
                )

        except Exception as error:
            return {
                "success": False,
                "status": (
                    "CAMPAIGN_SNAPSHOT_INVALID"
                ),
                "restored": [],
                "removed": [],
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
            }

        staged: list[
            tuple[
                dict[str, Any],
                Path,
                Path | None,
            ]
        ] = []

        try:
            for (
                entry,
                target,
                content,
            ) in prepared:
                temporary: Path | None = None

                if content is not None:
                    target.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=target.parent,
                        prefix=(
                            f".{target.name}."
                        ),
                        suffix=(
                            ".campaign.tmp"
                        ),
                        delete=False,
                    ) as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(
                            handle.fileno()
                        )
                        temporary = Path(
                            handle.name
                        )

                    os.chmod(
                        temporary,
                        int(
                            entry.get(
                                "mode",
                                0o644,
                            )
                            or 0o644
                        ),
                    )

                staged.append(
                    (
                        entry,
                        target,
                        temporary,
                    )
                )

            restored: list[str] = []
            removed: list[str] = []

            for (
                entry,
                target,
                temporary,
            ) in reversed(staged):
                if bool(
                    entry.get(
                        "existed",
                        False,
                    )
                ):
                    if temporary is None:
                        raise RuntimeError(
                            "Brak pliku tymczasowego "
                            "rollbacku."
                        )

                    self._replace_with_retry(
                        temporary,
                        target,
                    )
                    restored.append(
                        str(target)
                    )
                else:
                    if target.exists():
                        if not target.is_file():
                            raise ValueError(
                                "Nowy target kampanii "
                                "nie jest plikiem."
                            )

                        target.unlink()

                    removed.append(
                        str(target)
                    )

            return {
                "success": True,
                "status": (
                    "CAMPAIGN_SNAPSHOT_RESTORED"
                ),
                "restored": restored,
                "removed": removed,
                "errors": [],
            }

        except Exception as error:
            return {
                "success": False,
                "status": (
                    "CAMPAIGN_SNAPSHOT_RESTORE_FAILED"
                ),
                "restored": locals().get(
                    "restored",
                    [],
                ),
                "removed": locals().get(
                    "removed",
                    [],
                ),
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
            }

        finally:
            for (
                _,
                _,
                temporary,
            ) in staged:
                if (
                    temporary is not None
                    and temporary.exists()
                ):
                    temporary.unlink(
                        missing_ok=True
                    )

    def cleanup(
        self,
        campaign_id: str,
    ) -> None:
        shutil.rmtree(
            self._snapshot_dir(
                campaign_id
            ),
            ignore_errors=True,
        )

    def snapshot_path(
        self,
        campaign_id: str,
    ) -> str:
        return str(
            self._snapshot_dir(
                campaign_id
            )
        )

    def _target(
        self,
        relative: Any,
    ) -> Path:
        text = str(
            relative
        ).strip().replace(
            "\\",
            "/",
        )

        if not text:
            raise ValueError(
                "Pusta ścieżka snapshotu."
            )

        unresolved = (
            self.project_root
            / text
        )

        current = unresolved

        while current != self.project_root:
            if (
                current.exists()
                and current.is_symlink()
            ):
                raise ValueError(
                    "Snapshot nie obsługuje symlinków."
                )

            current = current.parent

        candidate = unresolved.resolve(
            strict=False
        )

        try:
            candidate.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ValueError(
                "Ścieżka snapshotu wychodzi "
                "poza projekt."
            ) from error

        return candidate

    def _snapshot_dir(
        self,
        campaign_id: str,
    ) -> Path:
        return (
            self.snapshots_root
            / self._safe_id(
                campaign_id
            )
        )

    @staticmethod
    def _safe_id(
        value: Any,
    ) -> str:
        text = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "-",
            str(value).strip(),
        ).strip("-_")

        if not text:
            raise ValueError(
                "Nieprawidłowe campaign_id."
            )

        return text[:100]

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
                        mode = stat.S_IMODE(
                            destination.stat().st_mode
                        )
                        os.chmod(
                            destination,
                            mode
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
