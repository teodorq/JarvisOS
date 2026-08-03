from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root

from .autonomous_backlog import AutonomousBacklogReader
from .autonomous_cycle_models import AutonomousBacklogPolicy, AutonomousDevelopmentCycle
from .autonomous_cycle_store import AutonomousCycleStore
from .autonomous_self_seeding import AutonomousBacklogSelfSeeder
from .safe_autonomous_development_service import SafeAutonomousDevelopmentService


class AutonomousBacklogCycleService:
    """B211-B220: choose one backlog task and stop at approval-ready patch."""

    CONFIG = "config/b211_b220_autonomous_development_2_1.json"

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: AutonomousBacklogPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or self._load_policy()
        self.store = AutonomousCycleStore(self.project_root, policy=self.policy)
        self.backlog = AutonomousBacklogReader(self.project_root, policy=self.policy)
        self.safe_development = SafeAutonomousDevelopmentService(self.project_root)
        self.self_seeder = AutonomousBacklogSelfSeeder(
            self.project_root,
            policy=self.policy,
        )

    def run_one(self) -> dict[str, Any]:
        existing = self.store.active()
        if existing is not None:
            existing = self._sync(existing)
            if existing.status in self.store.ACTIVE:
                return self._active_result(existing, duplicate=True)
        cycle = self.store.new_cycle()
        excluded = self.store.excluded_fingerprints()
        candidates = self.backlog.candidates(
            excluded_fingerprints=excluded
        )
        seed_result: dict[str, Any] = {}
        if not candidates:
            seed_result = self.self_seeder.seed_one(
                excluded_fingerprints=excluded
            )
            candidates = self.backlog.candidates(
                excluded_fingerprints=excluded
            )
        if not candidates:
            cycle.status = "NO_SAFE_SEED_CANDIDATE"
            cycle.result = {
                "candidate_count": 0,
                "self_seed": seed_result,
            }
            self.store.save(cycle)
            return self._result(
                cycle,
                success=False,
                status="NO_SAFE_SEED_CANDIDATE",
                message=(
                    "Backlog nie zawierał gotowego zadania, więc przeskanowałem "
                    "projekt. Nie znalazłem nowej poprawki spełniającej wszystkie "
                    "ograniczenia AutoDev 2.1. Niczego nie zmieniłem."
                ),
            )
        for candidate in candidates[: self.policy.max_attempts_per_cycle]:
            cycle.attempted_task_ids.append(candidate.task_id)
            task = candidate.to_dict()
            if not self.store.claim(cycle, task):
                continue
            prepared = self.safe_development.prepare(preview=self._preview(candidate))
            if prepared.get("success", False):
                session = dict(prepared.get("session", {}) or {})
                cycle.status = "READY_FOR_APPROVAL"
                cycle.safe_session_id = str(session.get("session_id", ""))
                cycle.operation_fingerprint = str(
                    prepared.get("operation_fingerprint", "")
                )
                cycle.result = {
                    "selected_task": task,
                    "safe_session": session,
                    "self_seed": seed_result,
                    "self_seeded": (
                        str(task.get("source", ""))
                        == "self_seeded_project_scan"
                    ),
                    "project_files_modified": False,
                    "requires_confirmation": False,
                }
                self.store.save(cycle)
                return self._active_result(cycle, duplicate=False)
            cycle.deferred.append({
                "task_id": candidate.task_id,
                "target": candidate.target,
                "status": str(prepared.get("status", "PREPARATION_FAILED")),
                "reason": str(prepared.get("message", "Nie udało się przygotować poprawki.")),
            })
            self.store.defer(
                cycle,
                str(prepared.get("status", "PREPARATION_FAILED")),
            )
            cycle.task = {}
            cycle.task_fingerprint = ""
            cycle.lease_expires_at = ""
            cycle.status = "SELECTING"
            self.store.save(cycle)
        cycle.status = "NO_PREPARABLE_TASK"
        cycle.result = {"candidate_count": len(candidates)}
        self.store.save(cycle)
        return self._result(
            cycle,
            success=False,
            status="NO_PREPARABLE_TASK",
            message=(
                "Sprawdziłem bezpieczne zadania z backlogu, ale żadne nie "
                "przeszło przygotowania na izolowanej kopii. Projekt pozostał bez zmian."
            ),
        )

    def status(self) -> dict[str, Any]:
        cycle = self.store.latest()
        if cycle is None:
            return {
                "success": True,
                "status": "NO_CYCLE",
                "message": "Nie uruchomiono jeszcze autonomicznego cyklu AutoDev 2.1.",
            }
        cycle = self._sync(cycle)
        return self._result(cycle, success=True, status=cycle.status, message=self._status_message(cycle))

    def resume(self) -> dict[str, Any]:
        active = self.store.active()
        if active is not None:
            active = self._sync(active)
            if active.status in self.store.ACTIVE:
                return self._active_result(active, duplicate=True)
        latest = self.store.latest()
        if latest is not None and latest.status == "READY_FOR_APPROVAL":
            return self._active_result(self._sync(latest), duplicate=True)
        return self.run_one()

    def cancel(self) -> dict[str, Any]:
        cycle = self.store.active()
        if cycle is None:
            return {
                "success": False,
                "status": "NO_ACTIVE_CYCLE",
                "message": "Nie ma aktywnego autonomicznego cyklu do anulowania.",
            }
        if cycle.safe_session_id:
            try:
                session = self.safe_development.store.load_session(cycle.safe_session_id)
                if session.status == "READY_FOR_APPROVAL":
                    self.safe_development.store.discard(session.session_id)
            except (OSError, ValueError, TypeError):
                pass
        cycle.status = "CANCELLED"
        self.store.release(cycle)
        self.store.save(cycle)
        return self._result(
            cycle,
            success=True,
            status="CANCELLED",
            message="Anulowałem cykl i usunąłem wyłącznie niewdrożony workspace.",
        )

    def _sync(self, cycle: AutonomousDevelopmentCycle) -> AutonomousDevelopmentCycle:
        if not cycle.safe_session_id:
            return cycle
        try:
            session = self.safe_development.store.load_session(cycle.safe_session_id)
        except (OSError, ValueError, TypeError):
            return cycle
        mapping = {
            "READY_FOR_APPROVAL": "READY_FOR_APPROVAL",
            "DEPLOYED": "DEPLOYED",
            "ROLLED_BACK": "ROLLED_BACK",
            "DISCARDED": "CANCELLED",
            "FAILED": "FAILED",
            "STALE": "STALE",
        }
        new_status = mapping.get(session.status, cycle.status)
        if new_status != cycle.status:
            cycle.status = new_status
            cycle.result["safe_session_status"] = session.status
            self.store.save(cycle)
        if new_status in {"DEPLOYED", "ROLLED_BACK"}:
            self.store.mark_completed(cycle)
        elif new_status in {"CANCELLED", "FAILED", "STALE"}:
            self.store.release(cycle)
        return cycle

    def _active_result(
        self,
        cycle: AutonomousDevelopmentCycle,
        *,
        duplicate: bool,
    ) -> dict[str, Any]:
        task = dict(cycle.task or {})
        session = dict(cycle.result.get("safe_session", {}) or {})
        prefix = "Ten sam cykl jest już gotowy. " if duplicate else ""
        origin = (
            "Backlog nie miał bezpiecznego zadania, więc sam utworzyłem jedno "
            "na podstawie skanu projektu. "
            if bool(cycle.result.get("self_seeded", False))
            else ""
        )
        return self._result(
            cycle,
            success=True,
            status=cycle.status,
            message=(
                f"{prefix}{origin}Sam wybrałem zadanie z backlogu: "
                f"{task.get('title', 'bez nazwy')}. "
                f"Przygotowałem poprawkę dla {task.get('target', 'pliku projektu')} "
                f"na izolowanej kopii. Zmiana obejmuje {session.get('changed_lines', 0)} "
                f"linii w {len(session.get('changed_files', []) or [])} pliku i przeszła "
                f"{self._test_count(session)} testów. Działający projekt nie został zmieniony. "
                "Czekam przed wdrożeniem na Twoją osobną decyzję."
            ),
            duplicate=duplicate,
        )

    def _status_message(self, cycle: AutonomousDevelopmentCycle) -> str:
        task = dict(cycle.task or {})
        if cycle.status == "READY_FOR_APPROVAL":
            return (
                f"Cykl {cycle.cycle_id} jest gotowy do decyzji. Zadanie: "
                f"{task.get('title', 'bez nazwy')}; plik: {task.get('target', '')}. "
                "Poprawka nie została wdrożona."
            )
        if cycle.status == "DEPLOYED":
            return "Wybrana poprawka została wdrożona i zweryfikowana."
        if cycle.status == "ROLLED_BACK":
            return "Wybrana poprawka została wdrożona, a następnie bezpiecznie cofnięta."
        return f"Ostatni autonomiczny cykl ma status: {cycle.status}."

    def _preview(self, candidate) -> dict[str, Any]:
        return {
            "task": {
                "target": candidate.target,
                "title": candidate.title,
                "description": candidate.description,
                "metadata": {
                    **dict(candidate.metadata),
                    "issue_type": candidate.issue_type,
                    "backlog_source": candidate.source,
                    "backlog_task_id": candidate.task_id,
                    "backlog_fingerprint": candidate.fingerprint,
                    "require_exact_target": True,
                },
            },
            "predicted_risk": candidate.risk_score,
            "effort_score": candidate.effort_score,
            "confidence": candidate.confidence,
            "backlog_task": candidate.to_dict(),
        }

    def _result(
        self,
        cycle: AutonomousDevelopmentCycle,
        *,
        success: bool,
        status: str,
        message: str,
        duplicate: bool = False,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "message": message,
            "cycle": cycle.to_dict(),
            "requires_confirmation": False,
            "project_files_modified": False,
            "auto_approve": False,
            "auto_deploy": False,
            "duplicate": duplicate,
        }

    @staticmethod
    def _test_count(session: dict[str, Any]) -> int:
        workspace = dict(dict(session.get("validation", {}) or {}).get("workspace", {}) or {})
        tests = dict(workspace.get("tests", {}) or {})
        try:
            return int(tests.get("count", 0))
        except (TypeError, ValueError):
            return 0

    def _load_policy(self) -> AutonomousBacklogPolicy:
        path = self.project_root / Path(self.CONFIG)
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            limits = dict(value.get("limits", {}) or {})
            safety = dict(value.get("safety", {}) or {})
            return AutonomousBacklogPolicy(
                max_candidates=int(limits.get("max_candidates", 50)),
                max_attempts_per_cycle=int(limits.get("max_attempts_per_cycle", 6)),
                max_risk_score=float(limits.get("max_risk_score", 50.0)),
                min_confidence=float(limits.get("min_confidence", 0.75)),
                min_final_score=float(limits.get("min_final_score", 15.0)),
                lease_seconds=int(limits.get("lease_seconds", 1800)),
                max_cycles=int(limits.get("max_cycles", 40)),
                auto_approve=bool(safety.get("auto_approve", False)),
                auto_deploy=bool(safety.get("auto_deploy", False)),
            )
        except (OSError, ValueError, TypeError):
            return AutonomousBacklogPolicy()
