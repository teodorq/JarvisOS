from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root

from .autonomous_backlog import AutonomousBacklogReader
from .autonomous_cycle_models import (
    AutonomousBacklogCandidate,
    AutonomousBacklogPolicy,
)
from .project_intelligence_scanner import ProjectOpportunityScanner


class AutonomousSelfSeedStore:
    """Persistent low-risk backlog owned by Autonomous Development 2.1."""

    RELATIVE_PATH = (
        "data/autodev/autonomous_development_2_1/self_seeded_tasks.json"
    )
    VERSION = 1

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        max_tasks: int = 20,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.path = self.project_root / self.RELATIVE_PATH
        self.max_tasks = max(1, min(100, int(max_tasks)))

    def tasks(self) -> list[dict[str, Any]]:
        payload = self._load()
        tasks = dict(payload.get("tasks", {}) or {})
        order = list(payload.get("order", []) or [])
        result: list[dict[str, Any]] = []
        for task_id in [*order, *sorted(set(tasks) - set(order))]:
            value = tasks.get(task_id)
            if isinstance(value, dict):
                result.append(dict(value))
        return result

    def save(self, task: dict[str, Any]) -> dict[str, Any]:
        value = dict(task)
        task_id = str(value.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("Brak identyfikatora zadania self-seed.")
        payload = self._load()
        tasks = dict(payload.get("tasks", {}) or {})
        tasks[task_id] = value
        order = [item for item in list(payload.get("order", []) or []) if item != task_id]
        order.insert(0, task_id)
        keep = order[: self.max_tasks]
        payload.update({
            "version": self.VERSION,
            "tasks": {key: tasks[key] for key in keep if key in tasks},
            "order": keep,
            "updated_at": self._now(),
        })
        self._atomic_json(payload)
        return value

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {
                "version": self.VERSION,
                "tasks": {},
                "order": [],
                "updated_at": "",
            }
        try:
            value = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError):
            return {
                "version": self.VERSION,
                "tasks": {},
                "order": [],
                "updated_at": "",
            }
        return dict(value) if isinstance(value, dict) else {}

    def _atomic_json(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


class AutonomousBacklogSelfSeeder:
    """Creates one bounded task when legacy backlog has no eligible item."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: AutonomousBacklogPolicy | None = None,
        max_files: int = 500,
        max_opportunities: int = 100,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or AutonomousBacklogPolicy()
        self.max_files = max(50, min(500, int(max_files)))
        self.max_opportunities = max(10, min(100, int(max_opportunities)))
        self.store = AutonomousSelfSeedStore(self.project_root)
        self.reader = AutonomousBacklogReader(
            self.project_root,
            policy=self.policy,
        )

    def seed_one(
        self,
        *,
        excluded_fingerprints: set[str] | None = None,
    ) -> dict[str, Any]:
        batch = self.seed_many(
            limit=1,
            excluded_fingerprints=excluded_fingerprints,
        )
        tasks = list(batch.get("tasks", []) or [])
        return {
            **batch,
            "status": "SELF_SEEDED" if tasks else "NO_SAFE_SEED_CANDIDATE",
            "task": dict(tasks[0]) if tasks else {},
        }

    def seed_many(
        self,
        *,
        limit: int = 5,
        excluded_fingerprints: set[str] | None = None,
    ) -> dict[str, Any]:
        """Create a diverse, evidence-bound backlog batch from one scan."""
        excluded = set(excluded_fingerprints or set())
        cycle = ProjectOpportunityScanner(
            self.project_root,
            max_files=self.max_files,
            max_opportunities=self.max_opportunities,
        ).run_cycle()
        prioritization = dict(cycle.get("prioritization", {}) or {})
        candidates = list(prioritization.get("candidates", []) or [])
        existing = {
            str(item.get("fingerprint", ""))
            for item in self.store.tasks()
        }
        created: list[dict[str, Any]] = []
        selected_targets: set[str] = set()
        bounded_limit = max(1, min(10, int(limit)))
        for raw in candidates:
            task = self._task_from_scan(dict(raw or {}))
            if not task:
                continue
            fingerprint = str(task.get("fingerprint", ""))
            if fingerprint in excluded or fingerprint in existing:
                continue
            target = str(task.get("target", ""))
            if target in selected_targets:
                continue
            candidate = self.to_candidate(task)
            if not self.reader.is_eligible(candidate):
                continue
            self.store.save(task)
            created.append(task)
            selected_targets.add(target)
            existing.add(fingerprint)
            if len(created) >= bounded_limit:
                break
        return {
            "success": bool(created),
            "status": "SELF_SEEDED_BATCH" if created else "NO_SAFE_SEED_CANDIDATE",
            "tasks": created,
            "files_scanned": int(cycle.get("files_scanned", 0) or 0),
            "scan_candidates": len(candidates),
            "legacy_backlog_modified": False,
        }

    def to_candidate(self, task: dict[str, Any]) -> AutonomousBacklogCandidate:
        metadata = dict(task.get("metadata", {}) or {})
        return AutonomousBacklogCandidate(
            source="self_seeded_project_scan",
            task_id=str(task.get("task_id", "")),
            fingerprint=str(task.get("fingerprint", "")),
            target=str(task.get("target", "")),
            title=str(task.get("title", "")),
            description=str(task.get("description", "")),
            issue_type=str(task.get("issue_type", "")),
            status=str(task.get("status", "PENDING")).upper(),
            risk_score=float(task.get("risk_score", 100.0)),
            value_score=float(task.get("value_score", 0.0)),
            effort_score=float(task.get("effort_score", 100.0)),
            confidence=float(task.get("confidence", 0.0)),
            final_score=float(task.get("final_score", 0.0)),
            metadata=metadata,
        )

    def _task_from_scan(self, raw: dict[str, Any]) -> dict[str, Any]:
        task = dict(raw.get("task", {}) or {})
        metadata = dict(task.get("metadata", {}) or {})
        target = str(task.get("target", "")).replace("\\", "/").strip("/")
        if not target:
            return {}
        source_path = self.project_root / Path(target)
        try:
            source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        except OSError:
            return {}
        issue_type = str(metadata.get("issue_type", "PROJECT_IMPROVEMENT"))
        function = str(metadata.get("function", ""))
        fingerprint = self._fingerprint(
            "self-seed-v1", target, issue_type, function, source_hash
        )
        return {
            "task_id": "self-seed-" + fingerprint[:16],
            "fingerprint": fingerprint,
            "source": "self_seeded_project_scan",
            "target": target,
            "title": str(task.get("title", "Bezpieczna poprawa projektu")),
            "description": str(task.get("description", "")),
            "issue_type": issue_type,
            "status": "PENDING",
            "risk_score": float(raw.get("predicted_risk", 100.0)),
            "value_score": float(raw.get("value_score", 0.0)),
            "effort_score": float(raw.get("effort_score", 100.0)),
            "confidence": float(metadata.get("confidence", 0.0)),
            "final_score": float(raw.get("final_score", 0.0)),
            "metadata": {
                **metadata,
                "self_seeded": True,
                "source_hash": source_hash,
                "scan_decision": str(raw.get("decision", "")),
                "evidence": {
                    "target": target,
                    "issue_type": issue_type,
                    "source_hash": source_hash,
                },
                "dependencies": [],
                "generated_at": AutonomousSelfSeedStore._now(),
            },
        }

    @staticmethod
    def _fingerprint(*parts: object) -> str:
        return hashlib.sha256("\x1f".join(map(str, parts)).encode()).hexdigest()
