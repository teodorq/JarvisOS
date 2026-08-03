from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import safe_error, utc_now


class WorkspaceReliabilityService:
    """B131 bounded retry, cached reads and persistent Google Workspace health."""

    RETRY_MARKERS = (
        "timeout", "timed out", "connection", "temporarily", "unavailable",
        "429", "500", "502", "503", "504", "reset by peer",
    )

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        provider: Any,
        sleep: Callable[[float], None] = time.sleep,
        max_read_attempts: int = 3,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider
        self.sleep = sleep
        self.max_read_attempts = max(1, min(int(max_read_attempts), 3))
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant_v13" / "reliability.json",
            lambda: {
                "operations": [], "cache": {}, "last_probe": {},
                "offline_mode": False, "updated_at": "",
            },
        )

    def read(self, key: str, action: Callable[[], Any]) -> dict[str, Any]:
        """Retry safe reads and return the last bounded cache when offline."""
        attempts = 0
        last_error = ""
        last_retryable = False
        for attempts in range(1, self.max_read_attempts + 1):
            try:
                value = action()
                self._cache(key, value)
                self._record(key, "LIVE", attempts=attempts)
                return {"mode": "LIVE", "value": value, "attempts": attempts, "error": ""}
            except Exception as error:
                last_error = safe_error(error)
                retryable = self._retryable(last_error)
                last_retryable = retryable
                self._record(key, "RETRY" if retryable else "FAILED", attempts=attempts, error=last_error)
                if not retryable or attempts >= self.max_read_attempts:
                    break
                self.sleep(min(0.2 * (2 ** (attempts - 1)), 0.8))
        cached = self._cached(key) if last_retryable else None
        if cached is not None:
            self._set_offline(True)
            self._record(key, "CACHED_OFFLINE", attempts=attempts, error=last_error)
            return {"mode": "CACHED_OFFLINE", "value": cached, "attempts": attempts, "error": last_error}
        raise RuntimeError(last_error or "Google Workspace read failed")

    def write(self, key: str, action: Callable[[], Any]) -> Any:
        """Never retry writes automatically because their remote result may be unknown."""
        try:
            value = action()
            self._record(key, "WRITE_OK", attempts=1)
            return value
        except Exception as error:
            message = safe_error(error)
            self._record(key, "WRITE_FAILED", attempts=1, error=message)
            raise RuntimeError(message) from None

    def probe(self) -> dict[str, Any]:
        connection = dict(self.provider.connection_status() or {})
        if not (
            connection.get("dependency_ready")
            and connection.get("client_configured")
            and connection.get("token_present")
        ):
            result = {
                "status": "NOT_CONNECTED", "gmail": False,
                "calendar": False, "drive": False, "mode": "LOCAL",
                "checked_at": utc_now(),
            }
            self._save_probe(result, offline=False)
            return result
        try:
            read = self.read("workspace_probe", self.provider.live_probe)
            probes = dict(read["value"] or {})
            result = {
                "status": "HEALTHY" if all(probes.get(name) for name in ("gmail", "calendar", "drive")) else "DEGRADED",
                "gmail": bool(probes.get("gmail")),
                "calendar": bool(probes.get("calendar")),
                "drive": bool(probes.get("drive")),
                "mode": read["mode"],
                "checked_at": utc_now(),
            }
            self._save_probe(result, offline=read["mode"] != "LIVE")
            return result
        except Exception as error:
            result = {
                "status": "OFFLINE", "gmail": False, "calendar": False,
                "drive": False, "mode": "OFFLINE", "error": safe_error(error),
                "checked_at": utc_now(),
            }
            self._save_probe(result, offline=True)
            return result

    def status(self) -> dict[str, Any]:
        data = self._load()
        operations = list(data.get("operations", []) or [])
        return {
            "status": "WORKSPACE_RELIABILITY_READY",
            "last_probe": dict(data.get("last_probe", {}) or {}),
            "offline_mode": bool(data.get("offline_mode", False)),
            "operation_count": len(operations),
            "last_operation": dict(operations[-1]) if operations else {},
            "max_read_attempts": self.max_read_attempts,
            "write_retry_enabled": False,
            "cache_entries": len(dict(data.get("cache", {}) or {})),
        }

    @classmethod
    def _retryable(cls, message: str) -> bool:
        value = str(message).casefold()
        return any(marker in value for marker in cls.RETRY_MARKERS)

    def _cache(self, key: str, value: Any) -> None:
        data = self._load()
        cache = dict(data.get("cache", {}) or {})
        cache[str(key)] = {"value": value, "saved_at": utc_now()}
        data.update({"cache": cache, "offline_mode": False, "updated_at": utc_now()})
        self.store.save(data)

    def _cached(self, key: str) -> Any | None:
        entry = dict(self._load().get("cache", {}).get(str(key), {}) or {})
        return entry.get("value") if "value" in entry else None

    def _record(self, key: str, result: str, *, attempts: int, error: str = "") -> None:
        data = self._load()
        operations = list(data.get("operations", []) or [])
        operations.append({
            "key": str(key), "result": str(result), "attempts": int(attempts),
            "error": safe_error(RuntimeError(error)) if error else "", "created_at": utc_now(),
        })
        data.update({"operations": operations[-250:], "updated_at": utc_now()})
        self.store.save(data)

    def _save_probe(self, probe: dict[str, Any], *, offline: bool) -> None:
        data = self._load()
        data.update({"last_probe": probe, "offline_mode": bool(offline), "updated_at": utc_now()})
        self.store.save(data)

    def _set_offline(self, value: bool) -> None:
        data = self._load()
        data.update({"offline_mode": bool(value), "updated_at": utc_now()})
        self.store.save(data)

    def _load(self) -> dict[str, Any]:
        data = self.store.load()
        return data if isinstance(data, dict) else {
            "operations": [], "cache": {}, "last_probe": {},
            "offline_mode": False, "updated_at": "",
        }
