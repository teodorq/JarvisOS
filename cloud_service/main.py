from __future__ import annotations

import hmac
import json
import math
import os
import threading
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from app.ai.planner_llm import PlannerLLM
from app.cloud.contracts import (
    SCHEMA_VERSION,
    CloudContractError,
    normalize_command,
    validate_cloud_plan,
)
from app.cloud.privacy import CloudPrivacyError, ensure_cloud_safe_command


SERVICE_NAME = "jarvis-os-cloud-planner"
SERVICE_VERSION = "0.4.0"
MAX_BODY_BYTES = 16_384


@dataclass(frozen=True)
class ServiceConfig:
    api_token: str
    environment: str = "production"
    requests_per_minute: int = 30

    @classmethod
    def from_environment(cls) -> "ServiceConfig":
        return cls(
            api_token=(
                os.getenv("JARVIS_OS_CLOUD_API_TOKEN", "").strip()
                or os.getenv("JARVIS_CLOUD_API_TOKEN", "").strip()
            ),
            environment=(
                os.getenv("JARVIS_OS_CLOUD_ENVIRONMENT", "").strip()
                or os.getenv("JARVIS_ENV", "production").strip()
                or "production"
            ),
            requests_per_minute=_requests_per_minute_from_environment(),
        )

def _requests_per_minute_from_environment() -> int:
    value = (
        os.getenv("JARVIS_OS_CLOUD_REQUESTS_PER_MINUTE", "").strip()
        or os.getenv("JARVIS_CLOUD_REQUESTS_PER_MINUTE", "30").strip()
    )
    try:
        limit = int(value)
    except ValueError:
        limit = 30
    return min(max(limit, 1), 120)



class PlannerService:
    def __init__(self, planner: PlannerLLM | None = None) -> None:
        self.planner = planner or PlannerLLM()

    def create_plan(self, command: Any) -> dict[str, Any]:
        normalized = normalize_command(command)
        ensure_cloud_safe_command(normalized)
        raw_plan = self.planner.create_plan(normalized)
        return validate_cloud_plan(raw_plan)


class PlanRateLimiter:
    WINDOW_SECONDS = 60.0

    def __init__(self, limit: int, clock=time.monotonic) -> None:
        self.limit = min(max(int(limit), 1), 120)
        self.clock = clock
        self._lock = threading.Lock()
        self._requests: dict[str, list[float]] = {}

    def allow(self, key: str) -> tuple[bool, int]:
        now = self.clock()
        cutoff = now - self.WINDOW_SECONDS
        with self._lock:
            recent = [
                value
                for value in self._requests.get(key, [])
                if value > cutoff
            ]
            if len(recent) >= self.limit:
                retry_after = max(
                    1, math.ceil(self.WINDOW_SECONDS - (now - recent[0]))
                )
                self._requests[key] = recent
                return False, retry_after
            recent.append(now)
            self._requests[key] = recent
            return True, 0


class JarvisOSCloudServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        config: ServiceConfig,
        service: PlannerService,
        rate_limiter: PlanRateLimiter | None = None,
    ) -> None:
        self.config = config
        self.planner_service = service
        self.rate_limiter = rate_limiter or PlanRateLimiter(
            config.requests_per_minute
        )
        super().__init__(server_address, JarvisOSCloudHandler)


class JarvisOSCloudHandler(BaseHTTPRequestHandler):
    server: JarvisOSCloudServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if urlsplit(self.path).path != "/health":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        self._json(
            HTTPStatus.OK,
            {
                "service": SERVICE_NAME,
                "status": "ok",
                "version": SERVICE_VERSION,
                "environment": self.server.config.environment,
                "auth_configured": bool(self.server.config.api_token),
            },
        )

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/v1/plan":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self.server.config.api_token:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "service_not_configured"},
            )
            return
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        allowed, retry_after = self.server.rate_limiter.allow(
            self.client_address[0]
        )
        if not allowed:
            self._json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"error": "rate_limited"},
                headers={"Retry-After": str(retry_after)},
            )
            return

        try:
            payload = self._read_payload()
            if payload.get("schema_version") != SCHEMA_VERSION:
                raise CloudContractError("unsupported request schema")
            plan = self.server.planner_service.create_plan(payload.get("command"))
        except CloudPrivacyError:
            self._json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "sensitive_command_requires_local"},
            )
            return
        except CloudContractError:
            self._json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "unsupported_or_unsafe_plan"},
            )
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        self._json(
            HTTPStatus.OK,
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": uuid.uuid4().hex,
                "plan": plan,
            },
        )

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(
            header[len(prefix) :], self.server.config.api_token
        )

    def _read_payload(self) -> dict[str, Any]:
        length_text = self.headers.get("Content-Length", "")
        try:
            length = int(length_text)
        except ValueError as error:
            raise ValueError("invalid content length") from error
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("invalid body size")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be an object")
        return payload

    def _json(
        self,
        status: HTTPStatus,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        # Never log request bodies, tokens, or user commands.
        print(f"{self.client_address[0]} - {format % args}", flush=True)


def build_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    config: ServiceConfig | None = None,
    service: PlannerService | None = None,
    rate_limiter: PlanRateLimiter | None = None,
) -> JarvisOSCloudServer:
    return JarvisOSCloudServer(
        (host, port),
        config or ServiceConfig.from_environment(),
        service or PlannerService(),
        rate_limiter=rate_limiter,
    )


def main() -> None:
    host = (
        os.getenv("JARVIS_OS_CLOUD_HOST", "").strip()
        or os.getenv("JARVIS_HOST", "0.0.0.0").strip()
        or "0.0.0.0"
    )
    try:
        port = int(os.getenv("PORT", "8000"))
    except ValueError:
        port = 8000
    server = build_server(host, port)
    print(f"{SERVICE_NAME} listening on {host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
