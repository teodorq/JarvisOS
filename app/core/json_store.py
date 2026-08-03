from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any


_PATH_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, Any] = {}


def _shared_path_lock(path: Path):
    key = os.path.normcase(str(path))
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(key, threading.RLock())


def _replace_with_retry(source: Path, destination: Path) -> None:
    for attempt in range(32):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 15:
                raise
            # Windows file locks can be transient; retry with a short backoff.
            time.sleep(min(0.05 * (attempt + 1), 1.0))


class JsonStore:
    """Thread-safe JSON storage with atomic replacement."""

    def __init__(
        self,
        path: str | Path,
        default_factory: Callable[[], Any],
        *,
        indent: int = 4,
    ) -> None:
        self.path = Path(
            path
        ).expanduser().resolve(
            strict=False
        )
        self.default_factory = default_factory
        self.indent = indent
        self._lock = _shared_path_lock(self.path)

    def exists(
        self,
    ) -> bool:
        return self.path.is_file()

    def load(
        self,
    ) -> Any:
        with self._lock:
            if not self.path.exists():
                return self.default_factory()

            try:
                with self.path.open(
                    "r",
                    encoding="utf-8",
                ) as file:
                    return json.load(
                        file
                    )
            except (
                OSError,
                UnicodeError,
                json.JSONDecodeError,
            ):
                return self.default_factory()

    def save(
        self,
        value: Any,
    ) -> None:
        with self._lock:
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            temporary_path: Path | None = None

            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.path.parent,
                    prefix=f".{self.path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(
                        temporary_file.name
                    )
                    json.dump(
                        value,
                        temporary_file,
                        indent=self.indent,
                        ensure_ascii=False,
                    )
                    temporary_file.flush()
                    os.fsync(
                        temporary_file.fileno()
                    )

                _replace_with_retry(temporary_path, self.path)
            except Exception:
                if (
                    temporary_path is not None
                    and temporary_path.exists()
                ):
                    try:
                        temporary_path.unlink()
                    except OSError:
                        raise RuntimeError("AutoDev: przechwycony wyjątek")

                raise

