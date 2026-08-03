from __future__ import annotations

from typing import Any


class BusinessPlatformServiceMixin:
    """B81-B83 service methods split from the B80 compatibility core."""

    def business_platform_status(self) -> dict[str, Any]:
        response = self.status()
        response["status"] = "BUSINESS_PLATFORM_B81_B83_STATUS"
        response["stage"] = "B81-B83"
        response["decision"] = "READY" if response.get("success") else "REVIEW"
        return response

    def organization_profiles_status(self) -> dict[str, Any]:
        return self.organization_profiles.status()

    def snapshot_organization_profile(self) -> dict[str, Any]:
        return self.organization_profiles.snapshot_current()

    def export_organization_profile(self) -> dict[str, Any]:
        return self.organization_profiles.export_active()

    def license_platform_status(self) -> dict[str, Any]:
        response = self.license_details()
        response["status"] = "BUSINESS_LICENSE_PLATFORM_STATUS"
        response["stage"] = "B82"
        response["activation_request_directory"] = str(
            self.license_manager.request_dir
        )
        return response

    def start_license_trial(self) -> dict[str, Any]:
        status = self.license_manager.start_trial(self.config_store.ensure())
        return self._license_operation_response(
            "BUSINESS_LICENSE_TRIAL_STARTED",
            status,
        )

    def export_license_request(self) -> dict[str, Any]:
        result = self.license_manager.export_activation_request(
            self.config_store.ensure()
        )
        result.update({
            "operation": "business_license",
            "stage": "B82",
            "runtime": {
                "phase": "READY",
                "running": False,
                "paused": False,
                "cycles_completed": 1,
                "last_decision": "EXPORTED",
            },
            "decision": "EXPORTED",
            "reason": "Wniosek aktywacyjny zapisano lokalnie.",
            "report_path": result.get("export_path", ""),
            "errors": [],
        })
        return result

    def deactivate_business_license(self) -> dict[str, Any]:
        status = self.license_manager.deactivate(self.config_store.ensure())
        return self._license_operation_response(
            "BUSINESS_LICENSE_DEACTIVATED",
            status,
        )

    def access_control_status(self) -> dict[str, Any]:
        return self.access_control.status()

    def set_owner_role(self) -> dict[str, Any]:
        return self.access_control.set_active_role("OWNER")

    def set_admin_role(self) -> dict[str, Any]:
        return self.access_control.set_active_role("ADMIN")

    def set_operator_role(self) -> dict[str, Any]:
        return self.access_control.set_active_role("OPERATOR")

    def set_auditor_role(self) -> dict[str, Any]:
        return self.access_control.set_active_role("AUDITOR")

    def _license_operation_response(
        self,
        status_name: str,
        license_status: dict[str, Any],
    ) -> dict[str, Any]:
        active = bool(license_status.get("active"))
        return {
            "success": active,
            "status": status_name,
            "operation": "business_license",
            "stage": "B82",
            "runtime": {
                "phase": "READY" if active else "ATTENTION_REQUIRED",
                "running": False,
                "paused": False,
                "cycles_completed": 1,
                "last_decision": "ACTIVE" if active else "REVIEW",
            },
            "license": license_status,
            "decision": "ACTIVE" if active else "REVIEW",
            "reason": "Stan licencji został zaktualizowany.",
            "report_path": str(self.license_manager.path),
            "errors": [] if active else [str(license_status.get("status", "UNKNOWN"))],
        }

