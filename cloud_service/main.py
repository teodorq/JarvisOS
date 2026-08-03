from __future__ import annotations

import hmac
import json
import os
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


SERVICE_NAME = "jarvis-os-cloud-planner"
SERVICE_VERSION = "0.1.0"
MAX_BODY_BYTES = 16_384


@dataclass(frozen=True)
class ServiceConfig:
    api_token: str
    environment: str = "production"

    @classmethod
    def from_environment(cls) -> "ServiceConfig":
        return cls(
            api_token=os.getenv("JARVIS_CLOUD_API_TOKEN", "").strip(),
            environment=os.getenv("JARVIS_ENV", "production").strip()
            or "production",
        )


class PlannerService:
    def __init__(self, planner: PlannerLLM | None = None) -> None:
        self.planner = planner or PlannerLLM()

    def create_plan(self, command: Any) -> dict[str, Any]:
        normalized = normalize_command(command)
        raw_plan = self.planner.create_plan(normalized)
        return validate_cloud_plan(raw_plan)


class JarvisCloudServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        config: ServiceConfig,
        service: PlannerService,
    ) -> None:
        self.config = config
        self.planner_service = service
        super().__init__(server_address, JarvisCloudHandler)


class JarvisCloudHandler(BaseHTTPRequestHandler):
    server: JarvisCloudServer
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
        try:
            payload = self._read_payload()
            if payload.get("schema_version") != SCHEMA_VERSION:
                raise CloudContractError("unsupported request schema")
            plan = self.server.planner_service.create_plan(payload.get("command"))
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

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
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
) -> JarvisCloudServer:
    return JarvisCloudServer(
        (host, port),
        config or ServiceConfig.from_environment(),
        service or PlannerService(),
    )


def main() -> None:
    host = os.getenv("JARVIS_HOST", "0.0.0.0")
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
