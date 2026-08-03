from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root

from .deployment_receipt_ledger import DeploymentReceiptLedger


class DeploymentReceiptAttestation:
    """Verify live code and backups against the latest durable receipts."""

    VERSION = 1

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        ledger: DeploymentReceiptLedger | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.ledger = ledger or DeploymentReceiptLedger(self.project_root)
        self.backups_root = (
            self.project_root
            / "data"
            / "autodev"
            / "safe_development_2"
            / "backups"
        )

    def attest_target(self, target: str) -> dict[str, Any]:
        try:
            normalized, _ = self._target(target)
        except ValueError as error:
            return self._seal({
                "success": False,
                "status": "INVALID_ATTESTATION_TARGET",
                "target": str(target),
                "errors": [str(error)],
            })
        audit = self.ledger.audit(repair_index=True)
        if not audit.get("success", False):
            return self._ledger_failure(audit, target=normalized)
        record = next(
            (
                item
                for item in self.ledger.list_receipts(limit=1000)
                if str(item.get("target", "")) == normalized
            ),
            None,
        )
        if record is None:
            return self._seal({
                "success": False,
                "status": "NO_RECEIPT_FOR_TARGET",
                "target": normalized,
                "errors": [],
            })
        return self.attest_receipt(str(record.get("receipt_digest", "")))

    def attest_receipt(self, receipt_digest: str) -> dict[str, Any]:
        verification = self.ledger.verify(receipt_digest)
        if not verification.get("success", False):
            return self._seal({
                "success": False,
                "status": "RECEIPT_EVIDENCE_INVALID",
                "receipt_digest": str(receipt_digest),
                "ledger_status": str(verification.get("status", "")),
                "errors": list(verification.get("errors", []) or []),
            })
        return self._attest_verified_receipt(
            dict(verification.get("receipt", {}) or {})
        )

    def attest_campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = str(campaign_id).strip()
        if not self._safe_identifier(campaign, prefix="autodev-work-"):
            return self._seal({
                "success": False,
                "status": "INVALID_ATTESTATION_CAMPAIGN",
                "campaign_id": campaign,
                "errors": ["Nieprawidłowy identyfikator kampanii."],
            })
        audit = self.ledger.audit(repair_index=True)
        if not audit.get("success", False):
            return self._ledger_failure(audit, campaign_id=campaign)
        all_records = self.ledger.list_receipts(limit=1000)
        campaign_records = [
            item
            for item in all_records
            if str(item.get("campaign_id", "")) == campaign
        ]
        if not campaign_records:
            return self._seal({
                "success": False,
                "status": "NO_RECEIPTS_FOR_CAMPAIGN",
                "campaign_id": campaign,
                "results": [],
                "errors": [],
            })
        latest_global = self._latest_by_target(all_records)
        latest_campaign = self._latest_by_target(campaign_records)
        results: list[dict[str, Any]] = []
        for target, record in latest_campaign.items():
            digest = str(record.get("receipt_digest", ""))
            global_digest = str(
                latest_global.get(target, {}).get("receipt_digest", "")
            )
            if global_digest and global_digest != digest:
                results.append(self._seal({
                    "success": True,
                    "status": "RECEIPT_SUPERSEDED",
                    "target": target,
                    "receipt_digest": digest,
                    "superseded_by": global_digest,
                    "errors": [],
                }))
                continue
            results.append(self.attest_receipt(digest))
        success = all(result.get("success", False) for result in results)
        return self._seal({
            "success": success,
            "status": (
                "CAMPAIGN_ATTESTED"
                if success
                else "CAMPAIGN_ATTESTATION_FAILED"
            ),
            "campaign_id": campaign,
            "target_count": len(results),
            "attested_count": sum(
                result.get("status") == "DEPLOYMENT_ATTESTED"
                for result in results
            ),
            "superseded_count": sum(
                result.get("status") == "RECEIPT_SUPERSEDED"
                for result in results
            ),
            "results": results,
            "errors": [],
        })

    def attest_all(self) -> dict[str, Any]:
        audit = self.ledger.audit(repair_index=True)
        if not audit.get("success", False):
            return self._ledger_failure(audit)
        records = self.ledger.list_receipts(limit=1000)
        latest = self._latest_by_target(records)
        results = [
            self.attest_receipt(str(record.get("receipt_digest", "")))
            for record in latest.values()
        ]
        success = all(result.get("success", False) for result in results)
        return self._seal({
            "success": success,
            "status": (
                "PROJECT_DEPLOYMENTS_ATTESTED"
                if success
                else "PROJECT_DEPLOYMENT_ATTESTATION_FAILED"
            ),
            "target_count": len(results),
            "attested_count": sum(
                result.get("status") == "DEPLOYMENT_ATTESTED"
                for result in results
            ),
            "results": results,
            "errors": [],
        })

    @classmethod
    def verify_report(cls, report: dict[str, Any]) -> bool:
        value = dict(report or {})
        provided = str(value.get("attestation_digest", ""))
        return bool(provided) and hmac.compare_digest(
            provided,
            cls._report_digest(value),
        )

    def _attest_verified_receipt(
        self,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        target_value = str(receipt.get("target", ""))
        digest = str(receipt.get("receipt_digest", ""))
        base = {
            "receipt_digest": digest,
            "session_id": str(receipt.get("session_id", "")),
            "campaign_id": str(receipt.get("campaign_id", "")),
            "target": target_value,
            "operation": str(receipt.get("operation", "")),
            "outcome": str(receipt.get("outcome", "")),
            "ledger_verified": True,
        }
        try:
            normalized, target = self._target(target_value)
        except ValueError as error:
            return self._seal({
                **base,
                "success": False,
                "status": "INVALID_ATTESTATION_TARGET",
                "errors": [str(error)],
            })
        base["target"] = normalized
        expected_live_hash = (
            str(receipt.get("proposed_hash", ""))
            if receipt.get("operation") == "DEPLOY"
            else str(receipt.get("source_hash", ""))
        )
        if not target.is_file() or target.is_symlink():
            return self._seal({
                **base,
                "success": False,
                "status": "LIVE_TARGET_MISSING",
                "expected_live_hash": expected_live_hash,
                "actual_live_hash": "",
                "live_matches": False,
                "backup_matches": False,
                "errors": [],
            })
        try:
            actual_live_hash = self._text_hash(
                target.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            return self._seal({
                **base,
                "success": False,
                "status": "LIVE_TARGET_UNREADABLE",
                "expected_live_hash": expected_live_hash,
                "actual_live_hash": "",
                "live_matches": False,
                "backup_matches": False,
                "errors": [f"{type(error).__name__}: {error}"],
            })
        live_matches = hmac.compare_digest(
            expected_live_hash,
            actual_live_hash,
        )
        backup = (
            self.backups_root
            / str(receipt.get("session_id", ""))
            / "original.py"
        )
        expected_backup_hash = str(receipt.get("backup_hash", ""))
        source_hash = str(receipt.get("source_hash", ""))
        actual_backup_hash = ""
        actual_backup_source_hash = ""
        backup_exists = backup.is_file() and not backup.is_symlink()
        if backup_exists:
            try:
                actual_backup_hash = self._bytes_hash(backup.read_bytes())
                actual_backup_source_hash = self._text_hash(
                    backup.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError):
                backup_exists = False
        backup_matches = bool(
            backup_exists
            and hmac.compare_digest(
                expected_backup_hash,
                actual_backup_hash,
            )
            and hmac.compare_digest(
                source_hash,
                actual_backup_source_hash,
            )
        )
        if not live_matches:
            status = "LIVE_TARGET_DRIFT"
        elif not backup_exists:
            status = "BACKUP_MISSING"
        elif not backup_matches:
            status = "BACKUP_TAMPERED"
        else:
            status = "DEPLOYMENT_ATTESTED"
        success = status == "DEPLOYMENT_ATTESTED"
        return self._seal({
            **base,
            "success": success,
            "status": status,
            "expected_live_hash": expected_live_hash,
            "actual_live_hash": actual_live_hash,
            "live_matches": live_matches,
            "expected_backup_hash": expected_backup_hash,
            "actual_backup_hash": actual_backup_hash,
            "backup_source_hash": actual_backup_source_hash,
            "backup_exists": backup_exists,
            "backup_matches": backup_matches,
            "errors": [],
        })

    def _ledger_failure(
        self,
        audit: dict[str, Any],
        **context: Any,
    ) -> dict[str, Any]:
        return self._seal({
            **context,
            "success": False,
            "status": "RECEIPT_LEDGER_UNHEALTHY",
            "ledger_status": str(audit.get("status", "")),
            "invalid_artifact_count": len(
                list(audit.get("invalid_artifacts", []) or [])
            ),
            "missing_artifact_count": len(
                list(audit.get("missing_artifacts", []) or [])
            ),
            "errors": [],
        })

    def _target(self, target: str) -> tuple[str, Path]:
        value = str(target).strip().replace("\\", "/")
        relative = Path(value)
        if (
            not value
            or value == "."
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            raise ValueError("Atestacja wymaga względnego targetu projektu.")
        resolved = (self.project_root / relative).resolve(strict=False)
        try:
            resolved.relative_to(self.project_root)
        except ValueError as error:
            raise ValueError("Target atestacji znajduje się poza projektem.") from error
        return relative.as_posix(), resolved

    @staticmethod
    def _latest_by_target(
        records: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for record in records:
            target = str(record.get("target", ""))
            if target and target not in latest:
                latest[target] = dict(record)
        return latest

    @staticmethod
    def _safe_identifier(value: str, *, prefix: str) -> bool:
        text = str(value).strip()
        return bool(
            text.startswith(prefix)
            and text.isascii()
            and len(text) <= 100
            and text.replace("-", "").isalnum()
        )

    @classmethod
    def _seal(cls, report: dict[str, Any]) -> dict[str, Any]:
        value = dict(report or {})
        value["schema_version"] = cls.VERSION
        value.setdefault("attested_at", datetime.now(timezone.utc).isoformat())
        value["attestation_digest"] = cls._report_digest(value)
        return value

    @staticmethod
    def _report_digest(report: dict[str, Any]) -> str:
        payload = {
            key: value for key, value in dict(report or {}).items()
            if key != "attestation_digest"
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _text_hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _bytes_hash(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()
