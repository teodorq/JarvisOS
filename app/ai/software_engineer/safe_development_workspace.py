from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from app.core.project_paths import resolve_project_root

from .safe_development_models import SafeDevelopmentPolicy, SafeDevelopmentSession
from .safe_development_store import SafeDevelopmentStore


class SafeDevelopmentWorkspace:
    """Creates and audits an isolated source copy for one proposal."""

    COPY_DIRS = ("app", "tests", "config", "tools", "scripts")
    ROOT_SUFFIXES = (".py", ".toml", ".ini", ".txt", ".json", ".yaml", ".yml")
    IGNORED_NAMES = {
        "__pycache__", ".git", ".venv", "venv", "env",
        "AI_PLIKI", "archive", "data",
    }
    RUNTIME_CACHE_DIRS = {"__pycache__", ".pytest_cache", ".safe_development"}
    RUNTIME_CACHE_SUFFIXES = {".pyc", ".pyo"}

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        store: SafeDevelopmentStore | None = None,
        policy: SafeDevelopmentPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or SafeDevelopmentPolicy()
        self.store = store or SafeDevelopmentStore(self.project_root, policy=self.policy)

    def create(
        self,
        session: SafeDevelopmentSession,
        *,
        proposed_content: str,
    ) -> dict[str, Any]:
        session_dir = self.store.session_dir(session.session_id)
        workspace = session_dir / "workspace"
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True, exist_ok=False)
        self._copy_project(workspace)
        target_live = self._live_target(session.target)
        target_copy = self._workspace_target(workspace, session.target)
        if not target_copy.is_file():
            raise FileNotFoundError("Target nie został skopiowany do workspace.")

        original = target_live.read_text(encoding="utf-8")
        before_inventory = self._inventory(workspace)
        target_copy.write_text(proposed_content, encoding="utf-8")
        after_inventory = self._inventory(workspace)
        changed = self._changed_files(before_inventory, after_inventory)
        if changed != [session.target]:
            raise ValueError(
                "Izolowana transformacja zmieniła pliki poza targetem: "
                + ", ".join(changed)
            )

        artifacts = session_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        original_path = artifacts / "original.py"
        proposed_path = artifacts / "proposed.py"
        diff_path = artifacts / "change.diff"
        manifest_path = artifacts / "patch_manifest.json"
        original_path.write_text(original, encoding="utf-8")
        proposed_path.write_text(proposed_content, encoding="utf-8")
        diff_text = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            proposed_content.splitlines(keepends=True),
            fromfile=session.target,
            tofile=session.target,
        ))
        diff_path.write_text(diff_text, encoding="utf-8")
        changed_lines = self.count_changed_lines(original, proposed_content)
        source_hash = self.hash_text(original)
        proposed_hash = self.hash_text(proposed_content)
        manifest = {
            "version": 1,
            "session_id": session.session_id,
            "target": session.target,
            "transform": session.transform,
            "changed_files": changed,
            "changed_lines": changed_lines,
            "source_hash": source_hash,
            "proposed_hash": proposed_hash,
            "workspace_hash": after_inventory.get(session.target, ""),
            "diff_hash": self.hash_text(diff_text),
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            **manifest,
            "workspace_path": str(workspace),
            "original_artifact": str(original_path),
            "proposed_artifact": str(proposed_path),
            "diff_artifact": str(diff_path),
            "manifest_artifact": str(manifest_path),
        }

    def cleanup_runtime_artifacts(
        self,
        session: SafeDevelopmentSession,
    ) -> dict[str, Any]:
        """Remove only generated validation caches from an isolated workspace."""
        workspace = Path(session.workspace_path).resolve(strict=False)
        session_root = self.store.session_dir(session.session_id).resolve(strict=False)
        try:
            workspace.relative_to(session_root)
        except ValueError:
            return {
                "success": False,
                "removed_files": 0,
                "removed_directories": 0,
                "errors": ["Workspace znajduje się poza katalogiem sesji."],
            }
        if not workspace.is_dir():
            return {
                "success": True,
                "removed_files": 0,
                "removed_directories": 0,
                "errors": [],
            }

        removed_files = 0
        removed_directories = 0
        errors: list[str] = []
        paths = sorted(
            workspace.rglob("*"),
            key=lambda item: len(item.parts),
            reverse=True,
        )
        for path in paths:
            try:
                if path.is_file() and path.suffix.casefold() in self.RUNTIME_CACHE_SUFFIXES:
                    path.unlink()
                    removed_files += 1
                elif path.is_dir() and path.name in self.RUNTIME_CACHE_DIRS:
                    shutil.rmtree(path)
                    removed_directories += 1
            except OSError as error:
                errors.append(f"{path.relative_to(workspace).as_posix()}: {error}")
        return {
            "success": not errors,
            "removed_files": removed_files,
            "removed_directories": removed_directories,
            "errors": errors,
        }

    def verify_artifacts(self, session: SafeDevelopmentSession) -> dict[str, Any]:
        original_path = Path(session.original_artifact)
        proposed_path = Path(session.proposed_artifact)
        diff_path = Path(session.diff_artifact)
        for path in (original_path, proposed_path, diff_path):
            self._ensure_session_artifact(session, path)
            if not path.is_file():
                raise FileNotFoundError("Brakuje artefaktu przygotowanej poprawki.")
        original = original_path.read_text(encoding="utf-8")
        proposed = proposed_path.read_text(encoding="utf-8")
        if self.hash_text(original) != session.source_hash:
            raise ValueError("Oryginalny artefakt ma nieprawidłowy hash.")
        if self.hash_text(proposed) != session.proposed_hash:
            raise ValueError("Proponowany artefakt ma nieprawidłowy hash.")
        return {
            "original": original,
            "proposed": proposed,
            "diff": diff_path.read_text(encoding="utf-8"),
        }

    def _copy_project(self, workspace: Path) -> None:
        for name in self.COPY_DIRS:
            source = self.project_root / name
            if not source.is_dir():
                continue
            if source.is_symlink():
                raise ValueError("Nie kopiuję katalogu będącego symlinkiem.")
            shutil.copytree(
                source,
                workspace / name,
                dirs_exist_ok=True,
                ignore=self._ignore,
                symlinks=False,
            )
        for source in self.project_root.iterdir():
            if (
                source.is_file()
                and not source.is_symlink()
                and source.suffix.casefold() in self.ROOT_SUFFIXES
            ):
                shutil.copy2(source, workspace / source.name)

    def _live_target(self, relative: str) -> Path:
        target = (self.project_root / Path(relative)).resolve(strict=False)
        try:
            target.relative_to(self.project_root)
        except ValueError as error:
            raise ValueError("Target znajduje się poza projektem.") from error
        if not target.is_file() or target.is_symlink():
            raise ValueError("Target nie jest bezpiecznym plikiem.")
        return target

    @staticmethod
    def _workspace_target(workspace: Path, relative: str) -> Path:
        target = (workspace / Path(relative)).resolve(strict=False)
        try:
            target.relative_to(workspace.resolve(strict=False))
        except ValueError as error:
            raise ValueError("Target wychodzi poza workspace.") from error
        return target

    def _ensure_session_artifact(
        self,
        session: SafeDevelopmentSession,
        path: Path,
    ) -> None:
        root = self.store.session_dir(session.session_id).resolve(strict=False)
        try:
            path.resolve(strict=False).relative_to(root)
        except ValueError as error:
            raise ValueError("Artefakt znajduje się poza sesją.") from error

    @classmethod
    def _inventory(cls, root: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if path.is_file():
                result[path.relative_to(root).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        return result

    @staticmethod
    def _changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
        return sorted(
            name for name in set(before) | set(after)
            if before.get(name) != after.get(name)
        )

    @staticmethod
    def count_changed_lines(old: str, new: str) -> int:
        return sum(
            1 for line in difflib.ndiff(old.splitlines(), new.splitlines())
            if line.startswith(("+ ", "- "))
        )

    @staticmethod
    def hash_text(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def _ignore(cls, directory: str, names: list[str]) -> set[str]:
        return {
            name for name in names
            if name in cls.IGNORED_NAMES or name.endswith((".pyc", ".pyo"))
        }
