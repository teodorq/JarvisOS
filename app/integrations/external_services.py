from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import json
import os
import re
from typing import Any, Mapping
from urllib.parse import urlsplit


class ExternalIntegrationError(RuntimeError):
    """Raised when an external integration fails closed."""


@dataclass(frozen=True)
class _ProviderPolicy:
    provider: str
    enabled_env: str
    endpoint_env: str
    token_env: str
    default_endpoint: str
    fixed_hosts: tuple[str, ...]
    exact_paths: tuple[str, ...] | None
    mode: str
    model_env: str = ""
    allowed_hosts_env: str = ""


_POLICIES = {
    "revenuecat": _ProviderPolicy(
        provider="revenuecat",
        enabled_env="JARVIS_OS_REVENUECAT_MCP_ENABLED",
        endpoint_env="JARVIS_OS_REVENUECAT_MCP_URL",
        token_env="JARVIS_OS_REVENUECAT_MCP_TOKEN",
        default_endpoint="https://mcp.revenuecat.ai/mcp",
        fixed_hosts=("mcp.revenuecat.ai",),
        exact_paths=("/mcp",),
        mode="read_only",
    ),
    "meta_ads": _ProviderPolicy(
        provider="meta_ads",
        enabled_env="JARVIS_OS_META_ADS_MCP_ENABLED",
        endpoint_env="JARVIS_OS_META_ADS_MCP_URL",
        token_env="JARVIS_OS_META_ADS_MCP_ACCESS_TOKEN",
        default_endpoint="",
        fixed_hosts=(),
        exact_paths=None,
        mode="read_only",
        allowed_hosts_env="JARVIS_OS_META_ADS_MCP_ALLOWED_HOSTS",
    ),
    "claude": _ProviderPolicy(
        provider="claude",
        enabled_env="JARVIS_OS_CLAUDE_ENABLED",
        endpoint_env="JARVIS_OS_CLAUDE_API_URL",
        token_env="ANTHROPIC_API_KEY",
        default_endpoint="https://api.anthropic.com/v1/messages",
        fixed_hosts=("api.anthropic.com",),
        exact_paths=("/v1/messages",),
        mode="reasoning_only",
        model_env="JARVIS_OS_CLAUDE_MODEL",
    ),
}

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.:/-]{1,160}$")
_CLAUDE_MODEL = re.compile(r"^claude-[a-z0-9][a-z0-9-]{1,78}$")

_READ_TOKENS = frozenset(
    {
        "analyze",
        "analytics",
        "chart",
        "fetch",
        "find",
        "get",
        "insights",
        "inspect",
        "list",
        "lookup",
        "query",
        "read",
        "report",
        "retrieve",
        "search",
        "status",
        "summary",
    }
)
_WRITE_TOKENS = frozenset(
    {
        "activate",
        "archive",
        "cancel",
        "create",
        "deactivate",
        "delete",
        "disable",
        "edit",
        "enable",
        "grant",
        "launch",
        "pause",
        "publish",
        "refund",
        "remove",
        "resume",
        "revoke",
        "send",
        "set",
        "transfer",
        "update",
        "upload",
        "write",
    }
)
_SENSITIVE_ARGUMENT_MARKERS = frozenset(
    {
        "access_token",
        "api_key",
        "auth_token",
        "authorization",
        "bearer",
        "client_secret",
        "password",
        "private_key",
        "secret",
        "secret_key",
    }
)


def _enabled(value: object) -> bool:
    return str(value or "").strip().lower() in _TRUE_VALUES


def _valid_public_hostname(hostname: str) -> bool:
    host = hostname.strip().lower().rstrip(".")
    if not host or host == "localhost" or host.endswith((".local", ".localhost")):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    labels = host.split(".")
    return len(labels) >= 2 and all(_DNS_LABEL.fullmatch(label) for label in labels)


def _configured_hosts(raw: object) -> tuple[str, ...]:
    values: list[str] = []
    for item in str(raw or "").split(","):
        host = item.strip().lower().rstrip(".")
        if not host:
            continue
        if not _valid_public_hostname(host):
            return ()
        if host not in values:
            values.append(host)
    return tuple(values)


def _endpoint_error(
    endpoint: str,
    allowed_hosts: tuple[str, ...],
    exact_paths: tuple[str, ...] | None,
) -> str:
    if not endpoint:
        return "missing_endpoint"
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        return "invalid_endpoint"
    host = str(parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https":
        return "https_required"
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return "unsafe_endpoint_components"
    if port not in (None, 443):
        return "https_port_required"
    if not _valid_public_hostname(host):
        return "public_dns_host_required"
    if not allowed_hosts or host not in allowed_hosts:
        return "host_not_allowlisted"
    path = parsed.path.rstrip("/") or "/"
    if exact_paths is not None and path not in exact_paths:
        return "path_not_allowlisted"
    if exact_paths is None and (not parsed.path.startswith("/") or ".." in parsed.path):
        return "unsafe_endpoint_path"
    return ""


@dataclass(frozen=True)
class IntegrationSettings:
    provider: str
    enabled: bool
    endpoint: str
    token: str = field(repr=False)
    token_env: str
    allowed_hosts: tuple[str, ...]
    exact_paths: tuple[str, ...] | None
    mode: str
    model: str = ""

    @property
    def configuration_error(self) -> str:
        error = _endpoint_error(self.endpoint, self.allowed_hosts, self.exact_paths)
        if error:
            return error
        if not self.token:
            return "missing_secret"
        if self.provider == "claude" and not _CLAUDE_MODEL.fullmatch(self.model):
            return "invalid_model"
        return ""

    @property
    def ready(self) -> bool:
        return self.enabled and not self.configuration_error

    def require_ready(self) -> None:
        if not self.enabled:
            raise ExternalIntegrationError(f"{self.provider}: integration_disabled")
        error = self.configuration_error
        if error:
            raise ExternalIntegrationError(f"{self.provider}: {error}")

    def status(self) -> dict[str, Any]:
        try:
            endpoint_host = str(urlsplit(self.endpoint).hostname or "").lower()
        except ValueError:
            endpoint_host = ""
        if not _valid_public_hostname(endpoint_host):
            endpoint_host = ""
        return {
            "provider": self.provider,
            "enabled": self.enabled,
            "ready": self.ready,
            "mode": self.mode,
            "endpoint_host": endpoint_host,
            "model": self.model,
            "configuration_error": self.configuration_error,
            "required_secret": self.token_env if not self.token else "",
        }


class ExternalIntegrationRegistry:
    """Create fail-closed external integration settings from an environment."""

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        self.environment = environment if environment is not None else os.environ

    def settings(self, provider: str) -> IntegrationSettings:
        try:
            policy = _POLICIES[provider]
        except KeyError as exc:
            raise ExternalIntegrationError(f"unknown_provider: {provider}") from exc
        if policy.allowed_hosts_env:
            allowed_hosts = _configured_hosts(
                self.environment.get(policy.allowed_hosts_env, "")
            )
        else:
            allowed_hosts = policy.fixed_hosts
        return IntegrationSettings(
            provider=provider,
            enabled=_enabled(self.environment.get(policy.enabled_env, "")),
            endpoint=str(
                self.environment.get(policy.endpoint_env, policy.default_endpoint) or ""
            ).strip(),
            token=str(self.environment.get(policy.token_env, "") or "").strip(),
            token_env=policy.token_env,
            allowed_hosts=allowed_hosts,
            exact_paths=policy.exact_paths,
            mode=policy.mode,
            model=str(
                self.environment.get(policy.model_env, "") if policy.model_env else ""
            ).strip(),
        )

    def status(self) -> dict[str, dict[str, Any]]:
        return {name: self.settings(name).status() for name in _POLICIES}


@dataclass(frozen=True)
class PreparedExternalRequest:
    """A request description whose representation never prints credentials."""

    url: str
    _payload_json: str = field(repr=False)
    _headers: tuple[tuple[str, str], ...] = field(repr=False)
    method: str = "POST"

    @classmethod
    def build(
        cls,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
    ) -> "PreparedExternalRequest":
        return cls(
            url=url,
            _payload_json=json.dumps(
                dict(payload), ensure_ascii=False, separators=(",", ":")
            ),
            _headers=tuple((str(key), str(value)) for key, value in headers.items()),
        )

    @property
    def payload(self) -> dict[str, Any]:
        return dict(json.loads(self._payload_json))

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._headers)

    @property
    def body(self) -> bytes:
        return self._payload_json.encode("utf-8")


def _json_arguments(arguments: Mapping[str, Any] | None) -> dict[str, Any]:
    value = dict(arguments or {})

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                normalized = re.sub(
                    r"(?<!^)(?=[A-Z])", "_", str(key).strip()
                ).lower().replace("-", "_")
                if any(
                    marker in normalized
                    for marker in _SENSITIVE_ARGUMENT_MARKERS
                ):
                    raise ExternalIntegrationError("sensitive_tool_argument_rejected")
                visit(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                visit(nested)

    visit(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ExternalIntegrationError("tool_arguments_must_be_json") from exc
    if len(encoded.encode("utf-8")) > 65_536:
        raise ExternalIntegrationError("tool_arguments_too_large")
    return value


def _require_read_only_tool(tool_name: str) -> str:
    name = str(tool_name or "").strip()
    if not _TOOL_NAME.fullmatch(name):
        raise ExternalIntegrationError("invalid_tool_name")
    tokens = frozenset(
        part for part in re.split(r"[^a-z0-9]+", name.lower()) if part
    )
    if tokens & _WRITE_TOKENS:
        raise ExternalIntegrationError("write_tool_rejected")
    if not tokens & _READ_TOKENS:
        raise ExternalIntegrationError("unknown_tool_rejected")
    return name


class SafeMcpAdapter:
    """Prepare MCP requests while exposing read-only tools only."""

    def __init__(self, settings: IntegrationSettings) -> None:
        if settings.provider not in {"revenuecat", "meta_ads"}:
            raise ExternalIntegrationError("mcp_provider_required")
        if settings.mode != "read_only":
            raise ExternalIntegrationError("read_only_policy_required")
        self.settings = settings

    def prepare_initialize(self, request_id: int = 1) -> PreparedExternalRequest:
        return self._prepare(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "jarvis-os", "version": "1.0"},
                },
            }
        )

    def prepare_tools_list(self, request_id: int = 2) -> PreparedExternalRequest:
        return self._prepare(
            {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}
        )

    def prepare_tool_call(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
        request_id: int = 3,
    ) -> PreparedExternalRequest:
        safe_name = _require_read_only_tool(tool_name)
        return self._prepare(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": safe_name, "arguments": _json_arguments(arguments)},
            }
        )

    def _prepare(self, payload: dict[str, Any]) -> PreparedExternalRequest:
        self.settings.require_ready()
        return PreparedExternalRequest.build(
            url=self.settings.endpoint,
            headers={
                "Authorization": f"Bearer {self.settings.token}",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            payload=payload,
        )


class ClaudeMessagesAdapter:
    """Prepare an optional Claude reasoning request without tools or automation."""

    def __init__(self, settings: IntegrationSettings) -> None:
        if settings.provider != "claude":
            raise ExternalIntegrationError("claude_provider_required")
        self.settings = settings

    def prepare_message(
        self,
        prompt: str,
        *,
        remote_content_approved: bool = False,
        max_tokens: int = 512,
        temperature: float = 0.0,
        system: str = "",
    ) -> PreparedExternalRequest:
        self.settings.require_ready()
        if remote_content_approved is not True:
            raise ExternalIntegrationError("remote_content_not_approved")
        text = str(prompt or "").strip()
        system_text = str(system or "").strip()
        if not text or len(text) > 20_000:
            raise ExternalIntegrationError("invalid_prompt_length")
        if len(system_text) > 5_000:
            raise ExternalIntegrationError("invalid_system_length")
        if not isinstance(max_tokens, int) or not 1 <= max_tokens <= 4_096:
            raise ExternalIntegrationError("invalid_max_tokens")
        try:
            selected_temperature = float(temperature)
        except (TypeError, ValueError) as exc:
            raise ExternalIntegrationError("invalid_temperature") from exc
        if not 0.0 <= selected_temperature <= 1.0:
            raise ExternalIntegrationError("invalid_temperature")
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": max_tokens,
            "temperature": selected_temperature,
            "messages": [{"role": "user", "content": text}],
        }
        if system_text:
            payload["system"] = system_text
        return PreparedExternalRequest.build(
            url=self.settings.endpoint,
            headers={
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "x-api-key": self.settings.token,
            },
            payload=payload,
        )


__all__ = [
    "ClaudeMessagesAdapter",
    "ExternalIntegrationError",
    "ExternalIntegrationRegistry",
    "IntegrationSettings",
    "PreparedExternalRequest",
    "SafeMcpAdapter",
]
