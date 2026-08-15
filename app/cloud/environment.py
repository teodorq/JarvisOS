from __future__ import annotations

import os
from pathlib import Path


MAX_CLOUD_ENV_BYTES = 16_384
ALLOWED_CLOUD_ENVIRONMENT_KEYS = frozenset(
    {
        "JARVIS_OS_CLOUD_URL",
        "JARVIS_OS_CLOUD_API_TOKEN",
        "JARVIS_OS_CLOUD_TIMEOUT_SECONDS",
        "JARVIS_OS_CLOUD_FAILURE_COOLDOWN_SECONDS",
        "JARVIS_OS_REMOTE_DEVICE_ID",
        "JARVIS_OS_REMOTE_POLL_SECONDS",
        "JARVIS_OS_REMOTE_QUEUE_URL",
        "JARVIS_OS_REVENUECAT_MCP_ENABLED",
        "JARVIS_OS_REVENUECAT_MCP_URL",
        "JARVIS_OS_REVENUECAT_MCP_TOKEN",
        "JARVIS_OS_META_ADS_MCP_ENABLED",
        "JARVIS_OS_META_ADS_MCP_URL",
        "JARVIS_OS_META_ADS_MCP_ALLOWED_HOSTS",
        "JARVIS_OS_META_ADS_MCP_ACCESS_TOKEN",
        "JARVIS_OS_CLAUDE_ENABLED",
        "JARVIS_OS_CLAUDE_API_URL",
        "JARVIS_OS_CLAUDE_MODEL",
        "ANTHROPIC_API_KEY",
    }
)


def load_cloud_environment(project_root: str | Path) -> tuple[str, ...]:
    """Load an ignored local cloud config without overriding the environment."""

    path = Path(project_root) / "config" / "cloud.env"
    try:
        if not path.is_file() or path.stat().st_size > MAX_CLOUD_ENV_BYTES:
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
        if key not in ALLOWED_CLOUD_ENVIRONMENT_KEYS or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not value or "\x00" in value:
            continue
        os.environ[key] = value
        loaded.append(key)
    return tuple(loaded)
