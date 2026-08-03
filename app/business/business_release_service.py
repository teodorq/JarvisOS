from __future__ import annotations

from typing import Any


class BusinessReleaseServiceMixin:
    """B87-B88 installation and Release Candidate service facade."""

    def business_release_status(self) -> dict[str, Any]:
        installation = self.installation_manager.status()
        release = self.release_candidate.status()
        return {
            "success": True,
            "status": "BUSINESS_RELEASE_B87_B88_STATUS",
            "operation": "business_release",
            "stage": "B87-B88",
            "runtime": {
                "phase": "READY" if release.get("release_ready") else "ATTENTION_REQUIRED",
                "running": False,
                "paused": False,
                "cycles_completed": (
                    int(installation.get("runtime", {}).get("cycles_completed", 0))
                    + int(release.get("runtime", {}).get("cycles_completed", 0))
                ),
                "last_decision": release.get("decision", "GATES_PENDING"),
            },
            "installation": installation,
            "release_candidate": release,
            "decision": release.get("decision", "GATES_PENDING"),
            "reason": "Instalator B87 i bramki Release Candidate B88 są dostępne.",
            "report_path": str(self.release_candidate.path),
            "errors": list(release.get("errors", [])),
        }

    def installation_manager_status(self) -> dict[str, Any]:
        return self.installation_manager.status()

    def initialize_business_first_run(self) -> dict[str, Any]:
        result = self.installation_manager.initialize_first_run()
        self._audit_operation("FIRST_RUN_INITIALIZED", result)
        return result

    def export_business_setup_package(self) -> dict[str, Any]:
        result = self.installation_manager.export_setup_package()
        self._audit_operation("SETUP_PACKAGE_EXPORTED", result)
        return result

    def export_business_uninstaller(self) -> dict[str, Any]:
        result = self.installation_manager.export_uninstaller()
        self._audit_operation("UNINSTALLER_EXPORTED", result)
        return result

    def release_candidate_status(self) -> dict[str, Any]:
        return self.release_candidate.status()

    def export_business_release_candidate(self) -> dict[str, Any]:
        result = self.release_candidate.export_release_candidate()
        self._audit_operation("RELEASE_CANDIDATE_EXPORTED", result)
        return result

    def verify_business_release_candidate(self) -> dict[str, Any]:
        return self.release_candidate.verify_release_candidate()
