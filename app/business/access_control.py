from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "OWNER": ("*",),
    "ADMIN": (
        "business.read",
        "business.configure",
        "profiles.manage",
        "autonomy.read",
        "autonomy.execute",
        "audit.read",
        "audit.export",
        "backup.manage",
        "updates.manage",
        "deployment.manage",
        "release.manage",
    ),
    "OPERATOR": (
        "business.read",
        "autonomy.read",
        "autonomy.execute",
    ),
    "AUDITOR": (
        "business.read",
        "autonomy.read",
        "audit.read",
    ),
    "VIEWER": (
        "business.read",
        "autonomy.read",
    ),
}


class BusinessAccessControl:
    """B83 local role policy with bounded authorization audit."""

    SENSITIVE_PHRASES = (
        "aktywuj licencję",
        "aktywuj licencje",
        "dezaktywuj licencję",
        "dezaktywuj licencje",
        "zmień rolę",
        "zmien role",
        "ustaw rolę",
        "ustaw role",
    )
    AUDIT_PHRASES = (
        "eksportuj raport audytu",
        "export audit report",
    )
    BACKUP_PHRASES = (
        "utwórz checkpoint", "utworz checkpoint",
        "przygotuj pakiet przywracania",
        "export restore package",
    )
    UPDATE_PHRASES = (
        "przygotuj aktualizację", "przygotuj aktualizacje",
        "eksportuj instalator aktualizacji",
        "stage business update", "export update installer",
    )
    DEPLOYMENT_PHRASES = (
        "inicjalizuj pierwsze uruchomienie",
        "eksportuj instalator business edition",
        "eksportuj bezpieczny deinstalator",
        "export business setup package",
        "export safe business uninstaller",
    )
    RELEASE_PHRASES = (
        "eksportuj release candidate",
        "eksportuj rc1",
        "export release candidate",
    )
    PROFILE_PHRASES = (
        "utwórz profil organizacji",
        "utworz profil organizacji",
        "aktywuj profil organizacji",
        "eksportuj profil organizacji",
        "importuj profil organizacji",
        "usuń profil organizacji",
        "usun profil organizacji",
    )

    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "access_control.json"
        self._store = JsonStore(self.path, self._default_payload)

    def ensure(self) -> dict[str, Any]:
        payload = self._normalize(self._store.load())
        self._store.save(payload)
        return payload

    def status(self) -> dict[str, Any]:
        payload = self.ensure()
        role = payload["active_role"]
        permissions = list(ROLE_PERMISSIONS.get(role, ()))
        return {
            "success": True,
            "status": "BUSINESS_ACCESS_CONTROL_STATUS",
            "operation": "business_access_control",
            "stage": "B83",
            "runtime": {
                "phase": "READY",
                "running": False,
                "paused": False,
                "cycles_completed": len(payload["audit"]),
                "last_decision": "READY",
            },
            "principal": payload["principal"],
            "active_role": role,
            "permissions": permissions,
            "available_roles": list(ROLE_PERMISSIONS),
            "audit_events": list(payload["audit"][-30:]),
            "decision": "READY",
            "reason": "Lokalne role i uprawnienia są aktywne.",
            "report_path": str(self.path),
            "errors": [],
        }

    def set_active_role(self, role: str) -> dict[str, Any]:
        normalized = str(role).strip().upper()
        if normalized not in ROLE_PERMISSIONS:
            return self._error("UNKNOWN_ROLE", "Nieznana rola.")
        payload = self.ensure()
        previous = payload["active_role"]
        payload["active_role"] = normalized
        self._append_audit(
            payload,
            action="ROLE_CHANGED",
            decision="ALLOW",
            detail=f"{previous}->{normalized}",
        )
        self._store.save(payload)
        response = self.status()
        response["status"] = "BUSINESS_ROLE_CHANGED"
        response["previous_role"] = previous
        response["decision"] = "CHANGED"
        return response

    def authorize(
        self,
        command: str,
        *,
        read_only: bool,
    ) -> dict[str, Any]:
        payload = self.ensure()
        role = payload["active_role"]
        normalized = " ".join(str(command).casefold().split())
        permission = self._required_permission(normalized, read_only)
        allowed = self._has_permission(role, permission)
        self._append_audit(
            payload,
            action="COMMAND_AUTHORIZATION",
            decision="ALLOW" if allowed else "DENY",
            detail=f"{permission}:{normalized[:120]}",
        )
        self._store.save(payload)
        return {
            "allowed": allowed,
            "role": role,
            "permission": permission,
            "reason": (
                "Rola ma wymagane uprawnienie."
                if allowed
                else f"Rola {role} nie ma uprawnienia {permission}."
            ),
        }

    def _required_permission(self, normalized: str, read_only: bool) -> str:
        if any(phrase in normalized for phrase in self.SENSITIVE_PHRASES):
            return "license.manage"
        if any(phrase in normalized for phrase in self.AUDIT_PHRASES):
            return "audit.export"
        if any(phrase in normalized for phrase in self.BACKUP_PHRASES):
            return "backup.manage"
        if any(phrase in normalized for phrase in self.UPDATE_PHRASES):
            return "updates.manage"
        if any(phrase in normalized for phrase in self.DEPLOYMENT_PHRASES):
            return "deployment.manage"
        if any(phrase in normalized for phrase in self.RELEASE_PHRASES):
            return "release.manage"
        if "audyt" in normalized and read_only:
            return "audit.read"
        if any(phrase in normalized for phrase in self.PROFILE_PHRASES):
            return "profiles.manage"
        if read_only:
            return "autonomy.read"
        return "autonomy.execute"

    @staticmethod
    def _has_permission(role: str, permission: str) -> bool:
        permissions = ROLE_PERMISSIONS.get(role, ())
        return "*" in permissions or permission in permissions

    def _default_payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "principal": "Kacper",
            "active_role": "OWNER",
            "audit": [],
        }

    def _normalize(self, payload: Any) -> dict[str, Any]:
        value = dict(payload or {}) if isinstance(payload, dict) else {}
        role = str(value.get("active_role", "OWNER")).upper()
        if role not in ROLE_PERMISSIONS:
            role = "OWNER"
        audit = value.get("audit", [])
        if not isinstance(audit, list):
            audit = []
        return {
            "schema_version": 1,
            "principal": " ".join(
                str(value.get("principal") or "Kacper").split()
            )[:80] or "Kacper",
            "active_role": role,
            "audit": [item for item in audit if isinstance(item, dict)][-200:],
        }

    def _append_audit(
        self,
        payload: dict[str, Any],
        *,
        action: str,
        decision: str,
        detail: str,
    ) -> None:
        payload["audit"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "decision": decision,
            "role": payload["active_role"],
            "detail": detail[:240],
        })
        payload["audit"] = payload["audit"][-200:]

    def _error(self, status: str, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "operation": "business_access_control",
            "stage": "B83",
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
