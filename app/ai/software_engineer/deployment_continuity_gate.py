from __future__ import annotations

import hmac
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root

from .deployment_receipt_attestation import DeploymentReceiptAttestation
from .deployment_receipt_ledger import DeploymentReceiptLedger
from .safe_development_models import SafeDevelopmentSession


class DeploymentContinuityGate:
    """Fail closed when a deployment no longer continues verified history."""

    VERSION = 1

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        ledger: DeploymentReceiptLedger | None = None,
        attestation: DeploymentReceiptAttestation | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.ledger = ledger or DeploymentReceiptLedger(self.project_root)
        self.attestation = attestation or DeploymentReceiptAttestation(
            self.project_root,
            ledger=self.ledger,
        )

    def check_deploy(
        self,
        session: SafeDevelopmentSession,
    ) -> dict[str, Any]:
        audit = self.ledger.audit(repair_index=True)
        if not audit.get("success", False):
            return self._ledger_failure(audit, target=session.target)
        try:
            previous = self.ledger.latest_receipt(session.target)
        except (OSError, TypeError, ValueError) as error:
            return {
                "success": False,
                "status": "RECEIPT_LEDGER_UNHEALTHY",
                "target": session.target,
                "previous_receipt_digest": "",
                "errors": [f"{type(error).__name__}: {error}"],
            }
        if previous is None:
            return {
                "success": True,
                "status": "DEPLOYMENT_CONTINUITY_BOOTSTRAP",
                "target": session.target,
                "previous_receipt_digest": "",
                "previous_operation": "",
                "expected_source_hash": session.source_hash,
                "actual_source_hash": session.source_hash,
                "errors": [],
            }

        previous_digest = str(previous.get("receipt_digest", ""))
        previous_operation = str(previous.get("operation", ""))
        expected_source_hash = (
            str(previous.get("proposed_hash", ""))
            if previous_operation == "DEPLOY"
            else str(previous.get("source_hash", ""))
        )
        if not hmac.compare_digest(expected_source_hash, session.source_hash):
            return {
                "success": False,
                "status": "DEPLOYMENT_BASELINE_MISMATCH",
                "target": session.target,
                "previous_receipt_digest": previous_digest,
                "previous_operation": previous_operation,
                "expected_source_hash": expected_source_hash,
                "actual_source_hash": session.source_hash,
                "errors": [],
            }

        attestation = self.attestation.attest_receipt(previous_digest)
        if not attestation.get("success", False):
            return {
                "success": False,
                "status": "PREVIOUS_DEPLOYMENT_UNHEALTHY",
                "target": session.target,
                "previous_receipt_digest": previous_digest,
                "previous_operation": previous_operation,
                "expected_source_hash": expected_source_hash,
                "actual_source_hash": session.source_hash,
                "attestation_status": str(attestation.get("status", "")),
                "errors": list(attestation.get("errors", []) or []),
            }
        return {
            "success": True,
            "status": "DEPLOYMENT_CONTINUITY_VERIFIED",
            "target": session.target,
            "previous_receipt_digest": previous_digest,
            "previous_operation": previous_operation,
            "expected_source_hash": expected_source_hash,
            "actual_source_hash": session.source_hash,
            "attestation_status": str(attestation.get("status", "")),
            "errors": [],
        }

    def check_rollback(
        self,
        session: SafeDevelopmentSession,
    ) -> dict[str, Any]:
        audit = self.ledger.audit(repair_index=True)
        if not audit.get("success", False):
            return self._ledger_failure(audit, target=session.target)
        deployment_receipt = dict(
            dict(session.deployment or {}).get("receipt", {}) or {}
        )
        deployment_digest = str(
            deployment_receipt.get("receipt_digest", "")
        )
        if not deployment_digest:
            return {
                "success": False,
                "status": "ROLLBACK_DEPLOYMENT_RECEIPT_MISSING",
                "target": session.target,
                "deployment_receipt_digest": "",
                "latest_receipt_digest": "",
                "errors": [],
            }
        try:
            latest = self.ledger.latest_receipt(session.target)
        except (OSError, TypeError, ValueError) as error:
            return {
                "success": False,
                "status": "RECEIPT_LEDGER_UNHEALTHY",
                "target": session.target,
                "deployment_receipt_digest": deployment_digest,
                "latest_receipt_digest": "",
                "errors": [f"{type(error).__name__}: {error}"],
            }
        latest_digest = str(
            dict(latest or {}).get("receipt_digest", "")
        )
        if (
            not latest_digest
            or not hmac.compare_digest(latest_digest, deployment_digest)
        ):
            return {
                "success": False,
                "status": "ROLLBACK_SUPERSEDED",
                "target": session.target,
                "deployment_receipt_digest": deployment_digest,
                "latest_receipt_digest": latest_digest,
                "errors": [],
            }

        attestation = self.attestation.attest_receipt(latest_digest)
        if not attestation.get("success", False):
            return {
                "success": False,
                "status": "ROLLBACK_DEPLOYMENT_UNHEALTHY",
                "target": session.target,
                "deployment_receipt_digest": deployment_digest,
                "latest_receipt_digest": latest_digest,
                "attestation_status": str(attestation.get("status", "")),
                "errors": list(attestation.get("errors", []) or []),
            }
        return {
            "success": True,
            "status": "ROLLBACK_CONTINUITY_VERIFIED",
            "target": session.target,
            "deployment_receipt_digest": deployment_digest,
            "latest_receipt_digest": latest_digest,
            "attestation_status": str(attestation.get("status", "")),
            "errors": [],
        }

    @staticmethod
    def _ledger_failure(
        audit: dict[str, Any],
        *,
        target: str,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "status": "RECEIPT_LEDGER_UNHEALTHY",
            "target": target,
            "previous_receipt_digest": "",
            "ledger_status": str(audit.get("status", "")),
            "invalid_artifact_count": len(
                list(audit.get("invalid_artifacts", []) or [])
            ),
            "missing_artifact_count": len(
                list(audit.get("missing_artifacts", []) or [])
            ),
            "timeline_conflict_count": len(
                list(audit.get("timeline_conflicts", []) or [])
            ),
            "errors": [],
        }
