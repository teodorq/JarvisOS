from __future__ import annotations

from typing import Any


class BusinessOperationsServiceMixin:
    """B84-B86 audit, disaster recovery and update operations."""

    def business_operations_status(self) -> dict[str, Any]:
        audit = self.audit_center_status()
        recovery = self.disaster_recovery.status()
        updates = self.update_center.status()
        ready = all(item.get("success", False) for item in (audit, recovery, updates))
        return {
            "success": ready,
            "status": "BUSINESS_OPERATIONS_B84_B86_STATUS",
            "operation": "business_operations",
            "stage": "B84-B86",
            "runtime": {
                "phase": "READY" if ready else "ATTENTION_REQUIRED",
                "running": False,
                "paused": False,
                "cycles_completed": (
                    int(audit.get("event_count", 0))
                    + int(recovery.get("checkpoint_count", 0))
                    + len(updates.get("history", []))
                ),
                "last_decision": "READY" if ready else "REVIEW",
            },
            "audit": audit,
            "disaster_recovery": recovery,
            "updates": updates,
            "decision": "READY" if ready else "REVIEW",
            "reason": "Audyt, checkpointy i aktualizacje lokalne są dostępne.",
            "report_path": str(self.audit_center.path),
            "errors": [],
        }

    def audit_center_status(self) -> dict[str, Any]:
        access = self.access_control.status()
        return self.audit_center.sync_access_events(access)

    def export_audit_report(self) -> dict[str, Any]:
        self.audit_center.sync_access_events(self.access_control.status())
        result = self.audit_center.export_report()
        self._audit_operation("AUDIT_REPORT_EXPORTED", result)
        return result

    def disaster_recovery_status(self) -> dict[str, Any]:
        return self.disaster_recovery.status()

    def create_business_checkpoint(self) -> dict[str, Any]:
        result = self.disaster_recovery.create_checkpoint()
        self._audit_operation("CHECKPOINT_CREATED", result)
        return result

    def verify_business_checkpoint(self) -> dict[str, Any]:
        result = self.disaster_recovery.verify_latest()
        self._audit_operation("CHECKPOINT_VERIFIED", result)
        return result

    def export_restore_package(self) -> dict[str, Any]:
        result = self.disaster_recovery.export_restore_package()
        self._audit_operation("RESTORE_PACKAGE_EXPORTED", result)
        return result

    def update_center_status(self) -> dict[str, Any]:
        return self.update_center.status()

    def scan_business_updates(self) -> dict[str, Any]:
        result = self.update_center.scan()
        self._audit_operation("UPDATE_SCAN", result)
        return result

    def stage_business_update(self) -> dict[str, Any]:
        result = self.update_center.stage_latest()
        self._audit_operation("UPDATE_STAGED", result)
        return result

    def export_update_installer(self) -> dict[str, Any]:
        result = self.update_center.export_installer()
        self._audit_operation("UPDATE_INSTALLER_EXPORTED", result)
        return result

    def _audit_operation(self, action: str, result: dict[str, Any]) -> None:
        self.audit_center.record(
            action,
            category=str(result.get("stage", "BUSINESS")),
            decision=str(result.get("decision", "OBSERVE")),
            detail=str(result.get("reason", "")),
            metadata={"status": result.get("status")},
        )
