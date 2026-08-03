from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import difflib
import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SafePatch:
    patch_id: str
    path: str
    old_content: str
    new_content: str
    unified_diff: str
    changed_lines: int
    old_hash: str
    new_hash: str
    created_at: str
    goal: str = ""
    requires_approval: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafePatchBuilder:
    """
    Buduje patch bez zapisywania zmian do projektu.

    Moduł:
    - czyta istniejący plik,
    - porównuje starą i nową treść,
    - generuje unified diff,
    - oblicza hashe,
    - nie modyfikuje pliku źródłowego.
    """

    def __init__(
        self,
        project_root: str = default_project_root(),
        max_changed_lines: int = 500,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.max_changed_lines = max_changed_lines
        self.last_patch: SafePatch | None = None

    def build(
        self,
        *,
        path: str,
        new_content: str,
        goal: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SafePatch:
        file_path = self._resolve_project_path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"Plik nie istnieje: {file_path}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"Ścieżka nie jest plikiem: {file_path}"
            )

        old_content = file_path.read_text(
            encoding="utf-8"
        )

        if old_content == new_content:
            raise ValueError(
                "Nowa treść jest identyczna z obecną."
            )

        changed_lines = self._count_changed_lines(
            old_content,
            new_content,
        )

        if changed_lines > self.max_changed_lines:
            raise ValueError(
                "Patch przekracza limit zmienionych linii: "
                f"{changed_lines}/{self.max_changed_lines}"
            )

        old_hash = self._hash(old_content)
        new_hash = self._hash(new_content)

        unified_diff = "".join(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(file_path),
                tofile=str(file_path),
            )
        )

        created_at = datetime.now().isoformat()

        patch_id = self._hash(
            f"{file_path}|{old_hash}|{new_hash}|{created_at}"
        )[:16]

        patch = SafePatch(
            patch_id=patch_id,
            path=str(file_path),
            old_content=old_content,
            new_content=new_content,
            unified_diff=unified_diff,
            changed_lines=changed_lines,
            old_hash=old_hash,
            new_hash=new_hash,
            created_at=created_at,
            goal=goal,
            requires_approval=True,
            metadata=dict(metadata or {}),
        )

        self.last_patch = patch
        return patch

    def _resolve_project_path(
        self,
        path: str,
    ) -> Path:
        candidate = Path(path)

        if not candidate.is_absolute():
            candidate = self.project_root / candidate

        resolved = candidate.resolve()

        try:
            resolved.relative_to(self.project_root)
        except ValueError as error:
            raise ValueError(
                "Ścieżka znajduje się poza katalogiem projektu."
            ) from error

        return resolved

    def _count_changed_lines(
        self,
        old_content: str,
        new_content: str,
    ) -> int:
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        max_len = max(len(old_lines), len(new_lines))

        changed = 0

        for index in range(max_len):
            old_line = (
                old_lines[index]
                if index < len(old_lines)
                else None
            )
            new_line = (
                new_lines[index]
                if index < len(new_lines)
                else None
            )

            if old_line != new_line:
                changed += 1

        return changed

    def _hash(
        self,
        value: str,
    ) -> str:
        return hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "max_changed_lines": self.max_changed_lines,
            "has_patch": self.last_patch is not None,
            "last_patch": (
                self.last_patch.to_dict()
                if self.last_patch is not None
                else None
            ),
        }
