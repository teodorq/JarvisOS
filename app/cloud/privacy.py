from __future__ import annotations

import re


class CloudPrivacyError(ValueError):
    """Raised when a command must remain on the desktop."""


_SENSITIVE_PATTERNS = (
    re.compile(
        r"(?i)\b(?:api[\s_-]?key|authorization|cookie|credentials?|"
        r"password|passphrase|has(?:l|ł)o|secret|sekret|token)\b"
        r"\s*[:=]\s*[\"']?[^\s\"',;]{4,}"
    ),
    re.compile(
        r"(?i)\b(?:--?(?:api[-_]?key|password|secret|token))\s+"
        r"[\"']?[^\s\"',;]{4,}"
    ),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/-]{8,}={0,2}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b"),
    re.compile(r"\bsk-[a-zA-Z0-9_-]{16,}\b"),
    re.compile(r"\b(?:gh[pousr]_[a-zA-Z0-9_]{20,}|github_pat_[a-zA-Z0-9_]{20,})\b"),
    re.compile(r"\bAIza[a-zA-Z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[a-zA-Z0-9-]{16,}\b"),
)


def ensure_cloud_safe_command(command: str) -> None:
    """Keep commands containing likely credentials out of the cloud."""

    if any(pattern.search(command) for pattern in _SENSITIVE_PATTERNS):
        raise CloudPrivacyError("sensitive command requires local planning")
