from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from typing import Any
import uuid

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .business_license_activation import BusinessLicenseActivationMixin


class BusinessLicenseManager(BusinessLicenseActivationMixin):
    """B80-compatible validation core extended by B82 activation operations."""

    PRODUCT_CODE = "JARVIS-OS-BUSINESS"
    OFFLINE_SALT = "JARVIS-B82-OFFLINE-ACTIVATION-V1"

    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "business_license.json"
        self.request_dir = self.paths.data / "business" / "license_requests"
        self._store = JsonStore(self.path, dict)

    def status(self, config: dict[str, Any]) -> dict[str, Any]:
        mode = str(
            dict(config.get("license", {}) or {}).get(
                "mode", "OWNER_DEVELOPMENT"
            )
        ).upper()
        if not self.path.is_file():
            return (
                self._owner_status(config)
                if mode == "OWNER_DEVELOPMENT"
                else self._inactive("MISSING", config)
            )
        payload = self._store.load()
        if not isinstance(payload, dict) or not payload:
            return self._inactive("MISSING", config)
        return self._validate(payload, config)

    def save_license(self, payload: dict[str, Any]) -> dict[str, Any]:
        value = dict(payload or {})
        value["integrity_checksum"] = self._checksum(value)
        self._store.save(value)
        return value

    def _validate(
        self,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        if str(payload.get("product_code", "")) != self.PRODUCT_CODE:
            return self._inactive("WRONG_PRODUCT", config)
        checksum = str(payload.get("integrity_checksum", ""))
        if not checksum or checksum != self._checksum(payload):
            return self._inactive("INTEGRITY_FAILED", config)
        fingerprint = str(payload.get("machine_fingerprint", ""))
        if fingerprint and fingerprint != self.machine_fingerprint():
            return self._inactive("MACHINE_MISMATCH", config)

        expires_at = str(payload.get("expires_at", "")).strip()
        if expires_at:
            try:
                expiration = datetime.fromisoformat(
                    expires_at.replace("Z", "+00:00")
                )
                if expiration.tzinfo is None:
                    expiration = expiration.replace(tzinfo=timezone.utc)
                if expiration < datetime.now(timezone.utc):
                    return self._inactive("EXPIRED", config)
            except ValueError:
                return self._inactive("INVALID_EXPIRY", config)

        mode = str(payload.get("mode", "COMMERCIAL")).upper()
        return {
            "active": True,
            "status": "TRIAL_ACTIVE" if mode == "TRIAL" else "ACTIVE",
            "mode": mode,
            "license_id": str(payload.get("license_id", "")),
            "organization": str(payload.get("organization", "")),
            "expires_at": expires_at or None,
            "machine_fingerprint": self.machine_fingerprint(),
            "commercial_activation": mode not in {
                "TRIAL", "OWNER_DEVELOPMENT"
            },
            "activation_source": payload.get("activation_source"),
        }

    def _owner_status(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "active": True,
            "status": "OWNER_DEVELOPMENT",
            "mode": "OWNER_DEVELOPMENT",
            "license_id": "OWNER-LOCAL-B82",
            "organization": str(config.get("organization", "Kacper")),
            "expires_at": None,
            "machine_fingerprint": self.machine_fingerprint(),
            "commercial_activation": False,
            "activation_source": "OWNER_MODE",
        }

    def _inactive(self, status: str, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "active": False,
            "status": status,
            "mode": str(
                dict(config.get("license", {}) or {}).get(
                    "mode", "UNLICENSED"
                )
            ).upper(),
            "license_id": "",
            "organization": str(config.get("organization", "")),
            "expires_at": None,
            "machine_fingerprint": self.machine_fingerprint(),
            "commercial_activation": False,
            "activation_source": None,
        }

    @staticmethod
    def machine_fingerprint() -> str:
        source = f"{platform.node()}|{uuid.getnode()}|JARVIS-OS-BUSINESS"
        return BusinessLicenseManager._sha256(source)[:16].upper()

    @staticmethod
    def _checksum(payload: dict[str, Any]) -> str:
        value = {
            key: item
            for key, item in payload.items()
            if key != "integrity_checksum"
        }
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return BusinessLicenseManager._sha256(encoded)

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
