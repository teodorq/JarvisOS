"""Lazy public API for JARVIS OS Business Edition services."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "BusinessConfigStore": ("business_config", "BusinessConfigStore"),
    "BusinessEditionService": ("business_edition_service", "BusinessEditionService"),
    "BusinessLicenseManager": ("business_license", "BusinessLicenseManager"),
    "BusinessAuditCenter": ("audit_center", "BusinessAuditCenter"),
    "BusinessDisasterRecovery": ("disaster_recovery", "BusinessDisasterRecovery"),
    "BusinessUpdateCenter": ("update_center", "BusinessUpdateCenter"),
    "BusinessInstallationManager": (
        "installation_manager",
        "BusinessInstallationManager",
    ),
    "BusinessReleaseCandidate": ("release_candidate", "BusinessReleaseCandidate"),
    "ProductionVersioning": ("production_versioning", "ProductionVersioning"),
    "CommercialLicenseAuthority": (
        "commercial_license",
        "CommercialLicenseAuthority",
    ),
    "ProductionRelease": ("production_release", "ProductionRelease"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
