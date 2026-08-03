from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from app.core.project_paths import resolve_project_root

from .autonomous_backlog import AutonomousBacklogReader
from .autonomous_self_seeding import AutonomousBacklogSelfSeeder
from .autonomous_work_models import AutonomousWorkCampaign, AutonomousWorkPolicy
from .autonomous_work_store import AutonomousWorkStore
from .safe_autonomous_development_service import SafeAutonomousDevelopmentService


class AutonomousWorkOrchestrator:
    """Prepare several tested patches while keeping the live source immutable."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: AutonomousWorkPolicy | None = None,
        store: AutonomousWorkStore | None = None,
        backlog: Any | None = None,
        seeder: Any | None = None,
        safe_development: Any | None = None,
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or AutonomousWorkPolicy()
        self.store = store or AutonomousWorkStore(
            self.project_root,
            policy=self.policy,
        )
        self.backlog = backlog or AutonomousBacklogReader(self.project_root)
        self.seeder = seeder or AutonomousBacklogSelfSeeder(self.project_root)
        self.safe_development = safe_development or (
            SafeAutonomousDevelopmentService(self.project_root)
        )
        default_heartbeat = min(
            30.0,
            max(1.0, max(10, self.policy.lease_seconds) / 3.0),
        )
        self.heartbeat_interval_seconds = (
            default_heartbeat
            if heartbeat_interval_seconds is None
            else max(0.01, float(heartbeat_interval_seconds))
        )

    def run(
        self,
        campaign_id: str,
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        campaign = self.store.load(campaign_id)
        token = uuid4().hex
        if not self.store.acquire_lease(campaign, token):
            return self._response(
                campaign,
                success=False,
                status="WORKER_LEASE_ACTIVE",
            )
        started = time.monotonic()
        deadline = started + max(1.0, float(self.policy.max_runtime_seconds))
        heartbeat = _LeaseHeartbeat(
            self.store,
            campaign.campaign_id,
            token,
            interval_seconds=self.heartbeat_interval_seconds,
        )
        try:
            heartbeat.start()
            campaign.status = "RECOVERING" if campaign.recovery_count else "RUNNING"
            if not campaign.source_digest_before:
                campaign.source_digest_before = self._source_digest()
            self.store.event(campaign, "WORKER_STARTED")
            self.store.save(campaign)
            self._recover_inflight(campaign)
            self._seed_backlog(campaign)
            campaign.status = "RUNNING"
            self.store.save(campaign)
            self._notify(progress_callback, campaign, "BACKLOG_READY")

            while campaign.prepared_tasks < campaign.requested_tasks:
                if campaign.stop_requested:
                    campaign.status = "CANCELLED"
                    self.store.event(campaign, "CAMPAIGN_CANCELLED")
                    break
                if campaign.failed_tasks >= self.policy.max_failures:
                    campaign.status = "FAILED"
                    campaign.errors.append("Przekroczono limit nieudanych przygotowań.")
                    break
                if time.monotonic() >= deadline:
                    campaign.status = "RECOVERING"
                    self.store.event(campaign, "RUNTIME_BUDGET_REACHED")
                    break
                if not self.store.renew_lease(campaign, token):
                    campaign.status = "FAILED"
                    campaign.errors.append("Utracono dzierżawę workera AutoDev.")
                    break

                candidate = self._next_candidate(campaign)
                if candidate is None:
                    self._seed_backlog(campaign)
                    candidate = self._next_candidate(campaign)
                if candidate is None:
                    campaign.status = (
                        "READY_FOR_APPROVAL"
                        if campaign.prepared_tasks
                        else "NO_PREPARABLE_TASK"
                    )
                    self.store.event(campaign, "BACKLOG_EXHAUSTED")
                    break
                outcome = self._prepare_candidate(
                    campaign,
                    candidate,
                    progress_callback,
                    deadline_monotonic=deadline,
                )
                if outcome == "RUNTIME_BUDGET_REACHED":
                    campaign.status = "RECOVERING"
                    self.store.event(campaign, "RUNTIME_BUDGET_REACHED")
                    break
                if heartbeat.lost:
                    campaign.status = "SAFETY_VIOLATION"
                    campaign.errors.append(
                        "Utracono dzierżawę workera podczas przygotowania poprawki."
                    )
                    self.store.event(campaign, "WORKER_LEASE_LOST")
                    break

            if heartbeat.lost and campaign.status != "SAFETY_VIOLATION":
                campaign.status = "SAFETY_VIOLATION"
                campaign.errors.append(
                    "Utracono dzierżawę workera AutoDev."
                )
                self.store.event(campaign, "WORKER_LEASE_LOST")
            elif campaign.status == "RUNNING":
                campaign.status = (
                    "READY_FOR_APPROVAL"
                    if campaign.prepared_tasks
                    else "NO_PREPARABLE_TASK"
                )
            campaign.source_digest_after = self._source_digest()
            if campaign.source_digest_after != campaign.source_digest_before:
                campaign.status = "SAFETY_VIOLATION"
                campaign.errors.append(
                    "Hash aktywnych źródeł zmienił się podczas pracy na kopiach."
                )
            campaign.risk_summary = self._risk_summary(campaign)
            self.store.event(campaign, "WORKER_FINISHED", status=campaign.status)
            self.store.save(campaign)
            self._notify(progress_callback, campaign, "FINISHED")
        except Exception as error:
            campaign.status = "FAILED"
            campaign.errors.append(f"{type(error).__name__}: {error}")
            self.store.event(campaign, "WORKER_FAILED")
            self.store.save(campaign)
        finally:
            if campaign.source_digest_before and not campaign.source_digest_after:
                try:
                    campaign.source_digest_after = self._source_digest()
                    if campaign.source_digest_after != campaign.source_digest_before:
                        campaign.status = "SAFETY_VIOLATION"
                        message = "Hash aktywnych źródeł zmienił się podczas pracy."
                        if message not in campaign.errors:
                            campaign.errors.append(message)
                        self.store.event(campaign, "SOURCE_IMMUTABILITY_VIOLATION")
                    campaign.risk_summary = self._risk_summary(campaign)
                    self.store.save(campaign)
                except OSError as error:
                    campaign.status = "SAFETY_VIOLATION"
                    campaign.errors.append(f"Nie udało się sprawdzić źródeł: {error}")
                    self.store.save(campaign)
            heartbeat.stop()
            if heartbeat.lost and campaign.status != "SAFETY_VIOLATION":
                campaign.status = "SAFETY_VIOLATION"
                message = "Utracono dzierżawę workera AutoDev."
                if message not in campaign.errors:
                    campaign.errors.append(message)
                self.store.event(campaign, "WORKER_LEASE_LOST")
                self.store.save(campaign)
            self.store.release_lease(campaign, token)
        return self._response(
            campaign,
            success=campaign.status == "READY_FOR_APPROVAL",
        )

    def _prepare_candidate(
        self,
        campaign: AutonomousWorkCampaign,
        candidate: Any,
        callback: Callable[[dict[str, Any]], None] | None,
        *,
        deadline_monotonic: float,
    ) -> str:
        task = candidate.to_dict()
        fingerprint = str(task.get("fingerprint", ""))
        item = {
            "item_id": "work-item-" + uuid4().hex[:12],
            "status": "PREPARING",
            "task": task,
            "task_fingerprint": fingerprint,
            "safe_session_id": "",
            "risk": {},
            "errors": [],
        }
        campaign.items.append(item)
        campaign.current_task_fingerprint = fingerprint
        self.store.event(
            campaign,
            "TASK_SELECTED",
            task_id=str(task.get("task_id", "")),
            target=str(task.get("target", "")),
        )
        self.store.save(campaign)
        self._notify(callback, campaign, "PREPARING_PATCH")
        prepared = self._prepare_with_deadline(
            self._preview(campaign, item, candidate),
            deadline_monotonic=deadline_monotonic,
        )
        if str(prepared.get("status", "")) == "RUNTIME_BUDGET_REACHED":
            session = dict(prepared.get("session", {}) or {})
            session_id = str(session.get("session_id", ""))
            if session_id:
                self._discard_session(session_id)
            item["status"] = "INTERRUPTED_RETRY_SAFE"
            item["errors"] = ["RUNTIME_BUDGET_REACHED"]
            campaign.current_task_fingerprint = ""
            self.store.event(
                campaign,
                "PATCH_PREPARATION_BUDGET_REACHED",
                target=str(task.get("target", "")),
            )
            self.store.save(campaign)
            self._notify(callback, campaign, item["status"])
            return "RUNTIME_BUDGET_REACHED"
        gate = self._risk_gate(candidate, prepared)
        item["risk"] = gate
        campaign.attempted_fingerprints.append(fingerprint)
        if gate["accepted"]:
            session = dict(prepared.get("session", {}) or {})
            session_id = str(session.get("session_id", ""))
            item.update({
                "status": "READY_FOR_APPROVAL",
                "safe_session_id": session_id,
                "session": session,
            })
            campaign.prepared_tasks += 1
            if session_id not in campaign.prepared_session_ids:
                campaign.prepared_session_ids.append(session_id)
            self.store.event(
                campaign,
                "PATCH_READY_FOR_APPROVAL",
                session_id=session_id,
                target=str(task.get("target", "")),
            )
        else:
            item["status"] = "REJECTED_BY_RISK_GATE"
            item["errors"] = list(gate.get("reasons", []) or [])
            campaign.failed_tasks += 1
            self.store.event(
                campaign,
                "PATCH_REJECTED",
                reasons=item["errors"],
            )
        campaign.current_task_fingerprint = ""
        self.store.save(campaign)
        self._notify(callback, campaign, item["status"])
        return str(item["status"])

    def _prepare_with_deadline(
        self,
        preview: dict[str, Any],
        *,
        deadline_monotonic: float,
    ) -> dict[str, Any]:
        prepare = self.safe_development.prepare
        try:
            parameters = inspect.signature(prepare).parameters.values()
            accepts_deadline = any(
                item.name == "deadline_monotonic"
                or item.kind is inspect.Parameter.VAR_KEYWORD
                for item in parameters
            )
        except (TypeError, ValueError):
            accepts_deadline = False
        if accepts_deadline:
            return prepare(
                preview=preview,
                deadline_monotonic=deadline_monotonic,
            )
        return prepare(preview=preview)

    def _discard_session(self, session_id: str) -> None:
        store = getattr(self.safe_development, "store", None)
        if store is None:
            return
        try:
            session = store.load_session(session_id)
            if session.status != "DEPLOYED":
                store.discard(session_id)
        except (OSError, TypeError, ValueError):
            return

    def _recover_inflight(self, campaign: AutonomousWorkCampaign) -> None:
        inflight = [
            item for item in campaign.items
            if str(item.get("status", "")) == "PREPARING"
        ]
        if not inflight:
            return
        latest = self.safe_development.store.latest_session()
        for item in inflight:
            fingerprint = str(item.get("task_fingerprint", ""))
            metadata = dict(getattr(latest, "metadata", {}) or {})
            matches = bool(
                latest is not None
                and metadata.get("campaign_id") == campaign.campaign_id
                and metadata.get("work_task_fingerprint") == fingerprint
            )
            if matches and latest.status == "READY_FOR_APPROVAL":
                prepared = {"success": True, "session": latest.to_dict()}
                task = dict(item.get("task", {}) or {})
                candidate = _RecoveredCandidate(task)
                gate = self._risk_gate(candidate, prepared)
                item["risk"] = gate
                if gate["accepted"]:
                    item["status"] = "READY_FOR_APPROVAL"
                    item["safe_session_id"] = latest.session_id
                    item["session"] = latest.to_dict()
                    campaign.prepared_tasks += 1
                    campaign.attempted_fingerprints.append(fingerprint)
                    if latest.session_id not in campaign.prepared_session_ids:
                        campaign.prepared_session_ids.append(latest.session_id)
                    continue
            if matches and latest is not None and latest.status != "DEPLOYED":
                try:
                    self.safe_development.store.discard(latest.session_id)
                except (OSError, TypeError, ValueError):
                    pass
            item["status"] = "INTERRUPTED_RETRY_SAFE"
        campaign.current_task_fingerprint = ""
        self.store.event(campaign, "INFLIGHT_TASKS_RECONCILED", count=len(inflight))
        self.store.save(campaign)

    def _seed_backlog(self, campaign: AutonomousWorkCampaign) -> None:
        excluded = set(campaign.attempted_fingerprints)
        excluded.update(self.store.excluded_fingerprints(
            except_campaign_id=campaign.campaign_id
        ))
        result = self.seeder.seed_many(
            limit=self.policy.max_seed_candidates,
            excluded_fingerprints=excluded,
        )
        for task in list(result.get("tasks", []) or []):
            task_id = str(task.get("task_id", ""))
            if task_id and task_id not in campaign.seeded_task_ids:
                campaign.seeded_task_ids.append(task_id)
        self.store.event(
            campaign,
            "BACKLOG_ANALYZED",
            files_scanned=int(result.get("files_scanned", 0) or 0),
            tasks_seeded=len(list(result.get("tasks", []) or [])),
        )
        self.store.save(campaign)

    def _next_candidate(self, campaign: AutonomousWorkCampaign) -> Any | None:
        excluded = set(campaign.attempted_fingerprints)
        excluded.update(self.store.excluded_fingerprints(
            except_campaign_id=campaign.campaign_id
        ))
        excluded.update(
            str(item.get("task_fingerprint", ""))
            for item in campaign.items
            if str(item.get("status", "")) == "READY_FOR_APPROVAL"
        )
        candidates = self.backlog.candidates(excluded_fingerprints=excluded)
        return candidates[0] if candidates else None

    def _preview(
        self,
        campaign: AutonomousWorkCampaign,
        item: dict[str, Any],
        candidate: Any,
    ) -> dict[str, Any]:
        return {
            "task": {
                "target": candidate.target,
                "title": candidate.title,
                "description": candidate.description,
                "metadata": {
                    **dict(candidate.metadata),
                    "issue_type": candidate.issue_type,
                    "campaign_id": campaign.campaign_id,
                    "work_item_id": item["item_id"],
                    "work_task_fingerprint": candidate.fingerprint,
                    "require_exact_target": True,
                },
            },
            "predicted_risk": candidate.risk_score,
            "effort_score": candidate.effort_score,
            "confidence": candidate.confidence,
            "backlog_task": candidate.to_dict(),
        }

    def _risk_gate(self, candidate: Any, prepared: dict[str, Any]) -> dict[str, Any]:
        reasons: list[str] = []
        session = dict(prepared.get("session", {}) or {})
        validation = dict(session.get("validation", {}) or {})
        static = dict(validation.get("static", {}) or {})
        workspace = dict(validation.get("workspace", {}) or {})
        metadata = dict(session.get("metadata", {}) or {})
        if not prepared.get("success", False):
            reasons.append(str(prepared.get("status", "PREPARATION_FAILED")))
        if bool(prepared.get("project_files_modified", False)):
            reasons.append("LIVE_PROJECT_MODIFICATION_FORBIDDEN")
        if str(session.get("status", "")) != "READY_FOR_APPROVAL":
            reasons.append("PATCH_NOT_APPROVAL_READY")
        if float(candidate.risk_score) > self.policy.max_risk_score:
            reasons.append("CANDIDATE_RISK_LIMIT")
        if float(candidate.confidence) < self.policy.min_confidence:
            reasons.append("CANDIDATE_CONFIDENCE_LIMIT")
        changed_files = list(session.get("changed_files", []) or [])
        if changed_files != [str(candidate.target)]:
            reasons.append("EXACT_TARGET_MISMATCH")
        if len(changed_files) > (
            self.policy.max_changed_files_per_patch
        ):
            reasons.append("CHANGED_FILE_LIMIT")
        if int(session.get("changed_lines", 0) or 0) > (
            self.policy.max_changed_lines_per_patch
        ):
            reasons.append("CHANGED_LINE_LIMIT")
        if not static.get("success", False):
            reasons.append("STATIC_VALIDATION_FAILED")
        if not workspace.get("success", False):
            reasons.append("WORKSPACE_VALIDATION_FAILED")
        tests = dict(workspace.get("tests", {}) or {})
        if not tests.get("success", False) or int(tests.get("count", 0) or 0) < 1:
            reasons.append("FOCUSED_TESTS_FAILED")
        expected_hash = str(dict(candidate.metadata).get("source_hash", ""))
        if expected_hash and str(session.get("source_hash", "")) != expected_hash:
            reasons.append("SOURCE_HASH_MISMATCH")
        if any((
            bool(prepared.get("auto_approve", False)),
            bool(session.get("auto_approve", False)),
            bool(metadata.get("automatic_approval", False)),
            bool(self.policy.auto_approve),
        )):
            reasons.append("AUTOMATIC_APPROVAL_FORBIDDEN")
        if any((
            bool(prepared.get("auto_deploy", False)),
            bool(session.get("auto_deploy", False)),
            bool(metadata.get("automatic_deployment", False)),
            bool(self.policy.auto_deploy),
        )):
            reasons.append("AUTOMATIC_DEPLOYMENT_FORBIDDEN")
        return {
            "accepted": not reasons,
            "reasons": reasons,
            "candidate_risk": float(candidate.risk_score),
            "confidence": float(candidate.confidence),
            "changed_files": len(changed_files),
            "changed_lines": int(session.get("changed_lines", 0) or 0),
            "tests": int(tests.get("count", 0) or 0),
            "auto_approve": False,
            "auto_deploy": False,
        }

    def _source_digest(self) -> str:
        digest = hashlib.sha256()
        paths: set[Path] = set()
        for name in ("app", "config", "tools", "scripts", "tests"):
            root = self.project_root / name
            if root.is_dir():
                paths.update(path for path in root.rglob("*") if path.is_file())
        paths.update(path for path in self.project_root.glob("*") if path.is_file())
        ignored = {"__pycache__", ".pytest_cache", ".git", ".venv"}
        for path in sorted(paths):
            if any(part in ignored for part in path.parts) or path.is_symlink():
                continue
            relative = path.relative_to(self.project_root).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    @staticmethod
    def _risk_summary(campaign: AutonomousWorkCampaign) -> dict[str, Any]:
        accepted = [
            dict(item.get("risk", {}) or {})
            for item in campaign.items
            if str(item.get("status", "")) == "READY_FOR_APPROVAL"
        ]
        return {
            "prepared_patches": len(accepted),
            "total_tests": sum(int(item.get("tests", 0) or 0) for item in accepted),
            "max_candidate_risk": max(
                [float(item.get("candidate_risk", 0.0)) for item in accepted]
                or [0.0]
            ),
            "auto_approve": False,
            "auto_deploy": False,
            "project_sources_unchanged": (
                campaign.source_digest_before == campaign.source_digest_after
            ),
        }

    @staticmethod
    def _notify(
        callback: Callable[[dict[str, Any]], None] | None,
        campaign: AutonomousWorkCampaign,
        phase: str,
    ) -> None:
        if not callable(callback):
            return
        try:
            callback({
                "campaign_id": campaign.campaign_id,
                "phase": phase,
                "status": campaign.status,
                "prepared_tasks": campaign.prepared_tasks,
                "requested_tasks": campaign.requested_tasks,
            })
        except Exception:
            return

    @staticmethod
    def _response(
        campaign: AutonomousWorkCampaign,
        *,
        success: bool,
        status: str | None = None,
    ) -> dict[str, Any]:
        modified = bool(
            campaign.source_digest_before
            and campaign.source_digest_after
            and campaign.source_digest_before != campaign.source_digest_after
        )
        return {
            "success": bool(success),
            "status": str(status or campaign.status),
            "campaign": campaign.to_dict(),
            "project_files_modified": modified,
            "auto_approve": False,
            "auto_deploy": False,
        }


class _LeaseHeartbeat:
    def __init__(
        self,
        store: AutonomousWorkStore,
        campaign_id: str,
        token: str,
        *,
        interval_seconds: float,
    ) -> None:
        self.store = store
        self.campaign_id = campaign_id
        self.token = token
        self.interval_seconds = max(0.01, float(interval_seconds))
        self._stop = threading.Event()
        self._lost = threading.Event()
        self._started = False
        self._thread = threading.Thread(
            target=self._run,
            name=f"jarvis-autodev-heartbeat-{campaign_id[-8:]}",
            daemon=True,
        )

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    def start(self) -> None:
        self._thread.start()
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.interval_seconds * 2.0))

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                renewed = self.store.heartbeat_lease(
                    self.campaign_id,
                    self.token,
                )
            except Exception:
                renewed = False
            if not renewed:
                self._lost.set()
                return


class _RecoveredCandidate:
    def __init__(self, task: dict[str, Any]) -> None:
        self._task = dict(task)
        self.target = str(task.get("target", ""))
        self.risk_score = float(task.get("risk_score", 100.0))
        self.confidence = float(task.get("confidence", 0.0))
        self.metadata = dict(task.get("metadata", {}) or {})
