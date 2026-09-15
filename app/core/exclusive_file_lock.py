"""Small cross-process lock for short atomic file transactions."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import time
from typing import Iterator

if os.name == "nt":
    import msvcrt
else:  # pragma: no cover - JARVIS local runtime is Windows.
    import fcntl


@contextmanager
def exclusive_file_lock(
    path: str | Path,
    *,
    timeout_seconds: float = 10.0,
    timeout_message: str = "file lock timeout",
) -> Iterator[None]:
    """Serialize a short transaction using an OS-released byte-range lock."""
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.1, float(timeout_seconds))
    stream = lock_path.open("a+b")
    stream.seek(0, os.SEEK_END)
    if stream.tell() == 0:
        stream.write(b"\0")
        stream.flush()
        os.fsync(stream.fileno())
    acquired = False
    while not acquired:
        try:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - JARVIS local runtime is Windows.
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            if time.monotonic() >= deadline:
                stream.close()
                raise TimeoutError(timeout_message)
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - JARVIS local runtime is Windows.
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


__all__ = ["exclusive_file_lock"]
