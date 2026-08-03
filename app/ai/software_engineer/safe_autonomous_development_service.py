from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from app.core.project_paths import resolve_project_root

from .deployment_receipt_attestation import DeploymentReceiptAttestation
from .project_intelligence_scanner import ProjectOpportunityScanner
from .safe_development_deployment import SafeDevelopmentDeployment
from .safe_development_models import SafeDevelopmentPolicy, SafeDevelopmentSession
from .safe_development_store import SafeDevelopmentStore
from .safe_development_transform import SafeTransformPlanner
from .safe_development_validation import SafeDevelopmentValidator
from .safe_development_workspace import SafeDevelopmentWorkspace


class SafeAutonomousDevelopmentService:
    """B201-B210 approval-gated isolated code preparation and deployment."""

    CONFIG = "config/b201_b210_safe_autonomous_development_2.json"

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: SafeDevelopmentPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or self._load_policy()
        self.store = SafeDevelopmentStore(self.project_root, policy=self.policy)
        self.planner = SafeTransformPlanner(self.project_root, policy=self.policy)
        self.workspace = SafeDevelopmentWorkspace(
            self.project_root,
            store=self.store,
            policy=self.policy,
        )
        self.validator = SafeDevelopmentValidator(
            self.project_root,
            policy=self.policy,
        )
        self.deployment = SafeDevelopmentDeployment(
            self.project_root,
            store=self.store,
            policy=self.policy,
            validator=self.validator,
            workspace=self.workspace,
        )
        self.attestation = DeploymentReceiptAttestation(
            self.project_root,
            ledger=self.deployment.ledger,
        )

    def prepare(
        self,
        *,
        preview: dict[str, Any] | None = None,
        deadline_monotonic: float | None = None,
    ) -> dict[str, Any]:
        session: SafeDevelopmentSession | None = None
        try:
            self._ensure_deadline(deadline_monotonic)
            selected = dict(preview or self.store.last_preview() or {})
            if not selected:
                selected = self._scan_preview()
            self._ensure_deadline(deadline_monotonic)
            candidate = self.planner.select(selected)
            source_path = self.project_root / Path(candidate.target)
            source = source_path.read_text(encoding="utf-8")
            proposed = self.planner.apply(candidate, source)
            session = self.store.new_session(
                target=candidate.target,
                transform=candidate.transform,
                title=candidate.title,
                rationale=candidate.rationale,
                risk_score=candidate.risk_score,
                confidence=candidate.confidence,
                metadata={
                    **dict(candidate.metadata),
                    "preview": selected,
                    "automatic_approval": False,
                    "automatic_deployment": False,
                },
            )
            artifacts = self.workspace.create(
                session,
                proposed_content=proposed,
            )
            session.changed_files = list(artifacts["changed_files"])
            session.changed_lines = int(artifacts["changed_lines"])
            session.source_hash = str(artifacts["source_hash"])
            session.proposed_hash = str(artifacts["proposed_hash"])
            session.workspace_path = str(artifacts["workspace_path"])
            session.original_artifact = str(artifacts["original_artifact"])
            session.proposed_artifact = str(artifacts["proposed_artifact"])
            session.diff_artifact = str(artifacts["diff_artifact"])
            self._ensure_deadline(deadline_monotonic)
            static = self.validator.static_validate(
                session,
                original=source,
                proposed=proposed,
            )
            session.validation["static"] = static
            if not static.get("success", False):
                return self._failed_session(
                    session,
                    "STATIC_VALIDATION_FAILED",
                    "Przygotowana zmiana nie przeszła walidacji statycznej.",
                    static,
                )
            self._ensure_deadline(deadline_monotonic)
            try:
                isolated = self.validator.validate_workspace(
                    session,
                    deadline_monotonic=deadline_monotonic,
                )
            finally:
                session.validation["runtime_cleanup"] = (
                    self.workspace.cleanup_runtime_artifacts(session)
                )
            session.validation["workspace"] = isolated
            session.focused_tests = list(isolated.get("focused_tests", []) or [])
            if isolated.get("status") == "RUNTIME_BUDGET_REACHED":
                return self._failed_session(
                    session,
                    "RUNTIME_BUDGET_REACHED",
                    "Wyczerpano budżet czasu podczas bezpiecznej walidacji.",
                    isolated,
                )
            if not isolated.get("success", False):
                return self._failed_session(
                    session,
                    "WORKSPACE_VALIDATION_FAILED",
                    "Testy na izolowanej kopii nie przeszły.",
                    isolated,
                )
            self._ensure_deadline(deadline_monotonic)
            session.fingerprint = self.store.fingerprint(
                "deploy",
                session.session_id,
                session.target,
                session.source_hash,
                session.proposed_hash,
            )
            session.status = "READY_FOR_APPROVAL"
            session.metadata["manifest_artifact"] = str(
                artifacts.get("manifest_artifact", "")
            )
            self.store.save_session(session)
            return {
                "success": True,
                "status": "READY_FOR_APPROVAL",
                "message": self._prepare_message(session),
                "session": session.to_dict(),
                "operation_fingerprint": session.fingerprint,
                "requires_confirmation": False,
                "project_files_modified": False,
            }
        except TimeoutError as error:
            result = {"errors": [str(error)]}
            if session is not None:
                if "runtime_cleanup" not in session.validation:
                    session.validation["runtime_cleanup"] = (
                        self.workspace.cleanup_runtime_artifacts(session)
                    )
                return self._failed_session(
                    session,
                    "RUNTIME_BUDGET_REACHED",
                    "Wyczerpano budżet czasu bezpiecznego przygotowania.",
                    result,
                )
            return {
                "success": False,
                "status": "RUNTIME_BUDGET_REACHED",
                "message": (
                    "Wyczerpano budżet czasu bezpiecznego przygotowania. "
                    "Nie zmieniłem plików projektu."
                ),
                "errors": [str(error)],
                "requires_confirmation": False,
                "project_files_modified": False,
            }
        except Exception as error:
            result = {"errors": [str(error)]}
            if session is not None:
                return self._failed_session(
                    session,
                    "PREPARATION_FAILED",
                    "Nie udało mi się bezpiecznie przygotować poprawki.",
                    result,
                )
            return {
                "success": False,
                "status": "PREPARATION_FAILED",
                "message": (
                    "Nie udało mi się bezpiecznie przygotować poprawki. "
                    "Nie zmieniłem plików projektu."
                ),
                "errors": [str(error)],
                "requires_confirmation": False,
                "project_files_modified": False,
            }

    def status(self) -> dict[str, Any]:
        session = self.store.latest_session()
        if session is None:
            return {
                "success": True,
                "status": "NO_SESSION",
                "message": "Nie ma jeszcze przygotowanej poprawki AutoDev.",
            }
        return {
            "success": True,
            "status": session.status,
            "message": self._status_message(session),
            "session": session.to_dict(),
        }

    def plan_deploy(self) -> dict[str, Any]:
        session = self.store.latest_ready()
        if session is None:
            return {
                "success": False,
                "status": "NO_READY_PATCH",
                "message": "Nie ma gotowej, przetestowanej poprawki do wdrożenia.",
            }
        return {
            "success": True,
            "status": "CONFIRM_DEPLOYMENT",
            "session": session.to_dict(),
            "operation_fingerprint": session.fingerprint,
            "confirmation_message": (
                f"Czy wdrożyć dokładnie tę poprawkę: {session.title} w "
                f"{session.target}? Zmiana obejmuje {session.changed_lines} "
                "linii i przeszła testy na izolowanej kopii."
            ),
        }

    def deploy(self, session_id: str, fingerprint: str) -> dict[str, Any]:
        result = self.deployment.deploy(session_id, fingerprint)
        return self._attach_campaign_reconciliation(result)

    def plan_rollback(self) -> dict[str, Any]:
        session = self.store.latest_session(statuses={"DEPLOYED"})
        if session is None:
            return {
                "success": False,
                "status": "NO_DEPLOYED_PATCH",
                "message": "Nie ma ostatniej wdrożonej poprawki do cofnięcia.",
            }
        fingerprint = self.deployment.rollback_fingerprint(session)
        return {
            "success": True,
            "status": "CONFIRM_ROLLBACK",
            "session": session.to_dict(),
            "operation_fingerprint": fingerprint,
            "confirmation_message": (
                f"Czy cofnąć poprawkę {session.title} w {session.target}? "
                "Przywrócę zweryfikowaną kopię sprzed wdrożenia."
            ),
        }

    def rollback(self, session_id: str, fingerprint: str) -> dict[str, Any]:
        result = self.deployment.rollback(session_id, fingerprint)
        return self._attach_campaign_reconciliation(result)

    def ensure_receipts(self, session_id: str) -> dict[str, Any]:
        result = dict(self.deployment.ensure_receipts(session_id) or {})
        audit = self.audit_receipt_ledger(repair_index=True)
        result["receipt_ledger"] = audit
        if result.get("success", False) and not audit.get("success", False):
            result["success"] = False
            result["status"] = "RECEIPT_LEDGER_INTEGRITY_FAILED"
        return result

    def audit_receipt_ledger(
        self,
        *,
        repair_index: bool = False,
    ) -> dict[str, Any]:
        return self.deployment.ledger.audit(repair_index=repair_index)

    def attest_deployment_target(self, target: str) -> dict[str, Any]:
        return self.attestation.attest_target(target)

    def attest_campaign_deployments(
        self,
        campaign_id: str,
    ) -> dict[str, Any]:
        return self.attestation.attest_campaign(campaign_id)

    def attest_all_deployments(self) -> dict[str, Any]:
        return self.attestation.attest_all()

    def discard(self) -> dict[str, Any]:
        session = self.store.latest_session(
            statuses={"PREPARING", "READY_FOR_APPROVAL", "FAILED", "STALE"}
        )
        if session is None:
            return {
                "success": False,
                "status": "NOTHING_TO_DISCARD",
                "message": "Nie ma przygotowanej poprawki do odrzucenia.",
            }
        discarded = self.store.discard(session.session_id)
        return {
            "success": True,
            "status": "DISCARDED",
            "message": (
                f"Odrzuciłem przygotowaną poprawkę dla {discarded.target}. "
                "Nie zmieniłem plików projektu."
            ),
            "session": discarded.to_dict(),
        }

    def _attach_campaign_reconciliation(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        response = dict(result or {})
        session = dict(response.get("session", {}) or {})
        metadata = dict(session.get("metadata", {}) or {})
        campaign_id = str(metadata.get("campaign_id", ""))
        if not campaign_id:
            response["campaign_reconciliation"] = {
                "success": True,
                "status": "NOT_A_CAMPAIGN_SESSION",
                "reconciled_changes": 0,
            }
            return response
        try:
            from .autonomous_work_review_service import (
                AutonomousWorkReviewService,
            )

            review = AutonomousWorkReviewService(
                self.project_root,
                safe_development=self,
            ).reconcile_campaign(campaign_id)
            response["campaign_reconciliation"] = {
                "success": bool(review.get("success", False)),
                "status": str(review.get("status", "")),
                "campaign_status": str(
                    dict(review.get("campaign", {}) or {}).get("status", "")
                ),
                "reconciled_changes": int(
                    review.get("reconciled_changes", 0) or 0
                ),
                "manifest_digest": str(review.get("manifest_digest", "")),
            }
        except Exception as error:
            response["campaign_reconciliation"] = {
                "success": False,
                "status": "CAMPAIGN_RECONCILIATION_FAILED",
                "reconciled_changes": 0,
                "error": f"{type(error).__name__}: {error}",
            }
        return response

    @staticmethod
    def _ensure_deadline(deadline_monotonic: float | None) -> None:
        if (
            deadline_monotonic is not None
            and time.monotonic() >= float(deadline_monotonic)
        ):
            raise TimeoutError("Wyczerpano budżet czasu kampanii AutoDev.")

    def _scan_preview(self) -> dict[str, Any]:
        cycle = ProjectOpportunityScanner(
            self.project_root,
            max_files=500,
            max_opportunities=30,
        ).run_cycle()
        prioritization = dict(cycle.get("prioritization", {}) or {})
        selected = prioritization.get("selected")
        preview = dict(selected) if isinstance(selected, dict) else {}
        if preview:
            self.store.record_preview(preview)
        return preview

    def _load_policy(self) -> SafeDevelopmentPolicy:
        path = self.project_root / self.CONFIG
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            limits = dict(raw.get("limits", {}) or {})
            safety = dict(raw.get("safety", {}) or {})
            return SafeDevelopmentPolicy(
                max_changed_files=int(limits.get("max_changed_files", 1)),
                max_changed_lines=int(limits.get("max_changed_lines", 40)),
                max_source_bytes=int(limits.get("max_source_bytes", 900_000)),
                max_sessions=int(limits.get("max_sessions", 20)),
                focused_test_limit=int(limits.get("focused_test_limit", 12)),
                focused_test_timeout_seconds=int(
                    limits.get("focused_test_timeout_seconds", 180)
                ),
                live_test_timeout_seconds=int(
                    limits.get("live_test_timeout_seconds", 180)
                ),
                auto_approve=bool(safety.get("auto_approve", False)),
                auto_deploy=bool(safety.get("auto_deploy", False)),
                auto_rollback=bool(safety.get("auto_rollback", True)),
            )
        except (OSError, ValueError, TypeError):
            return SafeDevelopmentPolicy()

    def _failed_session(
        self,
        session: SafeDevelopmentSession,
        status: str,
        message: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        session.status = "FAILED"
        session.errors.extend(list(result.get("errors", []) or []))
        self.store.save_session(session)
        return {
            "success": False,
            "status": status,
            "message": message + " Nie zmieniłem plików projektu.",
            "session": session.to_dict(),
            "requires_confirmation": False,
            "project_files_modified": False,
        }

    @staticmethod
    def _prepare_message(session: SafeDevelopmentSession) -> str:
        workspace = dict(session.validation.get("workspace", {}) or {})
        tests = dict(workspace.get("tests", {}) or {})
        count = int(tests.get("count", 0) or 0)
        test_text = (
            f"Uruchomiłem {count} testów ukierunkowanych."
            if count else
            "Dla tego pliku nie ma bezpośrednich testów; sprawdziłem składnię i import."
        )
        return "\n".join([
            "Przygotowałem jedną realną poprawkę na izolowanej kopii projektu.",
            f"Poprawka: {session.title}",
            f"Plik: {session.target}",
            f"Powód: {session.rationale}",
            f"Zakres: {session.changed_lines} zmienionych linii, 1 plik.",
            (
                f"Ocena: ryzyko {round(session.risk_score)}/100, "
                f"pewność {round(session.confidence * 100)}%."
            ),
            test_text,
            "Pliki działającego projektu nie zostały zmienione.",
            "Aby wdrożyć tę samą poprawkę, powiedz: „Wdróż przygotowaną poprawkę”.",
        ])

    @staticmethod
    def _status_message(session: SafeDevelopmentSession) -> str:
        labels = {
            "PREPARING": "Poprawka jest przygotowywana.",
            "READY_FOR_APPROVAL": "Poprawka jest gotowa i czeka na decyzję.",
            "DEPLOYING": "Poprawka jest wdrażana.",
            "DEPLOYED": "Poprawka została wdrożona i zweryfikowana.",
            "ROLLED_BACK": "Poprawka została cofnięta.",
            "DISCARDED": "Przygotowana poprawka została odrzucona.",
            "FAILED": "Przygotowanie lub walidacja poprawki nie przeszły.",
            "STALE": "Poprawka jest nieaktualna, bo projekt się zmienił.",
        }
        return (
            f"{labels.get(session.status, session.status)} "
            f"Plik: {session.target}. Sesja: {session.session_id}."
        )
