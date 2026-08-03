from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any, Callable

from app.core.project_paths import resolve_project_root

from .autonomous_work_models import AutonomousWorkPolicy
from .autonomous_work_orchestrator import AutonomousWorkOrchestrator
from .autonomous_work_review_service import AutonomousWorkReviewService
from .autonomous_work_store import AutonomousWorkStore


class AutonomousWorkService:
    """Background lifecycle facade for Autonomous Development 3 campaigns."""

    CONFIG = "config/b221_b230_autonomous_development_3.json"

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: AutonomousWorkPolicy | None = None,
        store: AutonomousWorkStore | None = None,
        orchestrator: Any | None = None,
        review_service: Any | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or self._load_policy()
        self.store = store or AutonomousWorkStore(
            self.project_root,
            policy=self.policy,
        )
        self.orchestrator = orchestrator or AutonomousWorkOrchestrator(
            self.project_root,
            policy=self.policy,
            store=self.store,
        )
        self.review_service = review_service or AutonomousWorkReviewService(
            self.project_root,
            store=self.store,
            safe_development=getattr(self.orchestrator, "safe_development", None),
        )
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._progress_callback: Callable[[dict[str, Any]], None] | None = None

    def start(
        self,
        *,
        max_tasks: int | None = None,
        background: bool = True,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            active = self.store.active()
            if active is not None:
                return self._result(
                    active,
                    success=True,
                    status="CAMPAIGN_ALREADY_ACTIVE",
                    message="AutoDev już pracuje nad aktywną kampanią.",
                )
            campaign = self.store.new_campaign(
                requested_tasks=self.policy.bounded_tasks(max_tasks)
            )
            self._progress_callback = progress_callback
            if background:
                self._start_thread(campaign.campaign_id)
                return self._result(
                    campaign,
                    success=True,
                    status="CAMPAIGN_STARTED",
                    message=(
                        f"Rozpocząłem w tle kampanię do {campaign.requested_tasks} "
                        "kolejnych zadań. Każdy patch zatrzyma się przed wdrożeniem."
                    ),
                )
        return self.orchestrator.run(
            campaign.campaign_id,
            progress_callback=progress_callback,
        )

    def status(self) -> dict[str, Any]:
        campaign = self.store.latest()
        if campaign is None:
            return {
                "success": True,
                "status": "NO_CAMPAIGN",
                "message": "Nie uruchomiono jeszcze kampanii AutoDev 3.",
                "campaign": {},
                "auto_approve": False,
                "auto_deploy": False,
            }
        review = self.review_service.review(campaign.campaign_id)
        result = self._result(
            campaign,
            success=True,
            message=(
                f"Kampania {campaign.campaign_id}: {campaign.status}. "
                f"Gotowe patche: {campaign.prepared_tasks}/"
                f"{campaign.requested_tasks}; błędy: {campaign.failed_tasks}."
            ),
        )
        result["review"] = review
        summary = dict(review.get("summary", {}) or {})
        if summary:
            result["message"] = (
                f"Kampania {campaign.campaign_id}: {campaign.status}. "
                f"Do decyzji: {summary.get('ready', 0)}, "
                f"zablokowane: {summary.get('blocked', 0)}, "
                f"rozstrzygnięte: {summary.get('resolved', 0)}."
            )
        return result

    def review(self, *, patch_index: int | None = None) -> dict[str, Any]:
        return self.review_service.review(patch_index=patch_index)

    def discard_patch(self, *, patch_index: int | None = None) -> dict[str, Any]:
        return self.review_service.discard_patch(patch_index=patch_index)

    def reconcile_review(self) -> dict[str, Any]:
        return self.review_service.reconcile_campaign()

    def resume(
        self,
        *,
        background: bool = True,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self.store.recover_interrupted()
            campaign = self.store.active() or self.store.latest()
            if campaign is None:
                return self.start(
                    background=background,
                    progress_callback=progress_callback,
                )
            if campaign.status == "READY_FOR_APPROVAL":
                return self._result(
                    campaign,
                    success=True,
                    status="CAMPAIGN_ALREADY_READY",
                    message="Kampania jest już gotowa i czeka przed wdrożeniem.",
                )
            if self.store.has_live_lease(campaign.campaign_id):
                return self._result(
                    campaign,
                    success=True,
                    status="CAMPAIGN_ALREADY_ACTIVE",
                    message="Kampania nadal działa w innym procesie roboczym.",
                )
            if self._thread is not None and self._thread.is_alive():
                return self._result(
                    campaign,
                    success=True,
                    status="CAMPAIGN_ALREADY_ACTIVE",
                    message="Kampania nadal działa w tle.",
                )
            if campaign.status not in {"CREATED", "RECOVERING", "RUNNING"}:
                return self._result(
                    campaign,
                    success=False,
                    status="CAMPAIGN_NOT_RESUMABLE",
                    message=f"Kampanii w stanie {campaign.status} nie można wznowić.",
                )
            campaign.status = "RECOVERING"
            self.store.event(campaign, "RESUME_REQUESTED")
            self.store.save(campaign)
            self._progress_callback = progress_callback
            if background:
                self._start_thread(campaign.campaign_id)
                return self._result(
                    campaign,
                    success=True,
                    status="CAMPAIGN_RESUMED",
                    message="Wznowiłem kampanię w tle od ostatniego checkpointu.",
                )
        return self.orchestrator.run(
            campaign.campaign_id,
            progress_callback=progress_callback,
        )

    def cancel(self) -> dict[str, Any]:
        with self._lock:
            campaign = self.store.active() or self.store.latest()
            if campaign is None:
                return {
                    "success": False,
                    "status": "NO_CAMPAIGN",
                    "message": "Nie ma kampanii AutoDev do anulowania.",
                    "auto_approve": False,
                    "auto_deploy": False,
                }
            if campaign.status == "READY_FOR_APPROVAL":
                self._discard_sessions(campaign.prepared_session_ids)
                campaign.status = "CANCELLED"
                campaign.stop_requested = True
                self.store.event(campaign, "READY_PATCHES_DISCARDED")
                self.store.save(campaign)
                return self._result(
                    campaign,
                    success=True,
                    message="Odrzuciłem wyłącznie izolowane patche tej kampanii.",
                )
            if campaign.status not in {"CREATED", "RUNNING", "RECOVERING", "CANCELLING"}:
                return self._result(
                    campaign,
                    success=False,
                    status="CAMPAIGN_NOT_ACTIVE",
                    message="Nie ma aktywnej kampanii do zatrzymania.",
                )
            self.store.request_cancel(campaign)
            return self._result(
                campaign,
                success=True,
                status="CANCELLATION_REQUESTED",
                message=(
                    "Zleciłem bezpieczne zatrzymanie. Bieżąca walidacja dokończy się "
                    "na izolowanej kopii, a kolejne zadanie nie wystartuje."
                ),
            )

    def wait(self, timeout: float | None = None) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _start_thread(self, campaign_id: str) -> None:
        self._thread = threading.Thread(
            target=self._run_background,
            args=(campaign_id,),
            name=f"jarvis-autodev-{campaign_id[-8:]}",
            daemon=True,
        )
        self._thread.start()

    def _run_background(self, campaign_id: str) -> None:
        self.orchestrator.run(
            campaign_id,
            progress_callback=self._progress_callback,
        )

    def _discard_sessions(self, session_ids: list[str]) -> None:
        safe = getattr(self.orchestrator, "safe_development", None)
        store = getattr(safe, "store", None)
        if store is None:
            return
        for session_id in session_ids:
            try:
                session = store.load_session(session_id)
                if session.status != "DEPLOYED":
                    store.discard(session_id)
            except (OSError, TypeError, ValueError):
                continue

    def _load_policy(self) -> AutonomousWorkPolicy:
        path = self.project_root / self.CONFIG
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            limits = dict(value.get("limits", {}) or {})
            safety = dict(value.get("safety", {}) or {})
            return AutonomousWorkPolicy(
                max_tasks=int(limits.get("max_tasks", 5)),
                max_seed_candidates=int(limits.get("max_seed_candidates", 10)),
                max_failures=int(limits.get("max_failures", 2)),
                max_runtime_seconds=int(limits.get("max_runtime_seconds", 3600)),
                lease_seconds=int(limits.get("lease_seconds", 120)),
                max_campaigns=int(limits.get("max_campaigns", 30)),
                max_risk_score=float(limits.get("max_risk_score", 50.0)),
                min_confidence=float(limits.get("min_confidence", 0.75)),
                max_changed_files_per_patch=int(
                    limits.get("max_changed_files_per_patch", 1)
                ),
                max_changed_lines_per_patch=int(
                    limits.get("max_changed_lines_per_patch", 40)
                ),
                auto_approve=bool(safety.get("auto_approve", False)),
                auto_deploy=bool(safety.get("auto_deploy", False)),
            )
        except (OSError, TypeError, ValueError):
            return AutonomousWorkPolicy()

    @staticmethod
    def _result(
        campaign: Any,
        *,
        success: bool,
        message: str,
        status: str | None = None,
    ) -> dict[str, Any]:
        return {
            "success": bool(success),
            "status": str(status or campaign.status),
            "message": str(message),
            "campaign": campaign.to_dict(),
            "project_files_modified": False,
            "auto_approve": False,
            "auto_deploy": False,
        }
