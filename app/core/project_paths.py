from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT_ENV = "JARVIS_PROJECT_ROOT"


def inferred_project_root() -> Path:
    """Return the project root inferred from app/core/project_paths.py."""
    return Path(__file__).resolve().parents[2]


def resolve_project_root(
    value: str | Path | None = None,
) -> Path:
    """Resolve an explicit, environment or inferred project root."""
    candidate: str | Path

    if value is not None and str(value).strip():
        candidate = value
    else:
        environment_value = os.getenv(
            PROJECT_ROOT_ENV,
            "",
        ).strip()
        candidate = (
            environment_value
            if environment_value
            else inferred_project_root()
        )

    path = Path(candidate).expanduser()

    if not path.is_absolute():
        path = Path.cwd() / path

    return path.resolve(
        strict=False
    )


def default_project_root() -> str:
    """Return a stable project-root string for legacy APIs."""
    return str(
        resolve_project_root()
    ).replace(
        "\\",
        "/",
    )


def default_project_path(
    *parts: str,
) -> str:
    """Return a normalized absolute path inside the project."""
    path = resolve_project_root()

    for part in parts:
        path = path / str(part)

    return str(path).replace(
        "\\",
        "/",
    )


@dataclass(
    frozen=True,
    slots=True,
)
class ProjectPaths:
    root: Path

    @classmethod
    def from_value(
        cls,
        value: str | Path | None = None,
    ) -> "ProjectPaths":
        return cls(
            root=resolve_project_root(
                value
            )
        )

    @property
    def app(self) -> Path:
        return self.root / "app"

    @property
    def tests(self) -> Path:
        return self.root / "tests"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def cache(self) -> Path:
        return self.data / "cache"

    @property
    def memory(self) -> Path:
        return self.data / "memory"

    @property
    def main_memory_file(self) -> Path:
        return self.data / "memory.json"

    @property
    def goal_memory_file(self) -> Path:
        return self.memory / "goals.json"

    @property
    def reflection_memory_file(self) -> Path:
        return self.memory / "reflections.json"

    @property
    def symbol_index_cache(self) -> Path:
        return self.cache / "symbol_index.json"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def archive(self) -> Path:
        return self.root / "archive"

    @property
    def ai_files(self) -> Path:
        return self.root / "AI_PLIKI"

    @property
    def autodev_data(self) -> Path:
        return self.data / "autodev"

    def ensure_runtime_directories(
        self,
    ) -> tuple[Path, ...]:
        directories = (
            self.data,
            self.memory,
            self.cache,
            self.logs,
            self.archive,
            self.ai_files,
            self.autodev_data,
        )

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        return directories

    def as_context(
        self,
    ) -> dict[str, Any]:
        return {
            "project_root": str(
                self.root
            ),
            "data_path": str(
                self.data
            ),
            "cache_path": str(
                self.cache
            ),
            "logs_path": str(
                self.logs
            ),
        }
