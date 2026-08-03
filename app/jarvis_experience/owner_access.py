from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import re
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OwnerAccessGate:
    """Local PIN gate for the hidden owner-mode entry point."""

    ITERATIONS = 210_000
    MAX_FAILURES = 3
    LOCK_SECONDS = 60

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "client_experience" / "owner_access.json",
            self._default,
        )
        if not self.store.exists():
            self.store.save(self._default())

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "pin_hash": "",
            "salt": "",
            "failed_attempts": 0,
            "locked_until": "",
        }

    def has_pin(self) -> bool:
        state = self._load()
        return bool(state.get("pin_hash") and state.get("salt"))

    def set_pin(self, pin: object) -> None:
        value = self._validate_pin(pin)
        salt = os.urandom(16)
        state = self._default()
        state.update({
            "pin_hash": self._derive(value, salt).hex(),
            "salt": salt.hex(),
        })
        self.store.save(state)

    def verify(self, pin: object) -> tuple[bool, str]:
        state = self._load()
        if not self.has_pin():
            return False, "PIN właściciela nie został jeszcze ustawiony."
        locked_until = self._parse_time(state.get("locked_until", ""))
        if locked_until and _utc_now() < locked_until:
            seconds = max(1, int((locked_until - _utc_now()).total_seconds()))
            return False, f"Dostęp chwilowo zablokowany. Spróbuj za {seconds} s."
        try:
            value = self._validate_pin(pin)
        except ValueError:
            return self._failure(state)
        salt = bytes.fromhex(str(state.get("salt", "")))
        expected = bytes.fromhex(str(state.get("pin_hash", "")))
        if hmac.compare_digest(self._derive(value, salt), expected):
            state.update({"failed_attempts": 0, "locked_until": ""})
            self.store.save(state)
            return True, "Dostęp właściciela odblokowany."
        return self._failure(state)

    def _failure(self, state: dict[str, Any]) -> tuple[bool, str]:
        attempts = int(state.get("failed_attempts", 0) or 0) + 1
        state["failed_attempts"] = attempts
        if attempts >= self.MAX_FAILURES:
            state["failed_attempts"] = 0
            state["locked_until"] = (
                _utc_now() + timedelta(seconds=self.LOCK_SECONDS)
            ).isoformat()
            message = "Nieprawidłowy PIN. Dostęp zablokowany na minutę."
        else:
            message = "Nieprawidłowy PIN właściciela."
        self.store.save(state)
        return False, message

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

    @classmethod
    def _derive(cls, pin: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", pin.encode("utf-8"), salt, cls.ITERATIONS
        )

    @staticmethod
    def _validate_pin(pin: object) -> str:
        value = str(pin or "").strip()
        if not re.fullmatch(r"\d{4,12}", value):
            raise ValueError("PIN musi zawierać od 4 do 12 cyfr.")
        return value

    @staticmethod
    def _parse_time(value: object) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value or ""))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
