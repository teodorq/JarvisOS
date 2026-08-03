from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


DEFAULT_BUSINESS_CONFIG: dict[str, Any] = {
    "schema_version": 2,
    "edition": "BUSINESS",
    "product_name": "JARVIS OS",
    "organization": "Kacper",
    "environment": "OWNER DEVELOPMENT",
    "accent_color": "#4DA3FF",
    "support_contact": "LOCAL OWNER",
    "license": {
        "mode": "OWNER_DEVELOPMENT",
        "product_code": "JARVIS-OS-BUSINESS",
    },
    "safety": {
        "auto_approve": False,
        "require_confirmation": True,
        "max_active_executions": 1,
        "allow_remote_code_execution": False,
    },
    "ui": {
        "start_page": "console",
        "show_quick_actions": True,
        "density": "comfortable",
    },
    "features": {
        "business_dashboard": True,
        "autonomy_control_center": True,
        "incident_response": True,
        "recovery_orchestration": True,
        "release_management": True,
        "security_audit": True,
        "disaster_recovery": True,
        "local_update_center": True,
        "production_24x7": True,
        "business_installer": True,
        "release_candidate": True,
        "commercial_platform": True,
        "production_release": True,
    },
}


class BusinessConfigStore:
    """Atomic, hardened configuration for the Business Edition shell."""

    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.root / "config" / "business_edition.json"
        self._store = JsonStore(self.path, self._default_payload)

    def load(self) -> dict[str, Any]:
        value = self._store.load()
        hardened = self._harden(value if isinstance(value, dict) else {})
        return hardened

    def ensure(self) -> dict[str, Any]:
        current = self.load()
        if not self.path.is_file() or self._store.load() != current:
            self._store.save(current)
        return current

    def reset(self) -> dict[str, Any]:
        value = self._harden(self._default_payload())
        self._store.save(value)
        return value

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        merged = self._deep_merge(current, dict(updates or {}))
        hardened = self._harden(merged)
        self._store.save(hardened)
        return hardened

    @staticmethod
    def _default_payload() -> dict[str, Any]:
        return deepcopy(DEFAULT_BUSINESS_CONFIG)

    @classmethod
    def _harden(cls, value: dict[str, Any]) -> dict[str, Any]:
        result = cls._deep_merge(cls._default_payload(), value)
        result["schema_version"] = 2
        result["edition"] = "BUSINESS"
        result["product_name"] = cls._text(
            result.get("product_name"), "JARVIS OS", 80
        )
        result["organization"] = cls._text(
            result.get("organization"), "Kacper", 80
        )
        result["environment"] = cls._text(
            result.get("environment"), "OWNER DEVELOPMENT", 60
        ).upper()
        result["support_contact"] = cls._text(
            result.get("support_contact"), "LOCAL OWNER", 120
        )
        accent = str(result.get("accent_color", "#4DA3FF")).strip().upper()
        result["accent_color"] = (
            accent if re.fullmatch(r"#[0-9A-F]{6}", accent) else "#4DA3FF"
        )

        license_config = dict(result.get("license", {}) or {})
        license_config["mode"] = cls._text(
            license_config.get("mode"), "OWNER_DEVELOPMENT", 40
        ).upper()
        license_config["product_code"] = "JARVIS-OS-BUSINESS"
        result["license"] = license_config

        safety = dict(result.get("safety", {}) or {})
        safety["auto_approve"] = False
        safety["require_confirmation"] = True
        safety["max_active_executions"] = 1
        safety["allow_remote_code_execution"] = False
        result["safety"] = safety

        ui = dict(result.get("ui", {}) or {})
        start_page = cls._text(ui.get("start_page"), "console", 20).lower()
        ui["start_page"] = (
            start_page if start_page in {"console", "settings", "trust", "platform", "operations", "release", "commercial"}
            else "console"
        )
        ui["show_quick_actions"] = bool(ui.get("show_quick_actions", True))
        ui["density"] = "comfortable"
        result["ui"] = ui

        defaults = DEFAULT_BUSINESS_CONFIG["features"]
        features = dict(result.get("features", {}) or {})
        result["features"] = {
            key: bool(features.get(key, enabled))
            for key, enabled in defaults.items()
        }
        return result

    @staticmethod
    def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = BusinessConfigStore._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    @staticmethod
    def _text(value: Any, default: str, limit: int) -> str:
        text = " ".join(str(value or default).split())
        return text[:limit] or default
