from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.cloud.contracts import SCHEMA_VERSION, normalize_command, validate_cloud_plan
from app.cloud.privacy import CloudPrivacyError, ensure_cloud_safe_command


class CloudPlannerError(RuntimeError):
    """Base error for the optional cloud planner."""


class CloudPlannerUnavailable(CloudPlannerError):
    """The remote planner cannot safely serve the request."""


class CloudSensitiveCommand(CloudPlannerError):
    """The command contains data that must remain on the desktop."""


@dataclass(frozen=True)
class CloudPlannerSettings:
    base_url: str = ""
    api_token: str = ""
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> "CloudPlannerSettings":
        timeout_text = _environment_value(
            "JARVIS_OS_CLOUD_TIMEOUT_SECONDS",
            "JARVIS_CLOUD_TIMEOUT_SECONDS",
            default="30",
        )
        try:
            timeout = min(max(float(timeout_text), 1.0), 120.0)
        except ValueError:
            timeout = 30.0
        return cls(
            base_url=_environment_value(
                "JARVIS_OS_CLOUD_URL", "JARVIS_CLOUD_URL"
            ).rstrip("/"),
            api_token=_environment_value(
                "JARVIS_OS_CLOUD_API_TOKEN", "JARVIS_CLOUD_API_TOKEN"
            ),
            timeout_seconds=timeout,
        )


def _environment_value(primary: str, legacy: str, *, default: str = "") -> str:
    return (
        os.getenv(primary, "").strip()
        or os.getenv(legacy, default).strip()
    )


class CloudPlannerClient:
    def __init__(self, settings: CloudPlannerSettings | None = None) -> None:
        self.settings = settings or CloudPlannerSettings.from_environment()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.base_url and self.settings.api_token)

    def create_plan(self, command: str) -> dict[str, Any]:
        if not self.is_configured:
            raise CloudPlannerUnavailable("cloud planner is not configured")
        self._validate_endpoint()
        normalized = normalize_command(command)
        try:
            ensure_cloud_safe_command(normalized)
        except CloudPrivacyError as error:
            raise CloudSensitiveCommand(
                "sensitive command requires local planning"
            ) from error
        payload = {
            "schema_version": SCHEMA_VERSION,
            "command": normalized,
        }
        response = self._request_json("/v1/plan", payload)
        if response.get("schema_version") != SCHEMA_VERSION:
            raise CloudPlannerUnavailable("unsupported cloud response schema")
        try:
            return validate_cloud_plan(response.get("plan"))
        except ValueError as error:
            raise CloudPlannerUnavailable("unsafe cloud plan was rejected") from error

    def health(self) -> dict[str, Any]:
        if not self.settings.base_url:
            raise CloudPlannerUnavailable("cloud planner URL is not configured")
        self._validate_endpoint()
        return self._request_json("/health", None)

    def _request_json(
        self,
        path: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        data = None
        method = "GET"
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = f"Bearer {self.settings.api_token}"
            method = "POST"
        request = urllib.request.Request(
            f"{self.settings.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.settings.timeout_seconds
            ) as response:
                raw = response.read(128_001)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
            raise CloudPlannerUnavailable("cloud planner request failed") from error
        if len(raw) > 128_000:
            raise CloudPlannerUnavailable("cloud planner response is too large")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CloudPlannerUnavailable("cloud planner returned invalid JSON") from error
        if not isinstance(parsed, dict):
            raise CloudPlannerUnavailable("cloud planner response must be an object")
        return parsed

    def _validate_endpoint(self) -> None:
        parsed = urllib.parse.urlsplit(self.settings.base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise CloudPlannerUnavailable("invalid cloud planner URL")
        if parsed.scheme == "https" and parsed.hostname:
            return
        if parsed.scheme == "http" and parsed.hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            return
        raise CloudPlannerUnavailable("cloud planner requires HTTPS")
