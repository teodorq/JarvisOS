from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any
import uuid


class BusinessLicenseActivationMixin:
    """B82 activation operations split from the validation core."""

    def start_trial(
        self,
        config: dict[str, Any],
        *,
        days: int = 14,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        payload = {
            "schema_version": 1,
            "mode": "TRIAL",
            "product_code": self.PRODUCT_CODE,
            "license_id": f"TRIAL-{uuid.uuid4().hex[:12].upper()}",
            "organization": str(config.get("organization", "")),
            "machine_fingerprint": self.machine_fingerprint(),
            "created_at": now.isoformat(),
            "expires_at": (
                now + timedelta(days=max(1, min(int(days), 30)))
            ).isoformat(),
            "activation_source": "LOCAL_TRIAL",
        }
        self.save_license(payload)
        return self.status(config)

    def activate_offline(
        self,
        package: str | dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            payload = (
                json.loads(package)
                if isinstance(package, str)
                else dict(package)
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return self._inactive("INVALID_PACKAGE", config)
        required = {
            "product_code",
            "license_id",
            "organization",
            "machine_fingerprint",
            "activation_code",
        }
        if not required.issubset(payload):
            return self._inactive("INVALID_PACKAGE", config)
        if str(payload.get("product_code")) != self.PRODUCT_CODE:
            return self._inactive("WRONG_PRODUCT", config)
        if str(payload.get("machine_fingerprint")) != self.machine_fingerprint():
            return self._inactive("MACHINE_MISMATCH", config)
        if str(payload.get("activation_code", "")).upper() != self.activation_code(payload):
            return self._inactive("ACTIVATION_PROOF_FAILED", config)
        payload["mode"] = "OFFLINE_ACTIVE"
        payload["activation_source"] = "OFFLINE_PACKAGE"
        payload["activated_at"] = datetime.now(timezone.utc).isoformat()
        self.save_license(payload)
        return self.status(config)

    def deactivate(self, config: dict[str, Any]) -> dict[str, Any]:
        if self.path.exists():
            self.path.unlink()
        return self.status(config)

    def export_activation_request(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        self.request_dir.mkdir(parents=True, exist_ok=True)
        fingerprint = self.machine_fingerprint()
        payload = {
            "schema_version": 1,
            "type": "JARVIS_BUSINESS_ACTIVATION_REQUEST",
            "product_code": self.PRODUCT_CODE,
            "organization": str(config.get("organization", "")),
            "machine_fingerprint": fingerprint,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        target = self.request_dir / f"activation_request_{fingerprint}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        return {
            "success": True,
            "status": "BUSINESS_LICENSE_REQUEST_EXPORTED",
            "stage": "B82",
            "request": payload,
            "export_path": str(target),
        }

    @classmethod
    def activation_code(cls, payload: dict[str, Any]) -> str:
        material = "|".join((
            str(payload.get("product_code", "")),
            str(payload.get("license_id", "")),
            str(payload.get("organization", "")),
            str(payload.get("machine_fingerprint", "")),
            str(payload.get("expires_at", "")),
            cls.OFFLINE_SALT,
        ))
        return cls._sha256(material)[:32].upper()
