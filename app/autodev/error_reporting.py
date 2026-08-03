from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import errno
from pathlib import Path
import re
from typing import Any
import uuid


_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}

_SECRET_PATTERN = re.compile(
    r"(?i)\b("
    r"api[_-]?key|authorization|cookie|credentials?|"
    r"password|secret|token"
    r")\b\s*[:=]\s*([^\s,;]+)"
)

_RETRYABLE_ERRNOS = {
    errno.EAGAIN,
    errno.EBUSY,
    errno.ECONNABORTED,
    errno.ECONNREFUSED,
    errno.ECONNRESET,
    errno.EINTR,
    errno.ENETDOWN,
    errno.ENETRESET,
    errno.ENETUNREACH,
    errno.ETIMEDOUT,
}


@dataclass(
    frozen=True,
    slots=True,
)
class AutoDevErrorReport:
    error_id: str
    stage: str
    error_type: str
    message: str
    retryable: bool
    context: dict[str, Any] = field(
        default_factory=dict
    )
    cause_type: str = ""
    cause_message: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    def summary(
        self,
    ) -> str:
        if self.message:
            return (
                f"{self.error_type}: "
                f"{self.message}"
            )

        return self.error_type

    def as_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "error_id": self.error_id,
            "stage": self.stage,
            "error_type": self.error_type,
            "message": self.message,
            "retryable": self.retryable,
            "context": dict(self.context),
            "cause_type": self.cause_type,
            "cause_message": self.cause_message,
            "created_at": self.created_at,
        }


class AutoDevErrorReporter:
    """Creates safe, structured AutoDev error reports."""

    @classmethod
    def capture(
        cls,
        error: BaseException,
        *,
        stage: str,
        context: dict[str, Any] | None = None,
        project_root: str | Path | None = None,
    ) -> AutoDevErrorReport:
        cause = (
            error.__cause__
            or error.__context__
        )

        return AutoDevErrorReport(
            error_id=uuid.uuid4().hex,
            stage=cls._clean_text(
                stage,
                project_root=project_root,
                limit=120,
            )
            or "autodev",
            error_type=type(error).__name__,
            message=cls._clean_text(
                str(error),
                project_root=project_root,
            ),
            retryable=cls.is_retryable(
                error
            ),
            context=cls.safe_context(
                context,
                project_root=project_root,
            ),
            cause_type=(
                type(cause).__name__
                if cause is not None
                else ""
            ),
            cause_message=(
                cls._clean_text(
                    str(cause),
                    project_root=project_root,
                )
                if cause is not None
                else ""
            ),
        )

    @staticmethod
    def is_retryable(
        error: BaseException,
    ) -> bool:
        if isinstance(
            error,
            (
                TimeoutError,
                ConnectionError,
                BlockingIOError,
                InterruptedError,
            ),
        ):
            return True

        if isinstance(
            error,
            OSError,
        ):
            return (
                error.errno
                in _RETRYABLE_ERRNOS
            )

        return False

    @classmethod
    def safe_context(
        cls,
        context: dict[str, Any] | None,
        *,
        project_root: str | Path | None = None,
    ) -> dict[str, Any]:
        return cls._sanitize_value(
            dict(context or {}),
            project_root=project_root,
            depth=0,
        )

    @classmethod
    def _sanitize_value(
        cls,
        value: Any,
        *,
        project_root: str | Path | None,
        depth: int,
    ) -> Any:
        if depth >= 4:
            return "<MAX_DEPTH>"

        if isinstance(
            value,
            dict,
        ):
            result: dict[str, Any] = {}

            for index, (
                key,
                item,
            ) in enumerate(
                value.items()
            ):
                if index >= 25:
                    result["<TRUNCATED>"] = True
                    break

                normalized_key = str(
                    key
                )
                key_token = normalized_key.casefold().replace(
                    "-",
                    "_",
                )

                if (
                    key_token in _SECRET_KEYS
                    or any(
                        secret in key_token
                        for secret in (
                            "password",
                            "secret",
                            "token",
                            "credential",
                            "api_key",
                        )
                    )
                ):
                    result[normalized_key] = "<REDACTED>"
                    continue

                result[normalized_key] = cls._sanitize_value(
                    item,
                    project_root=project_root,
                    depth=depth + 1,
                )

            return result

        if isinstance(
            value,
            (list, tuple, set),
        ):
            return [
                cls._sanitize_value(
                    item,
                    project_root=project_root,
                    depth=depth + 1,
                )
                for item in list(value)[:25]
            ]

        if isinstance(
            value,
            (
                str,
                Path,
            ),
        ):
            return cls._clean_text(
                str(value),
                project_root=project_root,
            )

        if value is None or isinstance(
            value,
            (
                bool,
                int,
                float,
            ),
        ):
            return value

        return cls._clean_text(
            repr(value),
            project_root=project_root,
        )

    @staticmethod
    def _clean_text(
        value: str,
        *,
        project_root: str | Path | None,
        limit: int = 500,
    ) -> str:
        text = str(value).replace(
            "\x00",
            "",
        )
        text = " ".join(
            text.split()
        )
        text = _SECRET_PATTERN.sub(
            lambda match: (
                f"{match.group(1)}=<REDACTED>"
            ),
            text,
        )

        if project_root:
            raw_root = str(
                project_root
            ).strip()
            resolved_root = str(
                Path(raw_root).expanduser().resolve(
                    strict=False
                )
            )
            candidates = {
                raw_root,
                raw_root.replace(
                    "\\",
                    "/",
                ),
                raw_root.replace(
                    "/",
                    "\\",
                ),
                resolved_root,
                resolved_root.replace(
                    "\\",
                    "/",
                ),
                resolved_root.replace(
                    "/",
                    "\\",
                ),
            }

            for candidate in sorted(
                candidates,
                key=len,
                reverse=True,
            ):
                if candidate:
                    text = re.sub(
                        re.escape(candidate),
                        "<PROJECT_ROOT>",
                        text,
                        flags=re.IGNORECASE,
                    )

        if len(text) > limit:
            return (
                text[: max(
                    0,
                    limit - 3,
                )]
                + "..."
            )

        return text
