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
from urllib.parse import parse_qs, urlsplit

from app.ai.planner_llm import PlannerLLM
from app.cloud.contracts import (
    SCHEMA_VERSION,
    CloudContractError,
    normalize_command,
    validate_cloud_plan,
)
from app.cloud.privacy import CloudPrivacyError, ensure_cloud_safe_command
from cloud_service.phone_ui import (
    PHONE_FORBIDDEN_PAGE,
    PHONE_ICON,
    PHONE_LOGIN_PAGE,
    PHONE_LOGOUT_PAGE,
    PHONE_MANIFEST,
    PHONE_OFFLINE_PAGE,
    PHONE_PAGE,
    PHONE_SERVICE_WORKER,
    PHONE_START_PAGE,
    phone_diagnostics_page,
    phone_login_complete_page,
)
from cloud_service.remote_store import (
    RemoteCommandStore,
    RemoteStoreConflict,
    normalize_command_id,
    normalize_device_id,
    normalize_event_status,
    remote_store_from_environment,
)


SERVICE_NAME = "jarvis-os-cloud-planner"
SERVICE_VERSION = "0.9.3"
MAX_BODY_BYTES = 16_384


@dataclass(frozen=True)
class ServiceConfig:
    api_token: str
    environment: str = "production"
    requests_per_minute: int = 30
    phone_api_token: str = ""
    phone_principal_id: str = ""
    build_sha: str = "development"

    @classmethod
    def from_environment(cls) -> "ServiceConfig":
        return cls(
            api_token=os.getenv(
                "JARVIS_OS_CLOUD_API_TOKEN", ""
            ).strip(),
            environment=(
                os.getenv("JARVIS_OS_CLOUD_ENVIRONMENT", "").strip()
                or os.getenv("JARVIS_ENV", "production").strip()
                or "production"
            ),
            requests_per_minute=_requests_per_minute_from_environment(),
            phone_api_token=os.getenv(
                "JARVIS_OS_PHONE_API_TOKEN", ""
            ).strip(),
            phone_principal_id=os.getenv(
                "JARVIS_OS_PHONE_PRINCIPAL_ID", ""
            ).strip().lower(),
            build_sha=(
                os.getenv("JARVIS_OS_BUILD_SHA", "").strip().lower()
                or "development"
            ),
        )

def _requests_per_minute_from_environment() -> int:
    value = os.getenv(
        "JARVIS_OS_CLOUD_REQUESTS_PER_MINUTE", "30"
    ).strip()
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
        remote_store: RemoteCommandStore | None = None,
    ) -> None:
        self.config = config
        self.planner_service = service
        self.rate_limiter = rate_limiter or PlanRateLimiter(
            config.requests_per_minute
        )
        self.remote_store = remote_store
        super().__init__(server_address, JarvisOSCloudHandler)


class JarvisOSCloudHandler(BaseHTTPRequestHandler):
    server: JarvisOSCloudServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._begin_request()
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            self._json(HTTPStatus.OK, {
                "service": SERVICE_NAME,
                "status": "ok",
                "version": SERVICE_VERSION,
                "build_sha": self.server.config.build_sha,
                "environment": self.server.config.environment,
                "auth_configured": bool(self.server.config.api_token),
                "remote_configured": self._remote_ready(),
                "remote_transport": self._remote_transport(),
                "remote_access_verified": self._remote_access_verified(),
            })
            return
        if parsed.path == "/phone":
            self._handle_phone_page()
            return
        if parsed.path == "/phone.webmanifest":
            self._asset(
                PHONE_MANIFEST, "application/manifest+json; charset=utf-8"
            )
            return
        if parsed.path == "/phone-sw.js":
            self._asset(
                PHONE_SERVICE_WORKER,
                "application/javascript; charset=utf-8",
                headers={"Service-Worker-Allowed": "/phone"},
            )
            return
        if parsed.path == "/phone-icon.svg":
            self._asset(PHONE_ICON, "image/svg+xml; charset=utf-8")
            return
        if parsed.path == "/phone-offline":
            self._html(PHONE_OFFLINE_PAGE, allow_script=True)
            return
        if parsed.path in {"/phone-recover", "/mobile-start"}:
            self._html(
                PHONE_START_PAGE.replace(
                    "%2Fphone", "%2Fmobile-complete"
                )
            )
            return
        if parsed.path == "/mobile-logout":
            self._html(PHONE_LOGOUT_PAGE)
            return
        if parsed.path == "/mobile-complete":
            self._handle_phone_login_complete()
            return
        if parsed.path == "/mobile-diagnostics":
            self._handle_phone_diagnostics()
            return
        if parsed.path == "/v1/phone/me":
            self._handle_phone_identity()
            return
        if parsed.path == "/v1/remote/commands/next":
            self._handle_remote_claim(parsed)
            return
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 4 and parts[:3] == ["v1", "remote", "commands"]:
            self._handle_remote_status(parsed, parts[3])
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        self._begin_request()
        parsed = urlsplit(self.path)
        if parsed.path == "/v1/plan":
            self._handle_plan()
            return
        if parsed.path == "/v1/remote/commands":
            self._handle_remote_submit()
            return
        if parsed.path == "/v1/remote/probe":
            self._handle_remote_probe()
            return
        parts = parsed.path.strip("/").split("/")
        if (
            len(parts) == 5
            and parts[:3] == ["v1", "remote", "commands"]
            and parts[4] == "events"
        ):
            self._handle_remote_event(parsed, parts[3])
            return
        self._reject_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _handle_plan(self) -> None:
        if not self.server.config.api_token:
            self._reject_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "service_not_configured"},
            )
            return
        if not self._authorized():
            self._reject_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": "unauthorized"},
            )
            return
        allowed, retry_after = self.server.rate_limiter.allow(self.client_address[0])
        if not allowed:
            self._reject_json(
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
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "sensitive_command_requires_local"})
            return
        except CloudContractError:
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "unsupported_or_unsafe_plan"})
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        self._json(HTTPStatus.OK, {"schema_version": SCHEMA_VERSION, "request_id": uuid.uuid4().hex, "plan": plan})

    def _handle_remote_submit(self) -> None:
        if not self._remote_ready():
            self._reject_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "remote_not_configured"},
            )
            return
        if not self._phone_authorized():
            self._reject_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": "unauthorized"},
            )
            return
        allowed, retry_after = self.server.rate_limiter.allow("phone:" + self.client_address[0])
        if not allowed:
            self._reject_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"error": "rate_limited"},
                headers={"Retry-After": str(retry_after)},
            )
            return
        try:
            payload = self._read_payload()
            device_id = normalize_device_id(payload.get("device_id"))
            command = normalize_command(payload.get("command"))
            ensure_cloud_safe_command(command)
            record = self.server.remote_store.create(
                device_id,
                command,
                kind="command",
                request_id=self._request_id(payload),
            )
        except RemoteStoreConflict:
            self._json(
                HTTPStatus.CONFLICT,
                {"error": "request_id_conflict"},
            )
            return
        except CloudPrivacyError:
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "sensitive_command_requires_local", "message": "To polecenie zawiera dane, które muszą pozostać na komputerze."})
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        except Exception:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "remote_temporarily_unavailable"},
            )
            return
        self._json(HTTPStatus.ACCEPTED, record)

    def _handle_remote_probe(self) -> None:
        if not self._remote_ready():
            self._reject_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "remote_not_configured"},
            )
            return
        if not self._phone_authorized():
            self._reject_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": "unauthorized"},
            )
            return
        allowed, retry_after = self.server.rate_limiter.allow(
            "phone:" + self.client_address[0]
        )
        if not allowed:
            self._reject_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"error": "rate_limited"},
                headers={"Retry-After": str(retry_after)},
            )
            return
        try:
            payload = self._read_payload()
            device_id = normalize_device_id(payload.get("device_id"))
            record = self.server.remote_store.create(
                device_id,
                "sprawdzenie dostępności",
                kind="probe",
                request_id=self._request_id(payload),
            )
        except RemoteStoreConflict:
            self._json(
                HTTPStatus.CONFLICT,
                {"error": "request_id_conflict"},
            )
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        except Exception:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "remote_temporarily_unavailable"},
            )
            return
        self._json(HTTPStatus.ACCEPTED, record)

    def _handle_remote_claim(self, parsed) -> None:
        if not self._remote_ready():
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "remote_not_configured"})
            return
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        if bool(
            getattr(self.server.remote_store, "direct_queue_enabled", False)
        ):
            self._empty(HTTPStatus.NO_CONTENT)
            return
        try:
            record = self.server.remote_store.claim_next(self._device_from_query(parsed))
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        if record is None:
            self._empty(HTTPStatus.NO_CONTENT)
            return
        self._json(HTTPStatus.OK, record)

    def _handle_remote_status(self, parsed, raw_command_id: str) -> None:
        if not self._remote_ready():
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "remote_not_configured"})
            return
        if not self._phone_authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        try:
            record = self.server.remote_store.get(
                self._device_from_query(parsed), normalize_command_id(raw_command_id)
            )
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        if record is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "command_not_found"})
            return
        self._json(HTTPStatus.OK, record)

    def _handle_remote_event(self, parsed, raw_command_id: str) -> None:
        if not self._remote_ready():
            self._reject_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "remote_not_configured"},
            )
            return
        if not self._authorized():
            self._reject_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": "unauthorized"},
            )
            return
        try:
            device_id = self._device_from_query(parsed)
            command_id = normalize_command_id(raw_command_id)
            payload = self._read_payload()
            status = normalize_event_status(payload.get("status"))
            message = " ".join(str(payload.get("message", "")).split())[:2_000]
            if not message:
                raise ValueError("message cannot be empty")
            try:
                ensure_cloud_safe_command(message)
            except CloudPrivacyError:
                message = "Wynik zawiera prywatne dane i pozostał tylko na komputerze."
            record = self.server.remote_store.set_status(device_id, command_id, status, message)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        if record is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "command_not_found"})
            return
        self._json(HTTPStatus.OK, record)

    def _remote_ready(self) -> bool:
        return bool(
            self.server.remote_store
            and (
                self.server.config.phone_principal_id
                or self.server.config.phone_api_token
            )
        )

    def _remote_transport(self) -> str:
        if not self.server.remote_store:
            return "disabled"
        if bool(
            getattr(self.server.remote_store, "direct_queue_enabled", False)
        ):
            return "azure_queue"
        return "https_poll"

    def _remote_access_verified(self) -> bool:
        return bool(
            self.server.remote_store
            and getattr(
                self.server.remote_store, "access_verified", False
            )
        )

    def _phone_authorized(self) -> bool:
        if self._phone_identity_authorized():
            return True
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        return bool(
            self.server.config.phone_api_token
            and header.startswith(prefix)
            and hmac.compare_digest(
                header[len(prefix):], self.server.config.phone_api_token
            )
        )

    def _phone_identity_authorized(self) -> bool:
        expected = self.server.config.phone_principal_id
        principal_id = self.headers.get(
            "X-MS-CLIENT-PRINCIPAL-ID", ""
        ).strip().lower()
        provider = self.headers.get(
            "X-MS-CLIENT-PRINCIPAL-IDP", ""
        ).strip().lower()
        return bool(
            expected
            and principal_id
            and provider == "aad"
            and hmac.compare_digest(principal_id, expected)
        )

    def _handle_phone_page(self) -> None:
        if not self.server.config.phone_principal_id:
            self._html(
                PHONE_PAGE.replace(
                    'href="/mobile-start">WYLOGUJ TEN TELEFON',
                    'href="/mobile-logout">WYLOGUJ TEN TELEFON',
                ),
                allow_script=True,
            )
            return
        principal_id = self.headers.get(
            "X-MS-CLIENT-PRINCIPAL-ID", ""
        ).strip()
        if not principal_id:
            self._html(
                PHONE_LOGIN_PAGE.replace(
                    "%2Fphone", "%2Fmobile-complete"
                )
            )
            return
        if not self._phone_identity_authorized():
            self._html(
                PHONE_FORBIDDEN_PAGE.replace(
                    'href="/mobile-start"', 'href="/mobile-logout"'
                ),
                status=HTTPStatus.FORBIDDEN,
            )
            return
        self._html(
            PHONE_PAGE.replace(
                'href="/mobile-start">WYLOGUJ TEN TELEFON',
                'href="/mobile-logout">WYLOGUJ TEN TELEFON',
            ),
            allow_script=True,
        )

    def _handle_phone_login_complete(self) -> None:
        principal_id = self.headers.get(
            "X-MS-CLIENT-PRINCIPAL-ID", ""
        ).strip()
        provider = self.headers.get(
            "X-MS-CLIENT-PRINCIPAL-IDP", ""
        ).strip().lower()
        self._html(phone_login_complete_page(
            identity_present=bool(principal_id),
            provider_valid=provider == "aad",
            owner_authorized=self._phone_identity_authorized(),
            request_id=self._trace_id(),
        ))

    def _handle_phone_diagnostics(self) -> None:
        principal_id = self.headers.get(
            "X-MS-CLIENT-PRINCIPAL-ID", ""
        ).strip()
        provider = self.headers.get(
            "X-MS-CLIENT-PRINCIPAL-IDP", ""
        ).strip().lower()
        self._html(phone_diagnostics_page(
            identity_present=bool(principal_id),
            provider_valid=provider == "aad",
            owner_authorized=self._phone_identity_authorized(),
            remote_configured=self._remote_ready(),
            storage_verified=self._remote_access_verified(),
            request_id=self._trace_id(),
            version=SERVICE_VERSION,
            build_sha=self.server.config.build_sha,
        ))

    def _handle_phone_identity(self) -> None:
        if not self._phone_identity_authorized():
            self._json(
                HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"}
            )
            return
        name = self.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", ""
        ).strip()
        self._json(
            HTTPStatus.OK,
            {"name": name or "Konto Microsoft", "session_minutes": 60},
        )

    @staticmethod
    def _device_from_query(parsed) -> str:
        value = parse_qs(parsed.query).get("device_id", [""])[0]
        return normalize_device_id(value)

    @staticmethod
    def _request_id(payload: dict[str, Any]) -> str | None:
        value = payload.get("request_id")
        if value in (None, ""):
            return None
        return normalize_command_id(value)

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
        payload = dict(payload)
        payload.setdefault("trace_id", self._trace_id())
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-JARVIS-REQUEST-ID", self._trace_id())
        self.send_header("Connection", "close")
        self.close_connection = True
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _reject_json(
        self,
        status: HTTPStatus,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._discard_small_request_body()
        self._json(status, payload, headers=headers)

    def _discard_small_request_body(self) -> None:
        if self.command != "POST":
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            return
        previous_timeout = self.connection.gettimeout()
        try:
            self.connection.settimeout(0.25)
            remaining = length
            while remaining:
                chunk = self.rfile.read(min(remaining, 4_096))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            return
        finally:
            try:
                self.connection.settimeout(previous_timeout)
            except OSError:
                pass

    def _empty(self, status: HTTPStatus) -> None:
        self.send_response(int(status))
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-JARVIS-REQUEST-ID", self._trace_id())
        self.end_headers()

    def _html(
        self,
        value: str,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        allow_script: bool = False,
    ) -> None:
        body = value.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Disposition", "inline")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-JARVIS-REQUEST-ID", self._trace_id())
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Referrer-Policy",
            "same-origin" if allow_script else "no-referrer",
        )
        script_policy = "'unsafe-inline'" if allow_script else "'none'"
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; "
            f"script-src {script_policy}; connect-src 'self'; "
            "img-src 'self'; manifest-src 'self'; worker-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _asset(
        self,
        value: str,
        content_type: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = value.encode("utf-8")
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Disposition", "inline")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-JARVIS-REQUEST-ID", self._trace_id())
        for name, header_value in (headers or {}).items():
            self.send_header(name, header_value)
        self.end_headers()
        self.wfile.write(body)

    def _begin_request(self) -> None:
        self._jarvis_trace_id = uuid.uuid4().hex

    def _trace_id(self) -> str:
        trace_id = getattr(self, "_jarvis_trace_id", "")
        if not trace_id:
            trace_id = uuid.uuid4().hex
            self._jarvis_trace_id = trace_id
        return trace_id

    def log_message(self, format: str, *args: Any) -> None:
        # Never log request bodies, tokens, or user commands.
        print(
            f"{self.client_address[0]} [{self._trace_id()}] - "
            f"{format % args}",
            flush=True,
        )


def build_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    config: ServiceConfig | None = None,
    service: PlannerService | None = None,
    rate_limiter: PlanRateLimiter | None = None,
    remote_store: RemoteCommandStore | None = None,
) -> JarvisOSCloudServer:
    selected_config = config or ServiceConfig.from_environment()
    return JarvisOSCloudServer(
        (host, port),
        selected_config,
        service or PlannerService(),
        rate_limiter=rate_limiter,
        remote_store=remote_store if remote_store is not None else remote_store_from_environment(),
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
