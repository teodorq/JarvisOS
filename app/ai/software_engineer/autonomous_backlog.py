from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from app.core.project_paths import resolve_project_root

from .autonomous_cycle_models import (
    AutonomousBacklogCandidate,
    AutonomousBacklogPolicy,
)


class AutonomousBacklogReader:
    """Reads legacy backlog sources without mutating them."""

    INTELLIGENCE = "data/autodev/project_intelligence.json"
    TASK_QUEUE = "data/autodev/autonomous_task_queue.json"
    SELF_SEEDED = (
        "data/autodev/autonomous_development_2_1/self_seeded_tasks.json"
    )

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: AutonomousBacklogPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or AutonomousBacklogPolicy()

    def candidates(
        self,
        *,
        excluded_fingerprints: set[str] | None = None,
    ) -> list[AutonomousBacklogCandidate]:
        excluded = set(excluded_fingerprints or set())
        values = [
            *self._project_intelligence_candidates(),
            *self._task_queue_candidates(),
            *self._self_seeded_candidates(),
        ]
        eligible = [
            item for item in values
            if item.fingerprint not in excluded and self._eligible(item)
        ]
        eligible.sort(key=self._rank_key)
        return eligible[: self.policy.max_candidates]

    def is_eligible(self, item: AutonomousBacklogCandidate) -> bool:
        """Public exact-transform gate shared with the self-seeder."""
        return self._eligible(item)

    def _project_intelligence_candidates(self) -> list[AutonomousBacklogCandidate]:
        data = self._load(self.INTELLIGENCE)
        opportunities = dict(data.get("opportunities", {}) or {})
        order = list(data.get("order", []) or [])
        result: list[AutonomousBacklogCandidate] = []
        for task_id in [*order, *sorted(set(opportunities) - set(order))]:
            value = dict(opportunities.get(task_id, {}) or {})
            if not value:
                continue
            result.append(self._from_intelligence(task_id, value))
        return result

    def _task_queue_candidates(self) -> list[AutonomousBacklogCandidate]:
        data = self._load(self.TASK_QUEUE)
        result: list[AutonomousBacklogCandidate] = []
        for value in list(data.get("tasks", []) or []):
            item = dict(value or {})
            if not item:
                continue
            result.append(self._from_queue(item))
        return result

    def _self_seeded_candidates(self) -> list[AutonomousBacklogCandidate]:
        data = self._load(self.SELF_SEEDED)
        tasks = dict(data.get("tasks", {}) or {})
        order = list(data.get("order", []) or [])
        result: list[AutonomousBacklogCandidate] = []
        for task_id in [*order, *sorted(set(tasks) - set(order))]:
            value = dict(tasks.get(task_id, {}) or {})
            if not value:
                continue
            result.append(self._from_seeded(value))
        return result

    def _from_intelligence(
        self,
        task_id: str,
        value: dict[str, Any],
    ) -> AutonomousBacklogCandidate:
        metadata = dict(value.get("metadata", {}) or {})
        fingerprint = str(value.get("fingerprint", "")).strip() or self._fingerprint(
            "project_intelligence", task_id, value.get("target", "")
        )
        return AutonomousBacklogCandidate(
            source="project_intelligence",
            task_id=str(value.get("opportunity_id", task_id)),
            fingerprint=fingerprint,
            target=self._target(value),
            title=str(value.get("title", "Zadanie z backlogu")),
            description=str(value.get("objective", value.get("description", ""))),
            issue_type=str(value.get("issue_type", metadata.get("issue_type", ""))),
            status=str(value.get("status", "")).upper(),
            risk_score=self._number(value.get("risk_score"), 100.0),
            value_score=self._number(value.get("value_score"), 0.0),
            effort_score=self._number(value.get("effort_score"), 100.0),
            confidence=self._confidence(value.get("confidence", metadata.get("confidence"))),
            final_score=self._number(value.get("final_score"), 0.0),
            metadata=metadata,
        )

    def _from_seeded(self, value: dict[str, Any]) -> AutonomousBacklogCandidate:
        metadata = dict(value.get("metadata", {}) or {})
        return AutonomousBacklogCandidate(
            source="self_seeded_project_scan",
            task_id=str(value.get("task_id", "")),
            fingerprint=str(value.get("fingerprint", "")),
            target=self._target(value),
            title=str(value.get("title", "Bezpieczna poprawa projektu")),
            description=str(value.get("description", "")),
            issue_type=str(value.get("issue_type", "PROJECT_IMPROVEMENT")),
            status=str(value.get("status", "PENDING")).upper(),
            risk_score=self._number(value.get("risk_score"), 100.0),
            value_score=self._number(value.get("value_score"), 0.0),
            effort_score=self._number(value.get("effort_score"), 100.0),
            confidence=self._confidence(value.get("confidence", 0.0)),
            final_score=self._number(value.get("final_score"), 0.0),
            metadata=metadata,
        )

    def _from_queue(self, value: dict[str, Any]) -> AutonomousBacklogCandidate:
        payload = dict(value.get("payload", {}) or {})
        task = dict(payload.get("task", {}) or {})
        metadata = dict(task.get("metadata", {}) or {})
        merged = {**payload, **task, "metadata": metadata}
        task_id = str(value.get("task_id", task.get("task_id", "")))
        fingerprint = str(value.get("fingerprint", "")).strip() or self._fingerprint(
            "autonomous_task_queue", task_id, self._target(merged)
        )
        risk = payload.get("risk", task.get("estimated_risk", 1.0))
        roi = payload.get("roi", task.get("estimated_roi", 0.0))
        return AutonomousBacklogCandidate(
            source="autonomous_task_queue",
            task_id=task_id,
            fingerprint=fingerprint,
            target=self._target(merged),
            title=str(value.get("title", task.get("title", "Zadanie AutoDev"))),
            description=str(value.get("description", task.get("description", ""))),
            issue_type=str(task.get("category", metadata.get("issue_type", ""))),
            status=str(value.get("status", "")).upper(),
            risk_score=self._percent(risk),
            value_score=self._percent(roi),
            effort_score=self._number(task.get("estimated_minutes"), 100.0),
            confidence=self._confidence(metadata.get("confidence", 0.8)),
            final_score=self._percent(roi) - self._percent(risk),
            metadata=metadata,
        )

    def _eligible(self, item: AutonomousBacklogCandidate) -> bool:
        if item.status not in self.policy.allowed_statuses:
            return False
        if (
            item.risk_score > self.policy.max_risk_score
            or item.confidence < self.policy.min_confidence
            or item.final_score < self.policy.min_final_score
        ):
            return False
        path = self._safe_target(item.target)
        if path is None:
            return False
        return self._has_exact_transform(path, item)

    def _has_exact_transform(
        self,
        path: Path,
        item: AutonomousBacklogCandidate,
    ) -> bool:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=item.target)
        except (OSError, UnicodeError, SyntaxError):
            return False
        if ast.get_docstring(tree, clean=False) is None or not source.endswith("\n"):
            return True
        function = str(item.metadata.get("function", "")).strip()
        if not function:
            return False
        return any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function
            and ast.get_docstring(node, clean=False) is None
            for node in ast.walk(tree)
        )

    def _safe_target(self, relative: str) -> Path | None:
        normalized = str(relative).replace("\\", "/").strip("/")
        if not normalized.endswith(".py"):
            return None
        if not any(normalized.startswith(prefix) for prefix in self.policy.allowed_prefixes):
            return None
        wrapped = "/" + normalized + "/"
        if any(fragment.casefold() in wrapped.casefold() for fragment in self.policy.protected_fragments):
            return None
        path = (self.project_root / Path(normalized)).resolve(strict=False)
        try:
            path.relative_to(self.project_root)
        except ValueError:
            return None
        return path if path.is_file() and not path.is_symlink() else None

    @staticmethod
    def _rank_key(item: AutonomousBacklogCandidate) -> tuple[Any, ...]:
        score = (
            item.final_score
            + item.value_score * 0.35
            + item.confidence * 20.0
            - item.risk_score * 0.55
            - item.effort_score * 0.15
        )
        return (-score, item.risk_score, item.effort_score, item.target, item.task_id)

    def _load(self, relative: str) -> dict[str, Any]:
        path = self.project_root / Path(relative)
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError):
            return {}
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _target(value: dict[str, Any]) -> str:
        metadata = dict(value.get("metadata", {}) or {})
        for key in ("target", "path", "file", "relative_path"):
            candidate = value.get(key, metadata.get(key, ""))
            text = str(candidate or "").replace("\\", "/").strip("/")
            if text:
                return text
        return ""

    @staticmethod
    def _number(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _percent(cls, value: Any) -> float:
        number = cls._number(value, 0.0)
        return number * 100.0 if -1.0 <= number <= 1.0 else number

    @classmethod
    def _confidence(cls, value: Any) -> float:
        number = cls._number(value, 0.0)
        return number / 100.0 if number > 1.0 else number

    @staticmethod
    def _fingerprint(*parts: object) -> str:
        return hashlib.sha256("\x1f".join(map(str, parts)).encode()).hexdigest()
