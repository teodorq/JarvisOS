from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
import uuid

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .business_config import BusinessConfigStore


class OrganizationProfileStore:
    """B81 persistent organization profiles with atomic import/export."""

    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "organization_profiles.json"
        self.export_dir = self.paths.data / "business" / "profile_exports"
        self.config_store = BusinessConfigStore(self.paths.root)
        self._store = JsonStore(self.path, self._default_payload)

    def ensure(self) -> dict[str, Any]:
        payload = self._normalize(self._store.load())
        if not payload["profiles"]:
            config = self.config_store.ensure()
            profile = self._profile_from_config(config, "Profil główny")
            payload["profiles"][profile["profile_id"]] = profile
            payload["active_profile_id"] = profile["profile_id"]
        self._store.save(payload)
        return payload

    def status(self) -> dict[str, Any]:
        payload = self.ensure()
        active_id = str(payload.get("active_profile_id", ""))
        profiles = list(payload["profiles"].values())
        return {
            "success": True,
            "status": "ORGANIZATION_PROFILES_STATUS",
            "operation": "organization_profiles",
            "stage": "B81",
            "runtime": {
                "phase": "READY",
                "running": False,
                "paused": False,
                "cycles_completed": len(profiles),
                "last_decision": "READY",
            },
            "active_profile_id": active_id,
            "profiles": profiles,
            "profile_count": len(profiles),
            "export_directory": str(self.export_dir),
            "decision": "READY",
            "reason": "Profile organizacji są zapisane lokalnie i atomowo.",
            "report_path": str(self.path),
            "errors": [],
        }

    def snapshot_current(self, name: str | None = None) -> dict[str, Any]:
        payload = self.ensure()
        config = self.config_store.ensure()
        profile = self._profile_from_config(
            config,
            name or f"Snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )
        payload["profiles"][profile["profile_id"]] = profile
        payload["active_profile_id"] = profile["profile_id"]
        self._store.save(payload)
        response = self.status()
        response["status"] = "ORGANIZATION_PROFILE_SNAPSHOT_CREATED"
        response["profile"] = profile
        response["decision"] = "CREATED"
        return response

    def activate(self, profile_id: str) -> dict[str, Any]:
        payload = self.ensure()
        profile = payload["profiles"].get(str(profile_id))
        if not isinstance(profile, dict):
            return self._error("PROFILE_NOT_FOUND", "Nie znaleziono profilu.")
        self.config_store.update(deepcopy(profile["configuration"]))
        payload["active_profile_id"] = str(profile_id)
        payload["profiles"][str(profile_id)]["last_activated_at"] = self._now()
        self._store.save(payload)
        response = self.status()
        response["status"] = "ORGANIZATION_PROFILE_ACTIVATED"
        response["profile"] = profile
        response["decision"] = "ACTIVATED"
        return response

    def export_active(self) -> dict[str, Any]:
        payload = self.ensure()
        active_id = str(payload.get("active_profile_id", ""))
        profile = payload["profiles"].get(active_id)
        if not isinstance(profile, dict):
            return self._error("NO_ACTIVE_PROFILE", "Brak aktywnego profilu.")
        self.export_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(profile["name"])).strip("_")
        target = self.export_dir / f"{safe_name or 'profile'}_{active_id[:8]}.json"
        package = {
            "schema_version": 1,
            "type": "JARVIS_BUSINESS_ORGANIZATION_PROFILE",
            "exported_at": self._now(),
            "profile": profile,
        }
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(package, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        response = self.status()
        response["status"] = "ORGANIZATION_PROFILE_EXPORTED"
        response["export_path"] = str(target)
        response["decision"] = "EXPORTED"
        return response

    def import_package(self, value: str | dict[str, Any]) -> dict[str, Any]:
        try:
            package = json.loads(value) if isinstance(value, str) else dict(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return self._error("INVALID_PROFILE_PACKAGE", "Nieprawidłowy pakiet profilu.")
        profile = package.get("profile")
        if not isinstance(profile, dict):
            return self._error("INVALID_PROFILE_PACKAGE", "Pakiet nie zawiera profilu.")
        normalized = self._normalize_profile(profile)
        normalized["profile_id"] = uuid.uuid4().hex
        normalized["imported_at"] = self._now()
        payload = self.ensure()
        payload["profiles"][normalized["profile_id"]] = normalized
        self._store.save(payload)
        response = self.status()
        response["status"] = "ORGANIZATION_PROFILE_IMPORTED"
        response["profile"] = normalized
        response["decision"] = "IMPORTED"
        return response

    def remove(self, profile_id: str) -> dict[str, Any]:
        payload = self.ensure()
        profile_id = str(profile_id)
        if profile_id == payload.get("active_profile_id"):
            return self._error(
                "ACTIVE_PROFILE_PROTECTED",
                "Aktywnego profilu nie można usunąć.",
            )
        if profile_id not in payload["profiles"]:
            return self._error("PROFILE_NOT_FOUND", "Nie znaleziono profilu.")
        payload["profiles"].pop(profile_id, None)
        self._store.save(payload)
        response = self.status()
        response["status"] = "ORGANIZATION_PROFILE_REMOVED"
        response["decision"] = "REMOVED"
        return response

    def _default_payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "active_profile_id": "",
            "profiles": {},
        }

    def _normalize(self, payload: Any) -> dict[str, Any]:
        value = dict(payload or {}) if isinstance(payload, dict) else {}
        profiles_raw = value.get("profiles", {})
        profiles: dict[str, dict[str, Any]] = {}
        if isinstance(profiles_raw, dict):
            for key, item in profiles_raw.items():
                if isinstance(item, dict):
                    profile = self._normalize_profile(item)
                    profile["profile_id"] = str(key)
                    profiles[str(key)] = profile
        active = str(value.get("active_profile_id", ""))
        if active not in profiles:
            active = next(iter(profiles), "")
        return {
            "schema_version": 1,
            "active_profile_id": active,
            "profiles": profiles,
        }

    def _profile_from_config(
        self,
        config: dict[str, Any],
        name: str,
    ) -> dict[str, Any]:
        return self._normalize_profile({
            "profile_id": uuid.uuid4().hex,
            "name": name,
            "created_at": self._now(),
            "last_activated_at": None,
            "configuration": {
                "product_name": config.get("product_name"),
                "organization": config.get("organization"),
                "environment": config.get("environment"),
                "support_contact": config.get("support_contact"),
                "accent_color": config.get("accent_color"),
                "ui": deepcopy(config.get("ui", {})),
            },
        })

    def _normalize_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        configuration = dict(profile.get("configuration", {}) or {})
        return {
            "profile_id": str(profile.get("profile_id") or uuid.uuid4().hex),
            "name": self._text(profile.get("name"), "Profil organizacji", 80),
            "created_at": str(profile.get("created_at") or self._now()),
            "last_activated_at": profile.get("last_activated_at"),
            "imported_at": profile.get("imported_at"),
            "configuration": {
                "product_name": self._text(
                    configuration.get("product_name"),
                    "JARVIS OS",
                    80,
                ),
                "organization": self._text(
                    configuration.get("organization"),
                    "Kacper",
                    80,
                ),
                "environment": self._text(
                    configuration.get("environment"),
                    "OWNER DEVELOPMENT",
                    60,
                ).upper(),
                "support_contact": self._text(
                    configuration.get("support_contact"),
                    "LOCAL OWNER",
                    120,
                ),
                "accent_color": self._accent(configuration.get("accent_color")),
                "ui": dict(configuration.get("ui", {}) or {}),
            },
        }

    def _error(self, status: str, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "operation": "organization_profiles",
            "stage": "B81",
            "runtime": {
                "phase": "ATTENTION_REQUIRED",
                "running": False,
                "paused": False,
                "cycles_completed": 0,
                "last_decision": "REJECT",
            },
            "decision": "REJECT",
            "reason": message,
            "report_path": str(self.path),
            "errors": [message],
        }

    @staticmethod
    def _text(value: Any, default: str, limit: int) -> str:
        text = " ".join(str(value or default).split())
        return text[:limit] or default

    @staticmethod
    def _accent(value: Any) -> str:
        text = str(value or "#4DA3FF").upper()
        return text if re.fullmatch(r"#[0-9A-F]{6}", text) else "#4DA3FF"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
