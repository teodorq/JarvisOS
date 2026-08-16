"""Bounded HTTPS JSON transport for reviewed read-only adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests


class MarketDataTransportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedJsonRequest:
    url: str
    allowed_host: str
    headers: tuple[tuple[str, str], ...] = field(default_factory=tuple, repr=False)
    timeout_seconds: float = 5.0
    max_response_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        parsed = urlsplit(self.url)
        try:
            port = parsed.port
        except ValueError as error:
            raise MarketDataTransportError("market_data_request: unsafe_url") from error
        if (
            parsed.scheme != "https"
            or parsed.hostname != self.allowed_host
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise MarketDataTransportError("market_data_request: unsafe_url")
        if not 1 <= self.timeout_seconds <= 15:
            raise MarketDataTransportError("market_data_request: unsafe_timeout")
        if not 1_024 <= self.max_response_bytes <= 4_000_000:
            raise MarketDataTransportError("market_data_request: unsafe_size_limit")

    @classmethod
    def build(
        cls,
        *,
        host: str,
        path: str,
        query: Iterable[tuple[str, str]] = (),
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 5.0,
    ) -> "PreparedJsonRequest":
        if not path.startswith("/") or ".." in path:
            raise MarketDataTransportError("market_data_request: unsafe_path")
        url = urlunsplit(("https", host, path, urlencode(tuple(query)), ""))
        return cls(
            url=url,
            allowed_host=host,
            headers=tuple(
                (str(key), str(value)) for key, value in (headers or {}).items()
            ),
            timeout_seconds=timeout_seconds,
        )

    def public_summary(self) -> dict[str, object]:
        parsed = urlsplit(self.url)
        return {
            "method": "GET",
            "host": parsed.hostname,
            "path": parsed.path,
            "has_credentials": any(
                key.casefold() in {"authorization", "apikey", "x-api-key"}
                for key, _ in self.headers
            ),
        }


class JsonHttpTransport:
    """GET JSON without redirects, unlimited downloads or secret logging."""

    def __call__(self, request: PreparedJsonRequest) -> Any:
        try:
            with requests.get(
                request.url,
                headers=dict(request.headers),
                timeout=request.timeout_seconds,
                allow_redirects=False,
                stream=True,
            ) as response:
                if response.is_redirect or not 200 <= response.status_code < 300:
                    raise MarketDataTransportError(
                        f"market_data_response: http_{response.status_code}"
                    )
                content_type = response.headers.get("Content-Type", "").casefold()
                if "json" not in content_type:
                    raise MarketDataTransportError(
                        "market_data_response: invalid_content_type"
                    )
                declared = response.headers.get("Content-Length", "")
                if declared.isdigit() and int(declared) > request.max_response_bytes:
                    raise MarketDataTransportError("market_data_response: too_large")
                payload = bytearray()
                for chunk in response.iter_content(chunk_size=65_536):
                    payload.extend(chunk)
                    if len(payload) > request.max_response_bytes:
                        raise MarketDataTransportError("market_data_response: too_large")
        except MarketDataTransportError:
            raise
        except requests.RequestException as error:
            raise MarketDataTransportError("market_data_response: unavailable") from error
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise MarketDataTransportError("market_data_response: invalid_json") from error


__all__ = ["JsonHttpTransport", "MarketDataTransportError", "PreparedJsonRequest"]
