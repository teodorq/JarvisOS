from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import shutil
import time
from typing import Any

from app.core.project_paths import resolve_project_root

from .deployment_continuity_gate import DeploymentContinuityGate
from .deployment_receipt_attestation import DeploymentReceiptAttestation
from .deployment_receipt_ledger import DeploymentReceiptLedger
from .safe_development_models import SafeDevelopmentPolicy, SafeDevelopmentSession
from .safe_development_store import SafeDevelopmentStore
from .safe_development_validation import SafeDevelopmentValidator
from .safe_development_workspace import SafeDevelopmentWorkspace


class SafeDevelopmentDeployment:
    """Approval-gated atomic deployment and verified rollback for one patch."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        store: SafeDevelopmentStore | None = None,
        policy: SafeDevelopmentPolicy | None = None,
        validator: SafeDevelopmentValidator | None = None,
        workspace: SafeDevelopmentWorkspace | None = None,
        ledger: DeploymentReceiptLedger | None = None,
        continuity: DeploymentContinuityGate | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or SafeDevelopmentPolicy()
        self.store = store or SafeDevelopmentStore(
            self.project_root,
            policy=self.policy,
        )
        self.validator = validator or SafeDevelopmentValidator(
            self.project_root,
            policy=self.policy,
        )
        self.workspace = workspace or SafeDevelopmentWorkspace(
            self.project_root,
            store=self.store,
            policy=self.policy,
        )
        self.ledger = ledger or DeploymentReceiptLedger(self.project_root)
        self.attestation = DeploymentReceiptAttestation(
            self.project_root,
            ledger=self.ledger,
        )
        self.continuity = continuity or DeploymentContinuityGate(
            self.project_root,
            ledger=self.ledger,
            attestation=self.attestation,
        )

    def deploy(self, session_id: str, fingerprint: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        if session.status == "DEPLOYED":
            return self._result(
                session,
                success=False,
                status="ALREADY_DEPLOYED",
                message="Ta poprawka została już wdrożona. Nie wdrożyłem jej ponownie.",
            )
        if session.status != "READY_FOR_APPROVAL":
            return self._result(
                session,
                success=False,
                status="DEPLOYMENT_NOT_READY",
                message="Ta poprawka nie jest gotowa do bezpiecznego wdrożenia.",
            )
        if not self._matches_deploy_fingerprint(session, fingerprint):
            return self._result(
                session,
                success=False,
                status="CONFIRMATION_MISMATCH",
                message="Potwierdzenie nie dotyczy tej przygotowanej poprawki.",
            )
        continuity = self.continuity.check_deploy(session)
        session.validation["continuity_pre_deploy"] = continuity
        if not continuity.get("success", False):
            self.store.save_session(session)
            return self._result(
                session,
                success=False,
                status="DEPLOYMENT_CONTINUITY_BLOCKED",
                message=(
                    "Historia tego pliku nie zgadza się z przygotowaną "
                    "poprawką. Niczego nie wdrożyłem."
                ),
            )
        try:
            artifacts = self.workspace.verify_artifacts(session)
            live_target = self._target(session.target)
            current = live_target.read_text(encoding="utf-8")
            if self._hash(current) != session.source_hash:
                session.status = "STALE"
                session.errors.append(
                    "Plik źródłowy zmienił się po przygotowaniu poprawki."
                )
                self.store.save_session(session)
                return self._result(
                    session,
                    success=False,
                    status="SOURCE_CHANGED",
                    message=(
                        "Projekt zmienił się od czasu przygotowania poprawki. "
                        "Nie wdrożyłem jej. Przygotuj nową wersję."
                    ),
                )
            static = self.validator.static_validate(
                session,
                original=artifacts["original"],
                proposed=artifacts["proposed"],
            )
            if not static.get("success", False):
                return self._reject(session, "STATIC_REVALIDATION_FAILED", static)
            backup = self._create_backup(session, live_target)
            session.backup_path = str(backup)
            session.status = "DEPLOYING"
            session.deployment = {
                "started_at": self._now(),
                "confirmation_fingerprint": fingerprint,
                "backup_hash": self._hash_bytes(backup.read_bytes()),
            }
            self.store.save_session(session)
            self._atomic_write(live_target, artifacts["proposed"])
            if self._hash(live_target.read_text(encoding="utf-8")) != session.proposed_hash:
                raise RuntimeError("Hash wdrożonego pliku nie zgadza się z propozycją.")
            live_validation = self.validator.validate_live_target(session)
            if not live_validation.get("success", False):
                raise RuntimeError("Walidacja po wdrożeniu nie przeszła.")
            session.status = "DEPLOYED"
            session.validation["live"] = live_validation
            completed_at = self._now()
            session.deployment.update({
                "completed_at": completed_at,
                "target_hash": session.proposed_hash,
                "verified": True,
            })
            receipt = self._build_receipt(
                session,
                operation="DEPLOY",
                outcome="DEPLOYED",
                completed_at=completed_at,
                validation=live_validation,
            )
            self.ledger.archive(receipt)
            session.deployment["receipt"] = receipt
            self.store.save_session(session)
            return self._result(
                session,
                success=True,
                status="DEPLOYED",
                message=(
                    f"Wdrożyłem przygotowaną poprawkę w {session.target}. "
                    "Sprawdziłem kompilację i testy po zmianie."
                ),
            )
        except Exception as error:
            rollback = self._restore_after_failure(session, str(error))
            return self._result(
                session,
                success=False,
                status=str(rollback.get("status", "DEPLOYMENT_FAILED")),
                message=str(rollback.get("message", "Wdrożenie nie powiodło się.")),
            )

    def rollback(self, session_id: str, fingerprint: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        if session.status == "ROLLED_BACK":
            return self._result(
                session,
                success=False,
                status="ALREADY_ROLLED_BACK",
                message="Ta poprawka została już cofnięta.",
            )
        if session.status != "DEPLOYED":
            return self._result(
                session,
                success=False,
                status="ROLLBACK_NOT_AVAILABLE",
                message="Nie ma wdrożonej poprawki, którą można teraz cofnąć.",
            )
        expected = self.rollback_fingerprint(session)
        if not fingerprint or fingerprint != expected:
            return self._result(
                session,
                success=False,
                status="ROLLBACK_CONFIRMATION_MISMATCH",
                message="Potwierdzenie nie dotyczy tej operacji cofnięcia.",
            )
        try:
            target = self._target(session.target)
            current = target.read_text(encoding="utf-8")
            if self._hash(current) != session.proposed_hash:
                return self._result(
                    session,
                    success=False,
                    status="ROLLBACK_SOURCE_CHANGED",
                    message=(
                        "Plik zmienił się po wdrożeniu. Nie nadpisałem nowszych zmian."
                    ),
                )
            backup = Path(session.backup_path)
            self._verify_backup(session, backup)
            continuity = self.continuity.check_rollback(session)
            session.validation["continuity_pre_rollback"] = continuity
            if not continuity.get("success", False):
                self.store.save_session(session)
                return self._result(
                    session,
                    success=False,
                    status="ROLLBACK_CONTINUITY_BLOCKED",
                    message=(
                        "To wdrożenie nie jest już najnowszym potwierdzonym "
                        "stanem pliku. Niczego nie cofnąłem."
                    ),
                )
            original = backup.read_text(encoding="utf-8")
            self._atomic_write(target, original)
            if self._hash(target.read_text(encoding="utf-8")) != session.source_hash:
                raise RuntimeError("Nie udało się potwierdzić przywróconej wersji.")
            session.status = "ROLLED_BACK"
            completed_at = self._now()
            session.rollback = {
                "completed_at": completed_at,
                "verified": True,
                "restored_hash": session.source_hash,
            }
            receipt = self._build_receipt(
                session,
                operation="ROLLBACK",
                outcome="ROLLED_BACK",
                completed_at=completed_at,
            )
            self.ledger.archive(receipt)
            session.rollback["receipt"] = receipt
            self.store.save_session(session)
            return self._result(
                session,
                success=True,
                status="ROLLED_BACK",
                message=(
                    f"Cofnąłem poprawkę w {session.target} i sprawdziłem przywrócony plik."
                ),
            )
        except Exception as error:
            session.errors.append(str(error))
            self.store.save_session(session)
            return self._result(
                session,
                success=False,
                status="ROLLBACK_FAILED",
                message="Nie udało się bezpiecznie cofnąć poprawki.",
            )

    def ensure_receipts(self, session_id: str) -> dict[str, Any]:
        """Backfill tamper-evident receipts only from already verified evidence."""
        session = self.store.load_session(session_id)
        created: list[str] = []
        backup = Path(session.backup_path) if session.backup_path else None
        if backup is not None and backup.is_file():
            self._verify_backup(session, backup)
            recorded_backup_hash = str(
                dict(session.deployment or {}).get("backup_hash", "")
            )
            if (
                recorded_backup_hash
                and self._hash_bytes(backup.read_bytes())
                != recorded_backup_hash
            ):
                raise ValueError("Hash backupu nie zgadza się z wdrożeniem.")

        deployment = dict(session.deployment or {})
        rollback = dict(session.rollback or {})
        requested_backfill = (
            deployment.get("verified") is True
            and not dict(deployment.get("receipt", {}) or {})
        ) or (
            rollback.get("verified") is True
            and not dict(rollback.get("receipt", {}) or {})
        )
        if requested_backfill and (backup is None or not backup.is_file()):
            raise FileNotFoundError(
                "Brakuje zweryfikowanego backupu dla receipt."
            )
        if (
            deployment.get("verified") is True
            and not dict(deployment.get("receipt", {}) or {})
        ):
            archived_receipt = self._archived_session_receipt(
                session,
                operations={"DEPLOY"},
            )
            if archived_receipt is not None:
                session.deployment["receipt"] = archived_receipt
                deployment = dict(session.deployment)
                created.append("DEPLOY")
        if (
            rollback.get("verified") is True
            and not dict(rollback.get("receipt", {}) or {})
        ):
            operation = (
                "AUTOMATIC_ROLLBACK"
                if rollback.get("automatic") is True
                else "ROLLBACK"
            )
            archived_receipt = self._archived_session_receipt(
                session,
                operations={operation},
            )
            if archived_receipt is not None:
                session.rollback["receipt"] = archived_receipt
                rollback = dict(session.rollback)
                created.append(operation)
        needs_backfill = (
            deployment.get("verified") is True
            and not dict(deployment.get("receipt", {}) or {})
        ) or (
            rollback.get("verified") is True
            and not dict(rollback.get("receipt", {}) or {})
        )
        if needs_backfill and (backup is None or not backup.is_file()):
            raise FileNotFoundError(
                "Brakuje zweryfikowanego backupu dla receipt."
            )
        if (
            deployment.get("verified") is True
            and not dict(deployment.get("receipt", {}) or {})
        ):
            if session.status == "DEPLOYED":
                target = self._target(session.target)
                current_hash = self._hash(target.read_text(encoding="utf-8"))
                if current_hash != session.proposed_hash:
                    raise ValueError("Nie można potwierdzić wdrożonego pliku.")
            session.deployment["receipt"] = self._build_receipt(
                session,
                operation="DEPLOY",
                outcome="DEPLOYED",
                completed_at=str(deployment.get("completed_at", "")),
                validation=dict(session.validation.get("live", {}) or {}),
            )
            created.append("DEPLOY")

        if (
            rollback.get("verified") is True
            and not dict(rollback.get("receipt", {}) or {})
        ):
            if session.status == "ROLLED_BACK":
                target = self._target(session.target)
                current_hash = self._hash(target.read_text(encoding="utf-8"))
                if current_hash != session.source_hash:
                    raise ValueError("Nie można potwierdzić cofniętego pliku.")
            operation = (
                "AUTOMATIC_ROLLBACK"
                if rollback.get("automatic") is True
                else "ROLLBACK"
            )
            session.rollback["receipt"] = self._build_receipt(
                session,
                operation=operation,
                outcome="ROLLED_BACK",
                completed_at=str(rollback.get("completed_at", "")),
                reason=str(rollback.get("reason", "")),
            )
            created.append(operation)
        archived: list[str] = []
        for channel in ("deployment", "rollback"):
            container = dict(getattr(session, channel, {}) or {})
            receipt = dict(container.get("receipt", {}) or {})
            if not receipt:
                continue
            archived_result = self.ledger.archive(receipt)
            if archived_result.get("created", False):
                archived.append(str(receipt.get("operation", channel.upper())))
        if created:
            self.store.save_session(session)
        status = (
            "RECEIPTS_BACKFILLED"
            if created
            else "RECEIPTS_ARCHIVED"
            if archived
            else "RECEIPTS_CURRENT"
        )
        return {
            "success": True,
            "status": status,
            "created": created,
            "archived": archived,
            "session": session.to_dict(),
        }

    def _archived_session_receipt(
        self,
        session: SafeDevelopmentSession,
        *,
        operations: set[str],
    ) -> dict[str, Any] | None:
        for record in self.ledger.list_receipts(
            session_id=session.session_id,
            limit=10,
        ):
            if str(record.get("operation", "")) not in operations:
                continue
            verification = self.ledger.verify(
                str(record.get("receipt_digest", ""))
            )
            receipt = dict(verification.get("receipt", {}) or {})
            if not verification.get("success", False):
                continue
            if any(
                receipt.get(key) != expected
                for key, expected in (
                    ("target", session.target),
                    ("source_hash", session.source_hash),
                    ("proposed_hash", session.proposed_hash),
                    (
                        "backup_hash",
                        str(session.deployment.get("backup_hash", "")),
                    ),
                )
            ):
                continue
            return receipt
        return None

    def rollback_fingerprint(self, session: SafeDevelopmentSession) -> str:
        return self.store.fingerprint(
            "rollback",
            session.session_id,
            session.target,
            session.proposed_hash,
        )

    def _matches_deploy_fingerprint(
        self,
        session: SafeDevelopmentSession,
        fingerprint: str,
    ) -> bool:
        return bool(fingerprint) and fingerprint == session.fingerprint

    def _create_backup(
        self,
        session: SafeDevelopmentSession,
        live_target: Path,
    ) -> Path:
        backup = self.store.backup_dir(session.session_id) / "original.py"
        shutil.copy2(live_target, backup)
        self._verify_backup(session, backup)
        return backup

    def _verify_backup(self, session: SafeDevelopmentSession, backup: Path) -> None:
        if not backup.is_file() or backup.is_symlink():
            raise FileNotFoundError("Brakuje bezpiecznej kopii źródła.")
        if self._hash(backup.read_text(encoding="utf-8")) != session.source_hash:
            raise ValueError("Kopia źródła ma nieprawidłowy hash.")

    def _restore_after_failure(
        self,
        session: SafeDevelopmentSession,
        reason: str,
    ) -> dict[str, Any]:
        session.errors.append(reason)
        backup = Path(session.backup_path) if session.backup_path else None
        target = self._target(session.target)
        if self.policy.auto_rollback and backup is not None and backup.is_file():
            try:
                self._verify_backup(session, backup)
                self._atomic_write(target, backup.read_text(encoding="utf-8"))
                restored = self._hash(target.read_text(encoding="utf-8"))
                if restored != session.source_hash:
                    raise RuntimeError("Hash po rollbacku jest nieprawidłowy.")
                session.status = "ROLLED_BACK"
                completed_at = self._now()
                session.rollback = {
                    "automatic": True,
                    "completed_at": completed_at,
                    "reason": reason,
                    "verified": True,
                }
                receipt = self._build_receipt(
                    session,
                    operation="AUTOMATIC_ROLLBACK",
                    outcome="ROLLED_BACK",
                    completed_at=completed_at,
                    reason=reason,
                )
                self.ledger.archive(receipt)
                session.rollback["receipt"] = receipt
                self.store.save_session(session)
                return {
                    "status": "AUTOMATIC_ROLLBACK_COMPLETED",
                    "message": (
                        "Wdrożenie nie przeszło walidacji. Automatycznie "
                        "przywróciłem poprzednią wersję."
                    ),
                }
            except Exception as rollback_error:
                session.errors.append(str(rollback_error))
        session.status = "FAILED"
        self.store.save_session(session)
        return {
            "status": "DEPLOYMENT_FAILED",
            "message": (
                "Wdrożenie nie powiodło się. Sprawdź raport sesji przed kolejną próbą."
            ),
        }

    def _reject(
        self,
        session: SafeDevelopmentSession,
        status: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        session.status = "FAILED"
        session.validation["deployment_static"] = result
        session.errors.extend(list(result.get("errors", []) or []))
        self.store.save_session(session)
        return self._result(
            session,
            success=False,
            status=status,
            message="Ponowna walidacja poprawki nie przeszła. Niczego nie zmieniłem.",
        )

    def _build_receipt(
        self,
        session: SafeDevelopmentSession,
        *,
        operation: str,
        outcome: str,
        completed_at: str,
        validation: dict[str, Any] | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        validation = dict(validation or {})
        tests = dict(validation.get("tests", {}) or {})
        metadata = dict(session.metadata or {})
        previous_digest = ""
        if operation in {"ROLLBACK", "AUTOMATIC_ROLLBACK"}:
            deployment_receipt = dict(
                dict(session.deployment or {}).get("receipt", {}) or {}
            )
            if self.verify_receipt(deployment_receipt):
                previous_digest = str(
                    deployment_receipt.get("receipt_digest", "")
                )
        if not previous_digest:
            previous = self.ledger.latest_receipt(session.target)
            previous_digest = str(
                dict(previous or {}).get("receipt_digest", "")
            )
        receipt = {
            "schema_version": 2,
            "operation": str(operation),
            "outcome": str(outcome),
            "session_id": session.session_id,
            "campaign_id": str(metadata.get("campaign_id", "")),
            "work_item_id": str(metadata.get("work_item_id", "")),
            "target": session.target,
            "source_hash": session.source_hash,
            "proposed_hash": session.proposed_hash,
            "backup_hash": str(session.deployment.get("backup_hash", "")),
            "completed_at": str(completed_at),
            "validation_success": bool(validation.get("success", True)),
            "test_count": int(tests.get("count", 0) or 0),
            "verified": True,
            "automatic_approval": False,
            "automatic_deployment": False,
            "previous_receipt_digest": previous_digest,
        }
        if reason:
            receipt["reason_digest"] = self._hash(reason)
        receipt["receipt_digest"] = self._receipt_digest(receipt)
        return receipt

    @classmethod
    def verify_receipt(cls, receipt: dict[str, Any]) -> bool:
        value = dict(receipt or {})
        provided = str(value.get("receipt_digest", ""))
        return bool(provided) and hmac.compare_digest(
            provided,
            cls._receipt_digest(value),
        )

    @staticmethod
    def _receipt_digest(receipt: dict[str, Any]) -> str:
        payload = {
            key: value for key, value in dict(receipt or {}).items()
            if key != "receipt_digest"
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _target(self, relative: str) -> Path:
        target = (self.project_root / Path(relative)).resolve(strict=False)
        try:
            target.relative_to(self.project_root)
        except ValueError as error:
            raise ValueError("Target znajduje się poza projektem.") from error
        if not target.is_file() or target.is_symlink():
            raise ValueError("Target nie jest bezpiecznym plikiem projektu.")
        return target

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_name(path.name + ".safe-dev.tmp")
        temporary.write_text(content, encoding="utf-8")
        for attempt in range(4):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt >= 3:
                    raise
                time.sleep(0.15 * (attempt + 1))

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_bytes(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _result(
        session: SafeDevelopmentSession,
        *,
        success: bool,
        status: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "message": message,
            "session": session.to_dict(),
        }
