from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from pathlib import PurePosixPath
from typing import Any

from .project_intelligence_models import ACTIVE_OPPORTUNITY_STATES
from .project_intelligence_ranker import ProjectOpportunityRanker
from .strategic_development_models import StrategicDevelopmentGoal


class StrategicDevelopmentPlanner:
    """Builds safe strategic goals from the B55 opportunity backlog."""

    def build_goals(
        self,
        opportunities: list[dict[str, Any]],
        *,
        existing_by_fingerprint: dict[str, dict[str, Any]] | None = None,
    ) -> list[StrategicDevelopmentGoal]:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for source in opportunities:
            if not isinstance(source, dict):
                continue
            target = self._target(source.get("target", ""))
            opportunity_id = str(source.get("opportunity_id", "")).strip()
            if not target or not opportunity_id:
                continue
            issue_type = str(
                source.get("issue_type", "PROJECT_IMPROVEMENT")
            ).upper().strip() or "PROJECT_IMPROVEMENT"
            grouped[(self._subsystem(target), issue_type)].append(dict(source))

        existing = dict(existing_by_fingerprint or {})
        goals: list[StrategicDevelopmentGoal] = []
        for (subsystem, issue_type), items in grouped.items():
            fingerprint = f"{subsystem.casefold()}::{issue_type.casefold()}"
            current = existing.get(fingerprint, {})
            goal_id = str(current.get("goal_id", "")).strip()
            if not goal_id:
                digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
                goal_id = f"strategic-{digest[:24]}"
            counts = self._counts(items)
            averages = self._averages(items)
            score = self._score(
                value=averages["value"],
                risk=averages["risk"],
                confidence=averages["confidence"],
                pending=counts["pending"],
                completed=counts["completed"],
                failed=counts["failed"],
            )
            status = self._status(counts)
            completed_at = str(current.get("completed_at", ""))
            if status in {"COMPLETED", "PARTIAL", "BLOCKED"}:
                completed_at = completed_at or self._now()
            else:
                completed_at = ""
            title = self._title(subsystem, issue_type)
            goals.append(StrategicDevelopmentGoal(
                goal_id=goal_id,
                fingerprint=fingerprint,
                title=title,
                objective=(
                    f"Systematycznie ulepszaj podsystem {subsystem} dla kategorii "
                    f"{issue_type}, wybierając najbezpieczniejsze zadania B55 i "
                    "zachowując pełną walidację, rollback oraz jawne zgody."
                ),
                subsystem=subsystem,
                issue_type=issue_type,
                opportunity_ids=[
                    str(item.get("opportunity_id", ""))
                    for item in items
                ],
                status=status,
                priority_score=score,
                value_score=round(averages["value"], 2),
                risk_score=round(averages["risk"], 2),
                confidence=round(averages["confidence"], 4),
                total_count=counts["total"],
                pending_count=counts["pending"],
                active_count=counts["active"],
                completed_count=counts["completed"],
                failed_count=counts["failed"],
                rejected_count=counts["rejected"],
                created_at=str(current.get("created_at", "")) or self._now(),
                updated_at=self._now(),
                completed_at=completed_at,
                metadata={
                    "source": "B57StrategicDevelopment",
                    "targets": sorted({
                        self._target(item.get("target", ""))
                        for item in items
                        if self._target(item.get("target", ""))
                    })[:100],
                },
            ))
        goals.sort(
            key=lambda item: (
                item.priority_score,
                item.confidence,
                -item.risk_score,
                item.pending_count,
                item.goal_id,
            ),
            reverse=True,
        )
        return goals

    def select_goal(
        self,
        goals: list[dict[str, Any]],
        *,
        min_score: float,
        max_risk: float,
        min_confidence: float,
    ) -> dict[str, Any] | None:
        candidates = [
            dict(item)
            for item in goals
            if isinstance(item, dict)
            and int(item.get("pending_count", 0) or 0) > 0
            and float(item.get("priority_score", 0.0) or 0.0)
            >= float(min_score)
            and float(item.get("risk_score", 0.0) or 0.0)
            <= float(max_risk)
            and float(item.get("confidence", 0.0) or 0.0)
            >= float(min_confidence)
            and str(item.get("status", "")).upper()
            not in {"REJECTED", "BLOCKED", "COMPLETED"}
        ]
        candidates.sort(
            key=lambda item: (
                float(item.get("priority_score", 0.0) or 0.0),
                float(item.get("confidence", 0.0) or 0.0),
                -float(item.get("risk_score", 0.0) or 0.0),
                int(item.get("pending_count", 0) or 0),
            ),
            reverse=True,
        )
        return candidates[0] if candidates else None

    def select_opportunity(
        self,
        goal: dict[str, Any],
        opportunities: list[dict[str, Any]],
        *,
        ranker: ProjectOpportunityRanker,
        min_score: float,
        max_risk: float,
        min_confidence: float,
    ) -> dict[str, Any] | None:
        allowed = {
            str(item).strip()
            for item in goal.get("opportunity_ids", [])
            if str(item).strip()
        }
        subset = [
            dict(item)
            for item in opportunities
            if isinstance(item, dict)
            and str(item.get("opportunity_id", "")).strip() in allowed
        ]
        return ranker.select_best(
            subset,
            min_score=min_score,
            max_risk=max_risk,
            min_confidence=min_confidence,
        )

    @staticmethod
    def _counts(items: list[dict[str, Any]]) -> dict[str, int]:
        counts = {
            "total": len(items),
            "pending": 0,
            "active": 0,
            "completed": 0,
            "failed": 0,
            "rejected": 0,
        }
        for item in items:
            status = str(item.get("status", "PENDING")).upper()
            if status in ACTIVE_OPPORTUNITY_STATES:
                counts["active"] += 1
            elif status == "COMPLETED":
                counts["completed"] += 1
            elif status == "FAILED":
                counts["failed"] += 1
            elif status in {"REJECTED", "CANCELLED"}:
                counts["rejected"] += 1
            else:
                counts["pending"] += 1
        return counts

    @staticmethod
    def _averages(items: list[dict[str, Any]]) -> dict[str, float]:
        count = max(1, len(items))
        return {
            "value": sum(float(item.get("value_score", 0.0) or 0.0) for item in items) / count,
            "risk": sum(float(item.get("risk_score", 0.0) or 0.0) for item in items) / count,
            "confidence": sum(float(item.get("confidence", 0.0) or 0.0) for item in items) / count,
        }

    @staticmethod
    def _score(
        *,
        value: float,
        risk: float,
        confidence: float,
        pending: int,
        completed: int,
        failed: int,
    ) -> float:
        score = (
            value
            + confidence * 25.0
            - risk * 0.50
            + min(20, pending) * 1.5
            + min(10, completed) * 0.5
            - min(10, failed) * 4.0
        )
        return round(min(100.0, max(-100.0, score)), 2)

    @staticmethod
    def _status(counts: dict[str, int]) -> str:
        if counts["active"]:
            return "ACTIVE"
        if counts["pending"]:
            return "PENDING"
        if counts["completed"] and not counts["failed"]:
            return "COMPLETED"
        if counts["completed"]:
            return "PARTIAL"
        if counts["failed"] or counts["rejected"]:
            return "BLOCKED"
        return "PENDING"

    @staticmethod
    def _subsystem(target: str) -> str:
        path = PurePosixPath(target)
        parent = path.parent.as_posix()
        return parent if parent and parent != "." else path.stem

    @staticmethod
    def _target(value: Any) -> str:
        target = str(value or "").strip().replace("\\", "/")
        while target.startswith("./"):
            target = target[2:]
        return target

    @staticmethod
    def _title(subsystem: str, issue_type: str) -> str:
        readable = issue_type.replace("_", " ").title()
        return f"{readable}: {subsystem}"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
