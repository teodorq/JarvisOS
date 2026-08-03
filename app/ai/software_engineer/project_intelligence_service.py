from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import threading
import traceback
from typing import Any

from .project_intelligence_scanner import ProjectOpportunityScanner
from .long_running_autonomy_service import LongRunningAutonomyService
from .project_intelligence_models import (
    ACTIVE_OPPORTUNITY_STATES,
    ProjectOpportunity,
)
from .project_intelligence_ranker import ProjectOpportunityRanker
from .project_intelligence_store import ProjectIntelligenceStore


class ProjectIntelligenceService:
    """B55 self-directed project scanning, backlog and safe dispatch."""

    JOB_STATE_MAP = {
        "QUEUED": "DISPATCHED",
        "SCHEDULED": "DISPATCHED",
        "RECOVERING": "RUNNING",
        "RUNNING": "RUNNING",
        "WAITING_APPROVAL": "WAITING_APPROVAL",
        "WAITING_RESOURCES": "WAITING_RESOURCES",
        "PAUSED": "PAUSED",
        "COMPLETED": "COMPLETED",
        "FAILED": "FAILED",
        "CANCELLED": "CANCELLED",
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        intelligence: Any | None = None,
        long_running_service: LongRunningAutonomyService | Any | None = None,
        store: ProjectIntelligenceStore | None = None,
        ranker: ProjectOpportunityRanker | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.intelligence = intelligence or ProjectOpportunityScanner(
            self.project_root
        )
        self.long_running_service = (
            long_running_service
            or LongRunningAutonomyService(self.project_root)
        )
        self.store = store or ProjectIntelligenceStore(self.project_root)
        self.ranker = ranker or ProjectOpportunityRanker()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def scan_project(self) -> dict[str, Any]:
        with self._lock:
            try:
                cycle = self.intelligence.run_cycle()
                candidates = self._extract_candidates(cycle)
                created = 0
                updated = 0
                saved: list[dict[str, Any]] = []
                for candidate in candidates:
                    candidate_value = (
                        candidate.to_dict()
                        if isinstance(candidate, ProjectOpportunity)
                        else dict(candidate)
                    )
                    existing = self.store.find_by_fingerprint(
                        str(candidate_value.get("fingerprint", ""))
                    )
                    result = self.store.upsert_by_fingerprint(
                        candidate_value
                    )
                    created += int(existing is None)
                    updated += int(existing is not None)
                    saved.append(result)
                runtime = self.store.runtime()
                self.store.update_runtime({
                    "last_scan_at": self._now(),
                    "last_error": "",
                    "cycles_completed": int(
                        runtime.get("cycles_completed", 0)
                    ) + 1,
                })
                response = self._response(
                    "PROJECT_INTELLIGENCE_SCAN_COMPLETED",
                    success=bool(cycle.get("success", True)),
                    scanned=len(candidates),
                    created=created,
                    updated=updated,
                    opportunities=saved[:50],
                )
                self.store.record_cycle({
                    **response,
                    "selected_id": "",
                    "dispatched_job_id": "",
                })
                return response
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                self.store.update_runtime({
                    "last_error": message,
                    "last_scan_at": self._now(),
                })
                response = self._response(
                    "PROJECT_INTELLIGENCE_SCAN_FAILED",
                    success=False,
                    errors=[message],
                    traceback=traceback.format_exc()[-12000:],
                )
                self.store.record_cycle(response)
                return response

    def select_best(self) -> dict[str, Any]:
        policy = self.store.policy()
        selected = self.ranker.select_best(
            self.store.list_opportunities(limit=1000),
            min_score=float(policy.get("min_score", 25.0)),
            max_risk=float(policy.get("max_risk", 65.0)),
            min_confidence=float(policy.get("min_confidence", 0.30)),
        )
        return self._response(
            (
                "PROJECT_INTELLIGENCE_BEST_SELECTED"
                if selected is not None
                else "PROJECT_INTELLIGENCE_NO_SAFE_CANDIDATE"
            ),
            success=True,
            selected=selected or {},
        )

    def dispatch_best(
        self,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            blocked = self._dispatch_guard(force=force)
            if blocked is not None:
                return blocked
            selected_response = self.select_best()
            selected = selected_response.get("selected", {})
            if not isinstance(selected, dict) or not selected:
                return selected_response
            return self._dispatch_selected(selected)

    def dispatch_opportunity(
        self,
        opportunity_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            blocked = self._dispatch_guard(force=force)
            if blocked is not None:
                return blocked
            item = self.store.get_opportunity(opportunity_id)
            if item is None:
                return self._not_found(opportunity_id)
            policy = self.store.policy()
            selected = self.ranker.select_best(
                [item],
                min_score=float(policy.get("min_score", 25.0)),
                max_risk=float(policy.get("max_risk", 65.0)),
                min_confidence=float(policy.get("min_confidence", 0.30)),
            )
            if selected is None:
                return self._response(
                    "PROJECT_INTELLIGENCE_NO_SAFE_CANDIDATE",
                    success=True,
                    selected={},
                )
            return self._dispatch_selected(selected)

    def _dispatch_guard(
        self,
        *,
        force: bool,
    ) -> dict[str, Any] | None:
        self.reconcile()
        policy = self.store.policy()
        active = self._active_opportunities()
        if len(active) >= int(policy.get("max_active_jobs", 1)):
            return self._response(
                "PROJECT_INTELLIGENCE_ACTIVE_LIMIT",
                success=False,
                errors=["Osiągnięto limit aktywnych zadań B55."],
            )
        if not force and not bool(policy.get("auto_dispatch", False)):
            return self._response(
                "PROJECT_INTELLIGENCE_AUTO_DISPATCH_DISABLED",
                success=False,
                errors=[
                    "Automatyczne uruchamianie jest wyłączone. "
                    "Użyj jawnego polecenia uruchomienia najlepszego zadania."
                ],
            )
        return None

    def _dispatch_selected(
        self,
        selected: dict[str, Any],
    ) -> dict[str, Any]:
        policy = self.store.policy()
        opportunity_id = str(selected.get("opportunity_id", ""))
        objective = str(selected.get("objective", "")).strip()
        if not objective:
            return self._response(
                "PROJECT_INTELLIGENCE_INVALID_OBJECTIVE",
                success=False,
                selected=selected,
                errors=["Wybrane zadanie nie ma celu wykonania."],
            )
        execution_targets = self._execution_targets(selected)
        if len(execution_targets) < 2:
            error = (
                "Nie znaleziono drugiego bezpiecznie powiązanego pliku "
                "dla zadania B55."
            )
            saved = self.store.update_opportunity(
                opportunity_id,
                {
                    "status": "FAILED",
                    "attempts": int(selected.get("attempts", 0) or 0) + 1,
                    "last_error": error,
                    "completed_at": self._now(),
                },
            )
            return self._response(
                "PROJECT_INTELLIGENCE_SCOPE_UNAVAILABLE",
                success=False,
                selected=saved or selected,
                errors=[error],
            )

        autonomy_metadata = {
            "source": "B55ProjectIntelligence",
            "planning_mode": "project_intelligence_scoped",
            "opportunity_id": opportunity_id,
            "fingerprint": selected.get("fingerprint", ""),
            "target": selected.get("target", ""),
            "issue_type": selected.get("issue_type", ""),
        }
        enqueue = self.long_running_service.enqueue(
            objective,
            context={
                "priority": self._priority_from_score(selected),
                "max_attempts": 3,
                "auto_approve": False,
                "auto_rollback": bool(policy.get("auto_rollback", True)),
                "final_validation": bool(policy.get("final_validation", True)),
                "optimization_constraints": {
                    "min_score": 50.0,
                    "max_risk": 6.0,
                    "max_campaigns": 1,
                    "max_total_minutes": 180.0,
                    "require_positive_roi": True,
                },
                "autonomy_targets": execution_targets,
                "autonomy_metadata": autonomy_metadata,
                "metadata": autonomy_metadata,
            },
        )
        if not bool(enqueue.get("success", False)):
            self.store.update_opportunity(
                opportunity_id,
                {
                    "last_error": "; ".join(
                        str(item)
                        for item in enqueue.get("errors", [])
                    ),
                },
            )
            return self._response(
                "PROJECT_INTELLIGENCE_DISPATCH_FAILED",
                success=False,
                selected=selected,
                errors=list(enqueue.get("errors", [])),
            )
        job = enqueue.get("job", {})
        job_id = str(
            enqueue.get("job_id", "")
            or (
                job.get("job_id", "")
                if isinstance(job, dict)
                else ""
            )
        )
        saved = self.store.update_opportunity(
            opportunity_id,
            {
                "status": "DISPATCHED",
                "job_id": job_id,
                "dispatched_at": self._now(),
                "last_error": "",
            },
        )
        self.store.update_runtime({"last_dispatch_at": self._now()})
        response = self._response(
            "PROJECT_INTELLIGENCE_JOB_DISPATCHED",
            success=True,
            selected=saved or selected,
            job_id=job_id,
            job=dict(job) if isinstance(job, dict) else {},
        )
        self.store.record_cycle({
            **response,
            "selected_id": opportunity_id,
            "dispatched_job_id": job_id,
        })
        return response

    def reconcile(self) -> dict[str, Any]:
        reconciled = 0
        for item in self.store.list_opportunities(limit=1000):
            job_id = str(item.get("job_id", "")).strip()
            if not job_id:
                continue
            job = self.long_running_service.store.get_job(job_id)
            if not isinstance(job, dict):
                continue
            next_status = self.JOB_STATE_MAP.get(
                str(job.get("state", "")).upper(),
                str(item.get("status", "PENDING")).upper(),
            )
            updates: dict[str, Any] = {
                "status": next_status,
                "attempts": int(job.get("attempts", 0) or 0),
                "last_error": str(job.get("last_error", ""))[:4000],
                "metadata": {
                    **dict(item.get("metadata", {}) or {}),
                    "last_job_state": job.get("state", ""),
                    "autonomy_run_id": job.get("autonomy_run_id", ""),
                },
            }
            if next_status in {"COMPLETED", "FAILED", "CANCELLED"}:
                updates["completed_at"] = str(
                    job.get("completed_at", "")
                    or self._now()
                )
            if (
                next_status != str(item.get("status", "")).upper()
                or updates["attempts"] != int(item.get("attempts", 0) or 0)
                or updates["last_error"] != str(item.get("last_error", ""))
            ):
                self.store.update_opportunity(
                    str(item.get("opportunity_id", "")),
                    updates,
                )
                reconciled += 1
        return self._response(
            "PROJECT_INTELLIGENCE_RECONCILED",
            success=True,
            reconciled=reconciled,
        )

    def run_cycle(
        self,
        *,
        dispatch: bool | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            reconciliation = self.reconcile()
            scan = self.scan_project()
            runtime = self.store.runtime()
            policy = self.store.policy()
            should_dispatch = (
                bool(dispatch)
                if dispatch is not None
                else bool(
                    runtime.get("enabled", False)
                    and not runtime.get("paused", False)
                    and policy.get("auto_dispatch", False)
                )
            )
            dispatched: list[dict[str, Any]] = []
            if should_dispatch:
                for _ in range(
                    int(policy.get("max_dispatch_per_cycle", 1))
                ):
                    result = self.dispatch_best(force=True)
                    dispatched.append(result)
                    if not bool(result.get("success", False)):
                        break
            status = (
                "PROJECT_INTELLIGENCE_CYCLE_COMPLETED"
                if bool(scan.get("success", False))
                else "PROJECT_INTELLIGENCE_CYCLE_FAILED"
            )
            return self._response(
                status,
                success=bool(scan.get("success", False)),
                scan=scan,
                reconciliation=reconciliation,
                dispatched=dispatched,
            )

    def start_background(self) -> dict[str, Any]:
        if self.is_running():
            return self._response(
                "PROJECT_INTELLIGENCE_SUPERVISOR_ALREADY_RUNNING",
                success=True,
            )
        with self._lock:
            if self.is_running():
                return self._response(
                    "PROJECT_INTELLIGENCE_SUPERVISOR_ALREADY_RUNNING",
                    success=True,
                )
            self.store.update_runtime({
                "enabled": True,
                "paused": False,
                "running": True,
                "last_error": "",
            })
            self.store.update_policy({
                "auto_dispatch": True,
                "auto_approve": False,
            })
            self.long_running_service.start_background()
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-project-intelligence",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "PROJECT_INTELLIGENCE_SUPERVISOR_STARTED",
                success=True,
            )

    def start_if_enabled(self) -> dict[str, Any]:
        self.store.compact()
        if bool(self.store.runtime().get("enabled", False)):
            return self.start_background()
        return self._response(
            "PROJECT_INTELLIGENCE_SUPERVISOR_DISABLED",
            success=True,
        )

    def stop_background(self) -> dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=5.0)
        self.store.update_runtime({
            "enabled": False,
            "running": False,
        })
        return self._response(
            "PROJECT_INTELLIGENCE_SUPERVISOR_STOPPED",
            success=True,
        )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({"paused": True})
        return self._response(
            "PROJECT_INTELLIGENCE_SUPERVISOR_PAUSED",
            success=True,
            runtime=runtime,
        )

    def resume(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({"paused": False})
        return self._response(
            "PROJECT_INTELLIGENCE_SUPERVISOR_RESUMED",
            success=True,
            runtime=runtime,
        )

    def reject(self, opportunity_id: str) -> dict[str, Any]:
        item = self.store.get_opportunity(opportunity_id)
        if item is None:
            return self._not_found(opportunity_id)
        if str(item.get("status", "")).upper() in ACTIVE_OPPORTUNITY_STATES:
            return self._response(
                "PROJECT_INTELLIGENCE_REJECT_BLOCKED",
                success=False,
                selected=item,
                errors=["Nie można odrzucić aktywnego zadania."],
            )
        saved = self.store.update_opportunity(
            opportunity_id,
            {
                "status": "REJECTED",
                "completed_at": self._now(),
            },
        )
        return self._response(
            "PROJECT_INTELLIGENCE_OPPORTUNITY_REJECTED",
            success=True,
            selected=saved or item,
        )

    def status(self) -> dict[str, Any]:
        self.reconcile()
        selected = self.select_best().get("selected", {})
        return self._response(
            "PROJECT_INTELLIGENCE_STATUS",
            success=True,
            selected=selected,
            opportunities=self.store.list_opportunities(limit=20),
        )

    def backlog(self, *, limit: int = 50) -> dict[str, Any]:
        self.reconcile()
        return self._response(
            "PROJECT_INTELLIGENCE_BACKLOG",
            success=True,
            opportunities=self.store.list_opportunities(limit=limit),
        )

    def opportunity(self, opportunity_id: str) -> dict[str, Any]:
        self.reconcile()
        item = self.store.get_opportunity(opportunity_id)
        if item is None:
            return self._not_found(opportunity_id)
        return self._response(
            "PROJECT_INTELLIGENCE_OPPORTUNITY_STATUS",
            success=True,
            selected=item,
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "PROJECT_INTELLIGENCE_HISTORY",
            success=True,
            cycles=self.store.cycles(limit=limit),
        )

    def update_policy(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        policy = self.store.update_policy({
            **dict(updates),
            "auto_approve": False,
        })
        return self._response(
            "PROJECT_INTELLIGENCE_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run_loop(self) -> None:
        try:
            if self._stop_event.wait(12.0):
                return

            while not self._stop_event.is_set():
                try:
                    if not bool(self.store.runtime().get("paused", False)):
                        self.run_cycle()
                except Exception as error:
                    self.store.update_runtime({
                        "last_error": f"{type(error).__name__}: {error}",
                    })
                interval = float(
                    self.store.policy().get(
                        "scan_interval_seconds",
                        300.0,
                    )
                )
                self._stop_event.wait(max(30.0, interval))
        finally:
            self.store.update_runtime({"running": False})

    def _extract_candidates(
        self,
        cycle: dict[str, Any],
    ) -> list[ProjectOpportunity]:
        prioritization = cycle.get("prioritization", {})
        candidates = (
            prioritization.get("candidates", [])
            if isinstance(prioritization, dict)
            else []
        )
        if not isinstance(candidates, list) or not candidates:
            base = cycle.get("base_cycle", {})
            planning = (
                base.get("planning", {})
                if isinstance(base, dict)
                else {}
            )
            candidates = (
                [
                    {"task": item}
                    for item in planning.get("tasks", [])
                    if isinstance(item, dict)
                ]
                if isinstance(planning, dict)
                else []
            )
        result: list[ProjectOpportunity] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            task = candidate.get("task", candidate)
            if not isinstance(task, dict):
                continue
            target = self._safe_target(task.get("target", ""))
            if not target:
                continue
            title = str(
                task.get("title", "Bezpieczne ulepszenie projektu")
            ).strip()
            issue_type = str(
                (task.get("metadata", {}) or {}).get(
                    "issue_type",
                    task.get("issue_type", "PROJECT_IMPROVEMENT"),
                )
            ).strip()
            severity = str(task.get("severity", "MEDIUM")).upper()
            risk = float(
                candidate.get(
                    "predicted_risk",
                    (task.get("metadata", {}) or {}).get("risk", 20.0),
                )
                or 0.0
            )
            value = float(
                candidate.get(
                    "value_score",
                    task.get("priority_score", 20.0),
                )
                or 0.0
            )
            effort = float(
                candidate.get(
                    "effort_score",
                    (task.get("metadata", {}) or {}).get(
                        "estimated_effort",
                        5.0,
                    ),
                )
                or 0.0
            )
            confidence = min(
                1.0,
                max(
                    0.0,
                    float(
                        (task.get("metadata", {}) or {}).get(
                            "confidence",
                            0.70,
                        )
                        or 0.0
                    ),
                ),
            )
            fingerprint = self._fingerprint(
                title,
                target,
                issue_type,
            )
            objective = self._objective(task, title, target)
            item = ProjectOpportunity(
                title=title,
                objective=objective,
                target=target,
                severity=severity,
                issue_type=issue_type,
                fingerprint=fingerprint,
                value_score=value,
                risk_score=risk,
                effort_score=effort,
                confidence=confidence,
                final_score=float(candidate.get("final_score", 0.0) or 0.0),
                metadata={
                    **dict(task.get("metadata", {}) or {}),
                    "decision": candidate.get(
                        "decision",
                        "READY_FOR_SAFE_GENERATION",
                    ),
                    "recommendation": task.get("recommendation", ""),
                },
            )
            result.append(
                ProjectOpportunity.from_dict(
                    self.ranker.score(item.to_dict())
                )
            )
        return result

    def _safe_target(self, value: Any) -> str:
        text = str(value).strip().replace("\\", "/")
        if not text:
            return ""
        candidate = Path(text)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve(strict=False).relative_to(
                    self.project_root
                )
            except ValueError:
                return ""
        normalized = candidate.as_posix().lstrip("/")
        if normalized.startswith("../") or "/../" in normalized:
            return ""
        if normalized.startswith(
            (
                ".git/",
                ".venv/",
                "venv/",
                "archive/",
                "backups/",
                "data/",
            )
        ):
            return ""
        return normalized

    @staticmethod
    def _objective(
        task: dict[str, Any],
        title: str,
        target: str,
    ) -> str:
        description = str(task.get("description", "")).strip()
        recommendation = str(task.get("recommendation", "")).strip()
        parts = [
            (
                f"Bezpiecznie zrealizuj zadanie rozwojowe dla istniejącego "
                f"modułu {target}: {title}."
            ),
            description,
            recommendation,
            (
                "Zachowaj kompatybilność, nie usuwaj publicznych symboli, "
                "wykonaj pełną walidację i testy oraz zatrzymaj się na "
                "podglądzie zmian, jeśli potrzebna jest jawna akceptacja."
            ),
        ]
        return " ".join(part for part in parts if part)[:5000]

    @staticmethod
    def _fingerprint(
        title: str,
        target: str,
        issue_type: str,
    ) -> str:
        value = "|".join(
            (
                title.casefold().strip(),
                target.casefold().strip(),
                issue_type.casefold().strip(),
            )
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _execution_targets(
        self,
        opportunity: dict[str, Any],
    ) -> list[str]:
        target = self._safe_target(opportunity.get("target", ""))
        target_path = self.project_root / target
        if (
            not target
            or target_path.suffix.casefold() != ".py"
            or not target_path.is_file()
            or target_path.is_symlink()
        ):
            return []

        module_name = target[:-3].replace("/", ".")
        stem = target_path.stem.casefold()
        parent = target_path.parent.resolve(strict=False)
        candidates: list[tuple[int, str]] = []
        scanned = 0

        for root_name in ("tests", "app"):
            root = self.project_root / root_name
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                if scanned >= 900:
                    break
                scanned += 1
                if path == target_path or path.is_symlink():
                    continue
                if "__pycache__" in path.parts:
                    continue
                try:
                    if path.stat().st_size > 500_000:
                        continue
                    relative = path.relative_to(self.project_root).as_posix()
                    source = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError, ValueError):
                    continue
                if not self._safe_target(relative):
                    continue

                lowered_source = source.casefold()
                score = 0
                if path.name.casefold() == f"test_{stem}.py":
                    score += 120
                if module_name.casefold() in lowered_source:
                    score += 90
                if f".{stem} import" in lowered_source:
                    score += 70
                if stem in path.stem.casefold():
                    score += 35
                if path.parent.resolve(strict=False) == parent:
                    score += 20
                if relative.startswith("tests/") and score > 0:
                    score += 10
                if score > 0:
                    candidates.append((score, relative))
            if scanned >= 900:
                break

        candidates.sort(key=lambda item: (-item[0], item[1]))
        result = [target]
        for _, relative in candidates:
            if relative not in result:
                result.append(relative)
            if len(result) >= 4:
                break
        return result

    def _active_opportunities(self) -> list[dict[str, Any]]:
        return self.store.list_opportunities(
            limit=1000,
            statuses=set(ACTIVE_OPPORTUNITY_STATES),
        )

    @staticmethod
    def _priority_from_score(item: dict[str, Any]) -> int:
        score = float(item.get("final_score", 50.0) or 50.0)
        return min(100, max(1, int(round(score))))

    def _not_found(self, opportunity_id: str) -> dict[str, Any]:
        return self._response(
            "PROJECT_INTELLIGENCE_OPPORTUNITY_NOT_FOUND",
            success=False,
            errors=[f"Nie znaleziono zadania {opportunity_id}."],
        )

    def _response(
        self,
        status: str,
        *,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "project_intelligence",
            "runtime": dict(extra.pop("runtime", self.store.runtime())),
            "policy": dict(extra.pop("policy", self.store.policy())),
            "summary": self.store.summary(),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


def bootstrap_project_intelligence(
    controller: Any,
) -> ProjectIntelligenceService:
    service = getattr(
        controller,
        "project_intelligence_service",
        None,
    )
    if service is None:
        long_running = getattr(
            controller,
            "long_running_autonomy_service",
            None,
        )
        service = ProjectIntelligenceService(
            controller.project_root,
            long_running_service=long_running,
        )
        controller.project_intelligence_service = service
    service.start_if_enabled()
    return service
