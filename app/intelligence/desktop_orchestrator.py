from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time
from typing import Any, Callable

from app.ai.actions import ActionTypes
from app.assistant.reliable_desktop import ReliableDesktopService
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.intelligence.vision_runtime import VisionRuntimeV3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DesktopAgentV2:
    """B103 transactional desktop wrapper with deduplication and verification."""

    NON_REPEATABLE = {ActionTypes.TYPE_TEXT, ActionTypes.CLICK, ActionTypes.VISION_CLICK}

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        vision: VisionRuntimeV3 | None = None,
        window_probe: Callable[[], list[str]] | None = None,
        duplicate_window_seconds: float = 4.0,
    ) -> None:
        root = resolve_project_root(project_root)
        self.vision = vision or VisionRuntimeV3(root)
        self.reliable = ReliableDesktopService(root, window_probe=window_probe)
        self.store = JsonStore(
            root / "data" / "intelligence" / "desktop2.json",
            self._default,
        )
        self.duplicate_window_seconds = max(0.1, float(duplicate_window_seconds))
        if not self.store.exists():
            self.store.save(self._default())

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "2.0",
            "transactions": [],
            "last_fingerprint": "",
            "last_started_monotonic": 0.0,
            "updated_at": "",
        }

    @staticmethod
    def supports(action: dict[str, Any]) -> bool:
        return ReliableDesktopService.supports(action)

    def execute_action(self, action: dict[str, Any], executor: Any) -> str:
        normalized = dict(action or {})
        fingerprint = self._fingerprint(normalized)
        data = self._load()
        now = time.monotonic()
        action_type = normalized.get("action_type")
        duplicate = (
            action_type in self.NON_REPEATABLE
            and fingerprint == data.get("last_fingerprint")
            and now - float(data.get("last_started_monotonic", 0.0) or 0.0)
            < self.duplicate_window_seconds
        )
        if duplicate:
            self._append_transaction(data, {
                "transaction_id": fingerprint,
                "action": normalized,
                "status": "BLOCKED_DUPLICATE",
                "result": "",
                "started_at": utc_now(),
                "finished_at": utc_now(),
            })
            return "B103: zablokowano szybkie powtórzenie nieodwracalnej akcji."

        transaction = {
            "transaction_id": f"desk-{int(time.time() * 1000)}-{fingerprint[:8]}",
            "action": normalized,
            "status": "RUNNING",
            "result": "",
            "rollback_hint": self._rollback_hint(normalized),
            "started_at": utc_now(),
            "finished_at": "",
        }
        data["last_fingerprint"] = fingerprint
        data["last_started_monotonic"] = now
        self._append_transaction(data, transaction)
        try:
            result = self.reliable.execute_action(normalized, executor)
            transaction["result"] = str(result)
            transaction["status"] = (
                "VERIFIED" if "potwierdzono" in str(result).casefold() else "COMPLETED_UNVERIFIED"
            )
        except Exception as error:
            transaction["status"] = "FAILED"
            transaction["result"] = f"{type(error).__name__}: {error}"
        transaction["finished_at"] = utc_now()
        data = self._load()
        transactions = list(data.get("transactions", []) or [])
        for index in range(len(transactions) - 1, -1, -1):
            if transactions[index].get("transaction_id") == transaction["transaction_id"]:
                transactions[index] = transaction
                break
        data["transactions"] = transactions[-500:]
        data["updated_at"] = utc_now()
        self.store.save(data)
        if transaction["status"] == "FAILED":
            return f"B103: akcja nie powiodła się: {transaction['result']}"
        return str(transaction["result"])

    def status(self) -> dict[str, Any]:
        transactions = list(self._load().get("transactions", []) or [])
        latest = dict(transactions[-1]) if transactions else {}
        return {
            "status": "DESKTOP_AGENT_2_READY",
            "transaction_count": len(transactions),
            "verified_count": sum(item.get("status") == "VERIFIED" for item in transactions),
            "unverified_count": sum(item.get("status") == "COMPLETED_UNVERIFIED" for item in transactions),
            "failure_count": sum(item.get("status") == "FAILED" for item in transactions),
            "duplicate_blocks": sum(item.get("status") == "BLOCKED_DUPLICATE" for item in transactions),
            "last_status": latest.get("status", ""),
            "last_action": dict(latest.get("action", {}) or {}).get("action_type", ""),
            "legacy_reliability": self.reliable.status(),
        }

    def _append_transaction(self, data: dict[str, Any], transaction: dict[str, Any]) -> None:
        transactions = list(data.get("transactions", []) or [])
        transactions.append(transaction)
        data["transactions"] = transactions[-500:]
        data["updated_at"] = utc_now()
        self.store.save(data)

    @staticmethod
    def _fingerprint(action: dict[str, Any]) -> str:
        fields = (
            action.get("action_type", ""), action.get("target", ""),
            action.get("text", ""), action.get("url", ""), action.get("query", ""),
            action.get("x", ""), action.get("y", ""),
        )
        return hashlib.sha256(repr(fields).encode("utf-8")).hexdigest()

    @staticmethod
    def _rollback_hint(action: dict[str, Any]) -> str:
        action_type = action.get("action_type")
        if action_type == ActionTypes.OPEN_APP:
            return "Zamknij aplikację tylko po osobnym potwierdzeniu."
        if action_type in DesktopAgentV2.NON_REPEATABLE:
            return "Brak automatycznego powtórzenia; wymagaj obserwacji użytkownika."
        return "Brak modyfikacji trwałych albo rollback nie jest wymagany."

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()
