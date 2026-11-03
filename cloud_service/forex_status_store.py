from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import PurePosixPath
import re
from typing import Any, Protocol


FOREX_STATUS_SCHEMA_VERSION = 1
FOREX_STATUS_MAX_BYTES = 65_536
FOREX_STATUS_FRESH_SECONDS = 7_200

_STORAGE_ACCOUNT = re.compile(r"^[a-z0-9]{3,24}$")
_CONTAINER = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")
_BLOB = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_:.-]{0,159}$")
_CYCLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
_PAIR = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")


class ForexStatusStoreError(RuntimeError):
    """Raised when the sanitized PAPER status cannot be used safely."""


class ForexStatusNotReady(ForexStatusStoreError):
    """Raised when the first sanitized PAPER status is not available yet."""


class ForexStatusStore(Protocol):
    access_verified: bool

    def read(self) -> dict[str, Any]: ...

    def write(self, value: object) -> dict[str, Any]: ...


def _code(value: object, *, required: bool = False) -> str:
    selected = str(value or "").strip()
    if not selected and not required:
        return ""
    if not _CODE.fullmatch(selected):
        raise ForexStatusStoreError("forex_status: invalid_code")
    return selected


def _cycle_id(value: object) -> str:
    selected = str(value or "").strip()
    if not _CYCLE_ID.fullmatch(selected):
        raise ForexStatusStoreError("forex_status: invalid_cycle_id")
    return selected


def _timestamp(value: object) -> str:
    selected = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(selected.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ForexStatusStoreError("forex_status: invalid_timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ForexStatusStoreError("forex_status: invalid_timestamp")
    return parsed.astimezone(timezone.utc).isoformat()


def _count(value: object, *, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool):
        raise ForexStatusStoreError("forex_status: invalid_count")
    try:
        selected = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ForexStatusStoreError("forex_status: invalid_count") from error
    if selected < 0 or selected > maximum:
        raise ForexStatusStoreError("forex_status: invalid_count")
    return selected


def _decimal_text(value: object, *, optional: bool = False) -> str:
    selected = str(value if value is not None else "").strip()
    if optional and not selected:
        return ""
    if not selected or len(selected) > 32:
        raise ForexStatusStoreError("forex_status: invalid_decimal")
    try:
        number = Decimal(selected)
    except (InvalidOperation, ValueError) as error:
        raise ForexStatusStoreError("forex_status: invalid_decimal") from error
    if not number.is_finite() or abs(number) > Decimal("1000000000000"):
        raise ForexStatusStoreError("forex_status: invalid_decimal")
    return selected


def _position(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ForexStatusStoreError("forex_status: invalid_position")
    pair = str(value.get("pair", "")).strip().upper()
    side = str(value.get("side", "")).strip().upper()
    if not _PAIR.fullmatch(pair) or side not in {"LONG", "SHORT"}:
        raise ForexStatusStoreError("forex_status: invalid_position")
    return {
        "pair": pair,
        "side": side,
        "entry_price": _decimal_text(value.get("entry_price")),
        "current_price": _decimal_text(value.get("current_price")),
        "stop_loss": _decimal_text(value.get("stop_loss")),
        "take_profit": _decimal_text(
            value.get("take_profit"), optional=True
        ),
        "opened_at": _timestamp(value.get("opened_at")),
        "initial_risk_pln": _decimal_text(
            value.get("initial_risk_pln"), optional=True
        ),
    }


def _pair_breakdown(value: object) -> dict[str, dict[str, Any]]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict) or len(value) > 20:
        raise ForexStatusStoreError("forex_status: invalid_pair_breakdown")
    result: dict[str, dict[str, Any]] = {}
    for raw_pair, raw_metrics in sorted(value.items()):
        pair = str(raw_pair).strip().upper()
        if not _PAIR.fullmatch(pair) or not isinstance(raw_metrics, dict):
            raise ForexStatusStoreError("forex_status: invalid_pair_breakdown")
        result[pair] = {
            "closed_trade_count": _count(
                raw_metrics.get("closed_trade_count", 0)
            ),
            "win_rate_pct": _decimal_text(
                raw_metrics.get("win_rate_pct", "0")
            ),
            "net_realized_pnl_pln": _decimal_text(
                raw_metrics.get("net_realized_pnl_pln", "0")
            ),
            "average_trade_pnl_pln": _decimal_text(
                raw_metrics.get("average_trade_pnl_pln", "0")
            ),
            "profit_factor": _decimal_text(
                raw_metrics.get("profit_factor"), optional=True
            ),
        }
    return result


def _performance(value: object) -> dict[str, Any]:
    selected = dict(value) if isinstance(value, dict) else {}
    return {
        "status": _code(selected.get("status", "")),
        "valid_closed_trade_count": _count(
            selected.get("valid_closed_trade_count", 0)
        ),
        "minimum_closed_trades_for_review": _count(
            selected.get("minimum_closed_trades_for_review", 0)
        ),
        "sample_progress_pct": _decimal_text(
            selected.get("sample_progress_pct", "0")
        ),
        "win_rate_pct": _decimal_text(selected.get("win_rate_pct", "0")),
        "net_realized_pnl_pln": _decimal_text(
            selected.get("net_realized_pnl_pln", "0")
        ),
        "average_trade_pnl_pln": _decimal_text(
            selected.get("average_trade_pnl_pln", "0")
        ),
        "profit_factor": _decimal_text(
            selected.get("profit_factor"), optional=True
        ),
        "maximum_closed_trade_drawdown_pln": _decimal_text(
            selected.get("maximum_closed_trade_drawdown_pln", "0")
        ),
        "maximum_closed_trade_drawdown_pct": _decimal_text(
            selected.get("maximum_closed_trade_drawdown_pct", "0")
        ),
        "maximum_consecutive_losses": _count(
            selected.get("maximum_consecutive_losses", 0)
        ),
        "pair_breakdown": _pair_breakdown(
            selected.get("pair_breakdown", {})
        ),
    }


def sanitize_forex_status(value: object) -> dict[str, Any]:
    """Return the strict public PAPER status allowlist or fail closed."""

    if not isinstance(value, dict):
        raise ForexStatusStoreError("forex_status: invalid_payload")
    if int(value.get("schema_version", 0) or 0) != FOREX_STATUS_SCHEMA_VERSION:
        raise ForexStatusStoreError("forex_status: invalid_schema")
    if any(
        value.get(name) is not False
        for name in (
            "broker_orders_sent",
            "live_orders_sent",
            "real_money_access",
        )
    ):
        raise ForexStatusStoreError("forex_status: unsafe_mode")
    mode = _code(value.get("mode"), required=True)
    if "PAPER" not in mode:
        raise ForexStatusStoreError("forex_status: unsafe_mode")
    raw_blocks = value.get("observation_opening_blocks", [])
    if not isinstance(raw_blocks, list) or len(raw_blocks) > 12:
        raise ForexStatusStoreError("forex_status: invalid_opening_blocks")
    blocks = [_code(item, required=True) for item in raw_blocks]
    raw_positions = value.get("v3_open_positions", [])
    if not isinstance(raw_positions, list) or len(raw_positions) > 20:
        raise ForexStatusStoreError("forex_status: invalid_positions")
    return {
        "schema_version": FOREX_STATUS_SCHEMA_VERSION,
        "status": _code(value.get("status"), required=True),
        "mode": mode,
        "cycle_id": _cycle_id(value.get("cycle_id")),
        "observed_at": _timestamp(value.get("observed_at")),
        "reason": _code(value.get("reason", "")),
        "observation_status": _code(value.get("observation_status", "")),
        "observation_reason": _code(value.get("observation_reason", "")),
        "observation_fully_cross_checked": (
            value.get("observation_fully_cross_checked") is True
        ),
        "observation_positions_unchanged": (
            value.get("observation_positions_unchanged") is True
        ),
        "observation_opening_blocks": blocks,
        "calendar_source_state": _code(
            value.get("calendar_source_state", "")
        ),
        "nbp_source_state": _code(value.get("nbp_source_state", "")),
        "position_count": _count(value.get("position_count", 0)),
        "v3_status": _code(value.get("v3_status", "")),
        "v3_balance_pln": _decimal_text(value.get("v3_balance_pln", "0")),
        "v3_equity_pln": _decimal_text(value.get("v3_equity_pln", "0")),
        "v3_unrealized_pnl_pln": _decimal_text(
            value.get("v3_unrealized_pnl_pln", "0")
        ),
        "v3_realized_pnl_pln": _decimal_text(
            value.get("v3_realized_pnl_pln", "0")
        ),
        "v3_position_count": _count(value.get("v3_position_count", 0)),
        "v3_closed_trade_count": _count(
            value.get("v3_closed_trade_count", 0)
        ),
        "v3_winning_trade_count": _count(
            value.get("v3_winning_trade_count", 0)
        ),
        "v3_losing_trade_count": _count(
            value.get("v3_losing_trade_count", 0)
        ),
        "v3_breakeven_trade_count": _count(
            value.get("v3_breakeven_trade_count", 0)
        ),
        "v3_win_rate_pct": _decimal_text(
            value.get("v3_win_rate_pct", "0")
        ),
        "v3_open_positions": [_position(item) for item in raw_positions],
        "v3_performance": _performance(value.get("v3_performance", {})),
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def forex_status_view(
    value: object,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    snapshot = sanitize_forex_status(value)
    selected_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    observed = datetime.fromisoformat(snapshot["observed_at"])
    age_seconds = max(0, int((selected_now - observed).total_seconds()))
    return {
        **snapshot,
        "age_seconds": age_seconds,
        "fresh": age_seconds <= FOREX_STATUS_FRESH_SECONDS,
    }


class MemoryForexStatusStore:
    access_verified = True

    def __init__(self, value: object | None = None) -> None:
        self._value = (
            sanitize_forex_status(value) if value is not None else None
        )

    def read(self) -> dict[str, Any]:
        if self._value is None:
            raise ForexStatusNotReady("forex_status: not_ready")
        return deepcopy(self._value)

    def write(self, value: object) -> dict[str, Any]:
        self._value = sanitize_forex_status(value)
        return deepcopy(self._value)


class AzureBlobForexStatusStore:
    access_verified = False

    def __init__(self, blob_client: Any) -> None:
        self.blob = blob_client

    def read(self) -> dict[str, Any]:
        try:
            properties = self.blob.get_blob_properties()
            size = int(getattr(properties, "size", 0) or 0)
            if size <= 0 or size > FOREX_STATUS_MAX_BYTES:
                raise ForexStatusStoreError("forex_status: invalid_size")
            payload = self.blob.download_blob().readall()
        except ForexStatusStoreError:
            raise
        except Exception as error:
            if error.__class__.__name__ == "ResourceNotFoundError":
                raise ForexStatusNotReady("forex_status: not_ready") from error
            raise ForexStatusStoreError("forex_status: read_failed") from error
        if len(payload) != size or len(payload) > FOREX_STATUS_MAX_BYTES:
            raise ForexStatusStoreError("forex_status: invalid_size")
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ForexStatusStoreError("forex_status: invalid_json") from error
        self.access_verified = True
        return sanitize_forex_status(value)

    def write(self, value: object) -> dict[str, Any]:
        snapshot = sanitize_forex_status(value)
        payload = json.dumps(
            snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(payload) > FOREX_STATUS_MAX_BYTES:
            raise ForexStatusStoreError("forex_status: invalid_size")
        try:
            from azure.storage.blob import ContentSettings

            self.blob.upload_blob(
                payload,
                overwrite=True,
                content_settings=ContentSettings(
                    content_type="application/json; charset=utf-8",
                ),
            )
        except Exception as error:
            raise ForexStatusStoreError("forex_status: write_failed") from error
        self.access_verified = True
        return snapshot


def _validate_location(account: str, container: str, blob_name: str) -> None:
    if not _STORAGE_ACCOUNT.fullmatch(account):
        raise ForexStatusStoreError("forex_status: invalid_storage_account")
    if not _CONTAINER.fullmatch(container):
        raise ForexStatusStoreError("forex_status: invalid_container")
    if (
        not _BLOB.fullmatch(blob_name)
        or ".." in PurePosixPath(blob_name).parts
    ):
        raise ForexStatusStoreError("forex_status: invalid_blob_name")


def forex_status_store_from_environment() -> ForexStatusStore | None:
    container = os.getenv("JARVIS_OS_FOREX_STATUS_CONTAINER", "").strip().lower()
    if not container:
        return None
    account = os.getenv("JARVIS_OS_REMOTE_STORAGE_ACCOUNT", "").strip().lower()
    blob_name = os.getenv(
        "JARVIS_OS_FOREX_STATUS_BLOB", "status/latest.json"
    ).strip()
    _validate_location(account, container, blob_name)
    try:
        from azure.identity import ManagedIdentityCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError as error:
        raise ForexStatusStoreError("forex_status: azure_sdk_missing") from error
    service = BlobServiceClient(
        account_url=f"https://{account}.blob.core.windows.net",
        credential=ManagedIdentityCredential(),
    )
    return AzureBlobForexStatusStore(
        service.get_blob_client(container=container, blob=blob_name)
    )


__all__ = [
    "AzureBlobForexStatusStore",
    "FOREX_STATUS_SCHEMA_VERSION",
    "ForexStatusNotReady",
    "ForexStatusStore",
    "ForexStatusStoreError",
    "MemoryForexStatusStore",
    "forex_status_store_from_environment",
    "forex_status_view",
    "sanitize_forex_status",
]
