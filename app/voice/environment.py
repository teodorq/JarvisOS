"""Load optional voice provider settings from an ignored local file."""

from __future__ import annotations

import os
from pathlib import Path


MAX_VOICE_ENV_BYTES = 16_384
ALLOWED_VOICE_ENVIRONMENT_KEYS = frozenset(
    {
        "JARVIS_OS_VOICE_PROVIDER",
        "JARVIS_OS_VOICE_TIMEOUT_SECONDS",
        "CARTESIA_API_KEY",
        "CARTESIA_VOICE_ID",
        "JARVIS_OS_CARTESIA_MODEL_ID",
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_VOICE_ID",
        "JARVIS_OS_ELEVENLABS_MODEL_ID",
    }
)


def load_voice_environment(project_root: str | Path) -> tuple[str, ...]:
    """Load allow-listed voice settings without overriding process variables."""

    path = Path(project_root) / "config" / "voice.env"
    try:
        if not path.is_file() or path.stat().st_size > MAX_VOICE_ENV_BYTES:
            return ()
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return ()

    loaded: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in ALLOWED_VOICE_ENVIRONMENT_KEYS or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not value or "\x00" in value:
            continue
        os.environ[key] = value
        loaded.append(key)
    return tuple(loaded)


__all__ = [
    "ALLOWED_VOICE_ENVIRONMENT_KEYS",
    "MAX_VOICE_ENV_BYTES",
    "load_voice_environment",
]
