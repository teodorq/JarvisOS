from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root

from .autonomous_work_store import AutonomousWorkStore
from .safe_autonomous_development_service import SafeAutonomousDevelopmentService


class AutonomousWorkReviewService:
    """Read-only integrity review and exact discard for campaign patches."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        store: AutonomousWorkStore | None = None,
        safe_development: Any | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.store = store or AutonomousWorkStore(self.project_root)
        self.safe_development = safe_development or (
            SafeAutonomousDevelopmentService(self.project_root)
        )

    def review(
        self,
        campaign_id: str = "",
        *,
        patch_index: int | None = None,
    ) -> dict[str, Any]:
        campaign = self._campaign(campaign_id)
        if campaign is None:
            return self._empty("NO_CAMPAIGN", "Nie ma kampanii AutoDev do przeglądu.")

        items = self._reviewable_items(campaign)
        patches = [
            self._review_item(campaign, item, index)
            for index, item in enumerate(items, start=1)
        ]
        ready_targets = Counter(
            patch["target"] for patch in patches
            if patch["session_status"] == "READY_FOR_APPROVAL"
            and patch["target"]
        )
        for patch in patches:
            if ready_targets[patch["target"]] > 1:
                self._block(patch, "TARGET_CONFLICT_IN_CAMPAIGN")
            patch["blockers"] = sorted(set(patch["blockers"]))
            if patch["session_status"] == "READY_FOR_APPROVAL":
                patch["review_status"] = (
                    "BLOCKED" if patch["blockers"] else "READY"
                )
            else:
                patch["review_status"] = patch["session_status"] or "BLOCKED"
            patch["eligible_for_confirmation"] = (
                patch["review_status"] == "READY"
            )

        manifest = {
            "schema_version": 1,
            "campaign_id": campaign.campaign_id,
            "campaign_status": campaign.status,
            "patches": [self._manifest_patch(patch) for patch in patches],
            "auto_approve": False,
            "auto_deploy": False,
        }
        digest = hashlib.sha256(
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        counts = Counter(patch["review_status"] for patch in patches)
        ready = counts.get("READY", 0)
        blocked = counts.get("BLOCKED", 0)
        resolved = sum(
            counts.get(status, 0)
            for status in ("DEPLOYED", "ROLLED_BACK", "DISCARDED", "STALE", "FAILED")
        )
        status = self._review_status(
            campaign.status,
            patches=len(patches),
            ready=ready,
            blocked=blocked,
            resolved=resolved,
        )
        selection: dict[str, Any] = {}
        if patch_index is not None:
            selection = next(
                (patch for patch in patches if patch["patch_index"] == int(patch_index)),
                {},
            )
            if not selection:
                return {
                    **self._empty(
                        "PATCH_NOT_FOUND",
                        f"Kampania nie ma poprawki numer {patch_index}.",
                    ),
                    "campaign": campaign.to_dict(),
                    "patches": patches,
                    "manifest_digest": digest,
                }
        return {
            "success": True,
            "status": status,
            "message": self._message(
                campaign.campaign_id,
                ready=ready,
                blocked=blocked,
                resolved=resolved,
                selection=selection,
            ),
            "campaign": campaign.to_dict(),
            "patches": patches,
            "selection": selection,
            "summary": {
                "patches": len(patches),
                "ready": ready,
                "blocked": blocked,
                "resolved": resolved,
                "states": dict(sorted(counts.items())),
            },
            "manifest_digest": digest,
            "reviewed_at": self._now(),
            "project_files_modified": False,
            "auto_approve": False,
            "auto_deploy": False,
        }

    def discard_patch(
        self,
        campaign_id: str = "",
        *,
        patch_index: int | None = None,
    ) -> dict[str, Any]:
        campaign = self._campaign(campaign_id)
        if campaign is None:
            return self._empty("NO_CAMPAIGN", "Nie ma kampanii AutoDev do zmiany.")
        items = self._reviewable_items(campaign)
        if patch_index is None:
            if len(items) != 1:
                return self._empty(
                    "PATCH_SELECTION_REQUIRED",
                    "Wskaż numer jednej poprawki. Nie odrzuciłem żadnej z nich.",
                )
            selected_index = 1
        else:
            selected_index = int(patch_index)
        if selected_index < 1 or selected_index > len(items):
            return self._empty(
                "PATCH_NOT_FOUND",
                f"Kampania nie ma poprawki numer {selected_index}.",
            )

        item = items[selected_index - 1]
        session_id = str(item.get("safe_session_id", ""))
        try:
            session = self.safe_development.store.load_session(session_id)
        except (AttributeError, OSError, TypeError, ValueError) as error:
            return self._empty("PATCH_SESSION_UNAVAILABLE", str(error))
        metadata = dict(getattr(session, "metadata", {}) or {})
        if (
            metadata.get("campaign_id") != campaign.campaign_id
            or metadata.get("work_item_id") != item.get("item_id")
            or metadata.get("work_task_fingerprint") != item.get("task_fingerprint")
        ):
            return self._empty(
                "PATCH_OWNERSHIP_MISMATCH",
                "Sesja nie należy dokładnie do wybranej poprawki kampanii.",
            )
        session_status = str(getattr(session, "status", ""))
        if session_status == "DEPLOYED":
            return self._empty(
                "DEPLOYED_PATCH_CANNOT_BE_DISCARDED",
                "Wdrożonej poprawki nie można odrzucić; wymaga osobnego cofnięcia.",
            )
        if session_status == "DISCARDED":
            return self._empty(
                "PATCH_ALREADY_DISCARDED",
                "Ta poprawka została już odrzucona.",
            )
        if session_status not in {
            "PREPARING", "READY_FOR_APPROVAL", "FAILED", "STALE",
        }:
            return self._empty(
                "PATCH_NOT_DISCARDABLE",
                f"Poprawki w stanie {session_status} nie można odrzucić.",
            )
        try:
            discarded = self.safe_development.store.discard(session_id)
        except (OSError, TypeError, ValueError) as error:
            return self._empty("PATCH_DISCARD_FAILED", str(error))

        item["status"] = "DISCARDED"
        item["session"] = discarded.to_dict()
        self.store.event(
            campaign,
            "PATCH_DISCARDED_BY_OWNER",
            patch_index=selected_index,
            session_id=session_id,
        )
        if not self._has_ready_session(campaign):
            campaign.status = "REVIEW_COMPLETED"
            self.store.event(campaign, "CAMPAIGN_REVIEW_COMPLETED")
        self.store.save(campaign)
        result = self.review(campaign.campaign_id, patch_index=selected_index)
        result.update({
            "success": True,
            "status": "PATCH_DISCARDED",
            "message": (
                f"Odrzuciłem wyłącznie poprawkę numer {selected_index} "
                f"({discarded.target}). Działający projekt pozostał bez zmian."
            ),
            "discarded_session_id": session_id,
            "project_files_modified": False,
            "auto_approve": False,
            "auto_deploy": False,
        })
        return result

    def reconcile_campaign(self, campaign_id: str = "") -> dict[str, Any]:
        """Persist exact external session outcomes without changing project sources."""
        campaign = self._campaign(campaign_id)
        if campaign is None:
            return self._empty("NO_CAMPAIGN", "Nie ma kampanii AutoDev do uzgodnienia.")
        changed = 0
        observed: list[str] = []
        verified_receipts = 0
        for item in self._reviewable_items(campaign):
            session_id = str(item.get("safe_session_id", ""))
            if not session_id:
                continue
            try:
                session = self.safe_development.store.load_session(session_id)
            except (AttributeError, OSError, TypeError, ValueError):
                continue
            metadata = dict(getattr(session, "metadata", {}) or {})
            if (
                metadata.get("campaign_id") != campaign.campaign_id
                or metadata.get("work_item_id") != item.get("item_id")
                or metadata.get("work_task_fingerprint")
                != item.get("task_fingerprint")
            ):
                continue
            session_status = str(getattr(session, "status", ""))
            deployment_service = getattr(
                self.safe_development,
                "deployment",
                None,
            )
            ensure_receipts = getattr(
                deployment_service,
                "ensure_receipts",
                None,
            )
            if callable(ensure_receipts) and session_status in {
                "DEPLOYED", "ROLLED_BACK",
            }:
                try:
                    ensure_receipts(session_id)
                    session = self.safe_development.store.load_session(session_id)
                except (OSError, TypeError, ValueError):
                    pass
            observed.append(session_status)
            session_value = session.to_dict()
            if (
                str(item.get("status", "")) != session_status
                or dict(item.get("session", {}) or {}) != session_value
            ):
                item["status"] = session_status
                item["session"] = session_value
                changed += 1
            receipt = (
                dict(session_value.get("deployment", {}) or {}).get("receipt", {})
                if session_status == "DEPLOYED"
                else dict(session_value.get("rollback", {}) or {}).get("receipt", {})
            )
            verify_receipt = getattr(
                deployment_service,
                "verify_receipt",
                None,
            )
            if receipt and callable(verify_receipt) and verify_receipt(receipt):
                verified_receipts += 1

        terminal = {"DEPLOYED", "ROLLED_BACK", "DISCARDED", "FAILED", "STALE"}
        next_status = campaign.status
        if observed and all(status in terminal for status in observed):
            if campaign.status not in {"CANCELLED", "SAFETY_VIOLATION"}:
                next_status = "REVIEW_COMPLETED"
        elif any(status == "READY_FOR_APPROVAL" for status in observed):
            if campaign.status == "REVIEW_COMPLETED":
                next_status = "READY_FOR_APPROVAL"
        if campaign.status != next_status:
            campaign.status = next_status
            changed += 1

        outcomes = Counter(observed)
        resolution_summary = {
            "review_outcomes": dict(sorted(outcomes.items())),
            "ready_patches": outcomes.get("READY_FOR_APPROVAL", 0),
            "deployed_patches": outcomes.get("DEPLOYED", 0),
            "rolled_back_patches": outcomes.get("ROLLED_BACK", 0),
            "discarded_patches": outcomes.get("DISCARDED", 0),
            "resolved_patches": sum(
                outcomes.get(status, 0) for status in terminal
            ),
            "campaign_review_completed": next_status == "REVIEW_COMPLETED",
            "verified_terminal_receipts": verified_receipts,
        }
        risk_summary = dict(campaign.risk_summary or {})
        if any(
            risk_summary.get(key) != value
            for key, value in resolution_summary.items()
        ):
            risk_summary.update(resolution_summary)
            campaign.risk_summary = risk_summary
            changed += 1
        if changed:
            self.store.event(
                campaign,
                "CAMPAIGN_SESSION_STATES_RECONCILED",
                changed=changed,
                observed_states=dict(sorted(Counter(observed).items())),
            )
            self.store.save(campaign)
        result = self.review(campaign.campaign_id)
        result["reconciled_changes"] = changed
        return result

    def _review_item(
        self,
        campaign: Any,
        item: dict[str, Any],
        patch_index: int,
    ) -> dict[str, Any]:
        task = dict(item.get("task", {}) or {})
        session_id = str(item.get("safe_session_id", ""))
        patch = {
            "patch_index": patch_index,
            "item_id": str(item.get("item_id", "")),
            "session_id": session_id,
            "title": str(task.get("title", "")),
            "target": str(task.get("target", "")),
            "session_status": "",
            "review_status": "BLOCKED",
            "changed_lines": 0,
            "tests": 0,
            "risk_score": float(task.get("risk_score", 0.0) or 0.0),
            "confidence": float(task.get("confidence", 0.0) or 0.0),
            "blockers": [],
            "eligible_for_confirmation": False,
            "requires_owner_confirmation": True,
        }
        try:
            session = self.safe_development.store.load_session(session_id)
        except (AttributeError, OSError, TypeError, ValueError):
            self._block(patch, "SESSION_MISSING")
            return patch

        session_value = session.to_dict()
        metadata = dict(session_value.get("metadata", {}) or {})
        validation = dict(session_value.get("validation", {}) or {})
        workspace_validation = dict(validation.get("workspace", {}) or {})
        tests = dict(workspace_validation.get("tests", {}) or {})
        patch.update({
            "session_status": str(session_value.get("status", "")),
            "changed_lines": int(session_value.get("changed_lines", 0) or 0),
            "tests": int(tests.get("count", 0) or 0),
            "risk_score": float(session_value.get("risk_score", 0.0) or 0.0),
            "confidence": float(session_value.get("confidence", 0.0) or 0.0),
        })
        if str(session_value.get("target", "")) != patch["target"]:
            self._block(patch, "TARGET_MISMATCH")
        if list(session_value.get("changed_files", []) or []) != [patch["target"]]:
            self._block(patch, "CHANGED_FILES_MISMATCH")
        if metadata.get("campaign_id") != campaign.campaign_id:
            self._block(patch, "CAMPAIGN_OWNERSHIP_MISMATCH")
        if metadata.get("work_item_id") != patch["item_id"]:
            self._block(patch, "WORK_ITEM_OWNERSHIP_MISMATCH")
        if metadata.get("work_task_fingerprint") != item.get("task_fingerprint"):
            self._block(patch, "TASK_OWNERSHIP_MISMATCH")
        if bool(metadata.get("automatic_approval", False)):
            self._block(patch, "AUTOMATIC_APPROVAL_FORBIDDEN")
        if bool(metadata.get("automatic_deployment", False)):
            self._block(patch, "AUTOMATIC_DEPLOYMENT_FORBIDDEN")
        if not str(session_value.get("fingerprint", "")):
            self._block(patch, "CONFIRMATION_FINGERPRINT_MISSING")

        if patch["session_status"] == "READY_FOR_APPROVAL":
            self._check_live_source(patch, session_value)
            workspace = getattr(self.safe_development, "workspace", None)
            verify = getattr(workspace, "verify_artifacts", None)
            if not callable(verify):
                self._block(patch, "ARTIFACT_VERIFIER_UNAVAILABLE")
            else:
                try:
                    verify(session)
                except (OSError, TypeError, ValueError):
                    self._block(patch, "ARTIFACT_INTEGRITY_FAILED")
        return patch

    def _check_live_source(
        self,
        patch: dict[str, Any],
        session: dict[str, Any],
    ) -> None:
        try:
            target = (self.project_root / Path(patch["target"])).resolve(strict=False)
            target.relative_to(self.project_root)
            if not target.is_file() or target.is_symlink():
                raise ValueError("unsafe target")
            current_hash = hashlib.sha256(
                target.read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest()
            if not session.get("source_hash") or current_hash != session.get("source_hash"):
                self._block(patch, "SOURCE_CHANGED")
        except (OSError, UnicodeError, ValueError):
            self._block(patch, "LIVE_TARGET_UNAVAILABLE")

    def _has_ready_session(self, campaign: Any) -> bool:
        for item in campaign.items:
            session_id = str(item.get("safe_session_id", ""))
            if not session_id:
                continue
            try:
                session = self.safe_development.store.load_session(session_id)
            except (AttributeError, OSError, TypeError, ValueError):
                continue
            if str(getattr(session, "status", "")) == "READY_FOR_APPROVAL":
                return True
        return False

    @staticmethod
    def _reviewable_items(campaign: Any) -> list[dict[str, Any]]:
        states = {
            "PREPARING", "READY_FOR_APPROVAL", "DEPLOYED", "ROLLED_BACK",
            "DISCARDED", "FAILED", "STALE",
        }
        return [
            item for item in campaign.items
            if str(item.get("safe_session_id", "")).strip()
            or str(item.get("status", "")) in states
        ]

    def _campaign(self, campaign_id: str) -> Any | None:
        if campaign_id:
            try:
                return self.store.load(campaign_id)
            except (OSError, TypeError, ValueError):
                return None
        return self.store.latest()

    @staticmethod
    def _block(patch: dict[str, Any], reason: str) -> None:
        patch["blockers"].append(str(reason))

    @staticmethod
    def _manifest_patch(patch: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "patch_index", "item_id", "session_id", "title", "target",
            "session_status", "review_status", "changed_lines", "tests",
            "risk_score", "confidence", "blockers",
            "eligible_for_confirmation", "requires_owner_confirmation",
        )
        return {key: patch[key] for key in keys}

    @staticmethod
    def _review_status(
        campaign_status: str,
        *,
        patches: int,
        ready: int,
        blocked: int,
        resolved: int,
    ) -> str:
        if campaign_status in {"RUNNING", "RECOVERING", "CANCELLING"}:
            return "CAMPAIGN_REVIEW_IN_PROGRESS"
        if not patches:
            return "CAMPAIGN_NO_PATCHES"
        if blocked:
            return "CAMPAIGN_REVIEW_BLOCKED"
        if ready and resolved:
            return "CAMPAIGN_REVIEW_PARTIAL"
        if ready:
            return "CAMPAIGN_REVIEW_READY"
        return "CAMPAIGN_REVIEW_COMPLETED"

    @staticmethod
    def _message(
        campaign_id: str,
        *,
        ready: int,
        blocked: int,
        resolved: int,
        selection: dict[str, Any],
    ) -> str:
        if selection:
            return (
                f"Poprawka {selection['patch_index']}: {selection['target']}; "
                f"stan {selection['review_status']}; zmienione linie "
                f"{selection['changed_lines']}; testy {selection['tests']}. "
                "Nie wdrożyłem żadnej zmiany."
            )
        return (
            f"Przegląd kampanii {campaign_id}: gotowe {ready}, "
            f"zablokowane {blocked}, rozstrzygnięte {resolved}. "
            "Nie wdrożyłem żadnej zmiany."
        )

    @staticmethod
    def _empty(status: str, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "message": message,
            "patches": [],
            "project_files_modified": False,
            "auto_approve": False,
            "auto_deploy": False,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
