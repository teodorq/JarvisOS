from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from app.core.project_paths import ProjectPaths
from .access_control import BusinessAccessControl
from .business_config import BusinessConfigStore
from .business_license import BusinessLicenseManager
from .organization_profiles import OrganizationProfileStore
from .business_platform_service import BusinessPlatformServiceMixin
from .business_operations_service import BusinessOperationsServiceMixin
from .business_release_service import BusinessReleaseServiceMixin
from .business_commercial_service import BusinessCommercialServiceMixin
from .production_versioning import ProductionVersioning
from .customer_update_channels import CustomerUpdateChannels
from .commercial_license import CommercialLicenseAuthority
from .distribution_protection import DistributionProtection
from .customer_deployment import CustomerDeployment
from .sales_readiness import SalesReadiness
from .production_release import ProductionRelease
from .audit_center import BusinessAuditCenter
from .disaster_recovery import BusinessDisasterRecovery
from .update_center import BusinessUpdateCenter
from .installation_manager import BusinessInstallationManager
from .release_candidate import BusinessReleaseCandidate
class BusinessEditionService(
    BusinessPlatformServiceMixin,
    BusinessOperationsServiceMixin,
    BusinessReleaseServiceMixin,
    BusinessCommercialServiceMixin,
):
    """B80 Business Edition status, safety and integrity foundation."""
    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.config_store = BusinessConfigStore(self.paths.root)
        self.license_manager = BusinessLicenseManager(self.paths.root)
        self.organization_profiles = OrganizationProfileStore(self.paths.root)
        self.access_control = BusinessAccessControl(self.paths.root)
        self.audit_center = BusinessAuditCenter(self.paths.root)
        self.disaster_recovery = BusinessDisasterRecovery(self.paths.root)
        self.update_center = BusinessUpdateCenter(self.paths.root)
        self.installation_manager = BusinessInstallationManager(self.paths.root)
        self.release_candidate = BusinessReleaseCandidate(self.paths.root, installation_manager=self.installation_manager, disaster_recovery=self.disaster_recovery, audit_center=self.audit_center, update_center=self.update_center)
        self.production_versioning = ProductionVersioning(self.paths.root)
        self.customer_update_channels = CustomerUpdateChannels(self.paths.root)
        self.commercial_license_authority = CommercialLicenseAuthority(self.paths.root)
        self.distribution_protection = DistributionProtection(self.paths.root)
        self.customer_deployment = CustomerDeployment(self.paths.root, self.installation_manager, self.distribution_protection, self.commercial_license_authority)
        self.sales_readiness = SalesReadiness(self.paths.root, self.customer_deployment)
        self.production_release = ProductionRelease(self.paths.root, versioning=self.production_versioning, updates=self.customer_update_channels, licensing=self.commercial_license_authority, distribution=self.distribution_protection, deployment=self.customer_deployment, sales=self.sales_readiness, release_candidate=self.release_candidate)
        self.manifest_path = self.paths.root / "config" / "business_integrity_manifest.json"
    def status(self) -> dict[str, Any]:
        config = self.config_store.ensure()
        license_status = self.license_manager.status(config)
        integrity = self.verify_integrity()
        ready = bool(license_status.get("active")) and integrity["status"] in {
            "VERIFIED",
            "BASELINE_PENDING",
        }
        return {
            "success": ready,
            "status": "BUSINESS_EDITION_STATUS",
            "operation": "business_edition",
            "stage": "B80",
            "runtime": {
                "phase": "READY" if ready else "ATTENTION_REQUIRED",
                "running": False,
                "paused": False,
                "cycles_completed": 0,
                "last_decision": "READY" if ready else "REVIEW",
            },
            "business": {
                "edition": config["edition"],
                "product_name": config["product_name"],
                "organization": config["organization"],
                "environment": config["environment"],
                "accent_color": config["accent_color"],
                "support_contact": config["support_contact"],
                "release": "B80.1",
                "ui": dict(config.get("ui", {})),
                "features": dict(config["features"]),
            },
            "license": license_status,
            "integrity": integrity,
            "organization_profiles": self.organization_profiles.status(),
            "access_control": self.access_control.status(),
            "safety": dict(config["safety"]),
            "decision": "READY" if ready else "REVIEW",
            "reason": (
                "Business Edition działa w trybie właścicielskim."
                if ready
                else "Licencja lub integralność wymagają uwagi."
            ),
            "report_path": str(self.manifest_path),
            "errors": [] if ready else ["Sprawdź licencję i manifest integralności."],
        }
    def configuration(self) -> dict[str, Any]:
        response = self.status()
        response["status"] = "BUSINESS_EDITION_CONFIGURATION"
        return response
    def license_details(self) -> dict[str, Any]:
        response = self.status()
        response["status"] = "BUSINESS_EDITION_LICENSE"
        response["decision"] = "ACTIVE" if response["license"].get("active") else "REVIEW"
        return response
    def integrity_status(self) -> dict[str, Any]:
        response = self.status()
        response["status"] = "BUSINESS_EDITION_INTEGRITY"
        response["decision"] = str(response["integrity"].get("status", "UNKNOWN"))
        return response
    def verify_integrity(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            return {
                "status": "BASELINE_PENDING",
                "files_checked": 0,
                "changed": [],
                "missing": [],
                "generated_at": None,
            }
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {
                "status": "INVALID_MANIFEST",
                "files_checked": 0,
                "changed": [],
                "missing": [],
                "generated_at": None,
            }
        files = payload.get("files", {})
        if not isinstance(files, dict):
            files = {}
        changed: list[str] = []
        missing: list[str] = []
        checked = 0
        root = self.paths.root.resolve(strict=False)
        for relative, expected in files.items():
            candidate = (root / str(relative)).resolve(strict=False)
            try:
                candidate.relative_to(root)
            except ValueError:
                changed.append(str(relative))
                continue
            if not candidate.is_file():
                missing.append(str(relative))
                continue
            checked += 1
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if digest != str(expected):
                changed.append(str(relative))
        status = "VERIFIED" if not changed and not missing else "CHANGED"
        return {
            "status": status,
            "files_checked": checked,
            "changed": changed[:50],
            "missing": missing[:50],
            "generated_at": payload.get("generated_at"),
        }
    def create_integrity_manifest(self, paths: list[str]) -> dict[str, Any]:
        root = self.paths.root.resolve(strict=False)
        files: dict[str, str] = {}
        for relative in paths:
            candidate = (root / relative).resolve(strict=False)
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            if candidate.is_file():
                files[relative.replace("\\", "/")] = hashlib.sha256(
                    candidate.read_bytes()
                ).hexdigest()
        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "algorithm": "SHA-256",
            "purpose": "tamper-detection-baseline-not-encryption",
            "files": files,
        }
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.manifest_path)
        return payload
