"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class GoalStatus(str, Enum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class GoalPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GoalTimeframe(str, Enum):
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    LONG_TERM = "LONG_TERM"
    CONTINUOUS = "CONTINUOUS"


class GoalType(str, Enum):
    PROJECT = "PROJECT"
    FEATURE = "FEATURE"
    REFACTOR = "REFACTOR"
    RESEARCH = "RESEARCH"
    MAINTENANCE = "MAINTENANCE"
    SELF_IMPROVEMENT = "SELF_IMPROVEMENT"
    OPERATIONS = "OPERATIONS"
    LEARNING = "LEARNING"
    UNKNOWN = "UNKNOWN"


@dataclass
class Goal:
    goal_id: str
    title: str
    description: str
    goal_type: str
    priority: str
    timeframe: str
    status: str
    progress: float
    parent_goal_id: str | None
    child_goal_ids: list[str]
    dependencies: list[str]
    blockers: list[str]
    tags: list[str]
    success_criteria: list[str]
    notes: list[str]
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    deadline: str | None = None
    estimated_effort: float | None = None
    owner: str = "JARVIS"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GoalManager:

    def __init__(
        self,
        storage_path: str | Path = "data/planning/goals.json",
        auto_save: bool = True,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.auto_save = bool(auto_save)
        self._goals: dict[str, Goal] = {}
        self._ensure_storage()
        self.load()

    def create_goal(
        self,
        title: str,
        description: str = "",
        goal_type: str = GoalType.UNKNOWN.value,
        priority: str = GoalPriority.MEDIUM.value,
        timeframe: str = GoalTimeframe.MEDIUM_TERM.value,
        parent_goal_id: str | None = None,
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
        success_criteria: list[str] | None = None,
        deadline: str | None = None,
        estimated_effort: float | None = None,
        owner: str = "JARVIS",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_title = str(title).strip()
        if not normalized_title:
            raise ValueError("GoalManager wymaga niepustego tytułu celu.")

        normalized_parent = self._optional_string(parent_goal_id)
        if normalized_parent and normalized_parent not in self._goals:
            raise ValueError(
                f"Nie znaleziono celu nadrzędnego: {normalized_parent}"
            )

        goal_id = f"goal_{uuid4().hex}"
        now = self._utc_now()

        goal = Goal(
            goal_id=goal_id,
            title=normalized_title,
            description=str(description).strip(),
            goal_type=self._enum_value(goal_type, GoalType, GoalType.UNKNOWN.value),
            priority=self._enum_value(priority, GoalPriority, GoalPriority.MEDIUM.value),
            timeframe=self._enum_value(
                timeframe,
                GoalTimeframe,
                GoalTimeframe.MEDIUM_TERM.value,
            ),
            status=GoalStatus.CREATED.value,
            progress=0.0,
            parent_goal_id=normalized_parent,
            child_goal_ids=[],
            dependencies=self._valid_goal_ids(dependencies or []),
            blockers=[],
            tags=self._unique_strings(tags or []),
            success_criteria=self._unique_strings(success_criteria or []),
            notes=[],
            created_at=now,
            updated_at=now,
            deadline=self._optional_string(deadline),
            estimated_effort=self._optional_float(estimated_effort),
            owner=str(owner).strip() or "JARVIS",
            metadata={"goal_manager_version": "1.0.0", **(metadata or {})},
        )

        self._goals[goal_id] = goal

        if normalized_parent:
            parent = self._goals[normalized_parent]
            parent.child_goal_ids.append(goal_id)
            parent.updated_at = now

        self._save_if_enabled()
        return goal.to_dict()

    def add_goal(self, title: str, description: str = "", **kwargs: Any) -> dict[str, Any]:
        return self.create_goal(title=title, description=description, **kwargs)

    def add_child_goal(
        self,
        parent_goal_id: str,
        title: str,
        description: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.create_goal(
            title=title,
            description=description,
            parent_goal_id=parent_goal_id,
            **kwargs,
        )

    def update_goal(self, goal_id: str, **changes: Any) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        if goal is None:
            return None

        if "title" in changes:
            title = str(changes["title"]).strip()
            if not title:
                raise ValueError("Tytuł celu nie może być pusty.")
            goal.title = title

        if "description" in changes:
            goal.description = str(changes["description"]).strip()
        if "goal_type" in changes:
            goal.goal_type = self._enum_value(changes["goal_type"], GoalType, goal.goal_type)
        if "priority" in changes:
            goal.priority = self._enum_value(changes["priority"], GoalPriority, goal.priority)
        if "timeframe" in changes:
            goal.timeframe = self._enum_value(changes["timeframe"], GoalTimeframe, goal.timeframe)
        if "deadline" in changes:
            goal.deadline = self._optional_string(changes["deadline"])
        if "estimated_effort" in changes:
            goal.estimated_effort = self._optional_float(changes["estimated_effort"])
        if "owner" in changes:
            goal.owner = str(changes["owner"]).strip() or goal.owner
        if "tags" in changes:
            goal.tags = self._unique_strings(changes["tags"])
        if "success_criteria" in changes:
            goal.success_criteria = self._unique_strings(changes["success_criteria"])
        if isinstance(changes.get("metadata"), dict):
            goal.metadata.update(changes["metadata"])

        goal.updated_at = self._utc_now()
        self._save_if_enabled()
        return goal.to_dict()

    def set_status(self, goal_id: str, status: str) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        if goal is None:
            return None

        normalized = self._enum_value(status, GoalStatus, goal.status)
        now = self._utc_now()

        if normalized == GoalStatus.ACTIVE.value and goal.started_at is None:
            goal.started_at = now
        if normalized == GoalStatus.COMPLETED.value:
            goal.progress = 1.0
            goal.completed_at = now
        if normalized in {
            GoalStatus.FAILED.value,
            GoalStatus.CANCELLED.value,
            GoalStatus.ARCHIVED.value,
        }:
            goal.completed_at = goal.completed_at or now

        goal.status = normalized
        goal.updated_at = now
        self._save_if_enabled()
        self._update_parent_progress(goal.goal_id)
        return goal.to_dict()

    def activate_goal(self, goal_id: str) -> dict[str, Any] | None:
        return self.set_status(goal_id, GoalStatus.ACTIVE.value)

    def pause_goal(self, goal_id: str) -> dict[str, Any] | None:
        return self.set_status(goal_id, GoalStatus.PAUSED.value)

    def complete_goal(self, goal_id: str) -> dict[str, Any] | None:
        return self.set_status(goal_id, GoalStatus.COMPLETED.value)

    def fail_goal(self, goal_id: str, reason: str | None = None) -> dict[str, Any] | None:
        if reason:
            self.add_note(goal_id, f"Powód niepowodzenia: {reason}")
        return self.set_status(goal_id, GoalStatus.FAILED.value)

    def cancel_goal(self, goal_id: str, reason: str | None = None) -> dict[str, Any] | None:
        if reason:
            self.add_note(goal_id, f"Powód anulowania: {reason}")
        return self.set_status(goal_id, GoalStatus.CANCELLED.value)

    def set_progress(self, goal_id: str, progress: float) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        if goal is None:
            return None

        goal.progress = round(max(0.0, min(1.0, float(progress))), 4)
        now = self._utc_now()

        if goal.progress >= 1.0:
            goal.status = GoalStatus.COMPLETED.value
            goal.completed_at = now
        elif goal.progress > 0.0 and goal.status in {
            GoalStatus.CREATED.value,
            GoalStatus.PLANNED.value,
            GoalStatus.PAUSED.value,
        }:
            goal.status = GoalStatus.ACTIVE.value
            goal.started_at = goal.started_at or now

        goal.updated_at = now
        self._save_if_enabled()
        self._update_parent_progress(goal.goal_id)
        return goal.to_dict()

    def increment_progress(self, goal_id: str, amount: float) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        if goal is None:
            return None
        return self.set_progress(goal_id, goal.progress + float(amount))

    def add_dependency(self, goal_id: str, dependency_goal_id: str) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        dependency = self._goal(dependency_goal_id)
        if goal is None or dependency is None:
            return None
        if goal.goal_id == dependency.goal_id:
            raise ValueError("Cel nie może zależeć od samego siebie.")
        if self._would_create_cycle(goal.goal_id, dependency.goal_id):
            raise ValueError("Dodanie zależności utworzyłoby cykl.")
        if dependency.goal_id not in goal.dependencies:
            goal.dependencies.append(dependency.goal_id)
            goal.updated_at = self._utc_now()
        self._save_if_enabled()
        return goal.to_dict()

    def remove_dependency(self, goal_id: str, dependency_goal_id: str) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        if goal is None:
            return None
        goal.dependencies = [item for item in goal.dependencies if item != dependency_goal_id]
        goal.updated_at = self._utc_now()
        self._save_if_enabled()
        return goal.to_dict()

    def add_blocker(self, goal_id: str, blocker: str) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        if goal is None:
            return None
        normalized = str(blocker).strip()
        if normalized:
            goal.blockers = self._unique_strings(goal.blockers + [normalized])
            if goal.status not in {
                GoalStatus.COMPLETED.value,
                GoalStatus.CANCELLED.value,
                GoalStatus.FAILED.value,
            }:
                goal.status = GoalStatus.BLOCKED.value
            goal.updated_at = self._utc_now()
        self._save_if_enabled()
        return goal.to_dict()

    def remove_blocker(self, goal_id: str, blocker: str) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        if goal is None:
            return None
        normalized = str(blocker).strip().lower()
        goal.blockers = [item for item in goal.blockers if item.lower() != normalized]
        if not goal.blockers and goal.status == GoalStatus.BLOCKED.value:
            goal.status = GoalStatus.PAUSED.value
        goal.updated_at = self._utc_now()
        self._save_if_enabled()
        return goal.to_dict()

    def add_note(self, goal_id: str, note: str) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        if goal is None:
            return None
        normalized = str(note).strip()
        if normalized:
            goal.notes.append(f"[{self._utc_now()}] {normalized}")
            goal.updated_at = self._utc_now()
        self._save_if_enabled()
        return goal.to_dict()

    def get_goal(self, goal_id: str) -> dict[str, Any] | None:
        goal = self._goal(goal_id)
        return goal.to_dict() if goal else None

    def get_children(self, goal_id: str) -> list[dict[str, Any]]:
        goal = self._goal(goal_id)
        if goal is None:
            return []
        return [
            self._goals[child_id].to_dict()
            for child_id in goal.child_goal_ids
            if child_id in self._goals
        ]

    def get_dependencies(self, goal_id: str) -> list[dict[str, Any]]:
        goal = self._goal(goal_id)
        if goal is None:
            return []
        return [
            self._goals[item].to_dict()
            for item in goal.dependencies
            if item in self._goals
        ]

    def dependencies_completed(self, goal_id: str) -> bool:
        goal = self._goal(goal_id)
        if goal is None:
            return False
        return all(
            self._goals[item].status == GoalStatus.COMPLETED.value
            for item in goal.dependencies
            if item in self._goals
        )

    def is_ready(self, goal_id: str) -> bool:
        goal = self._goal(goal_id)
        if goal is None:
            return False
        if goal.status in {
            GoalStatus.COMPLETED.value,
            GoalStatus.CANCELLED.value,
            GoalStatus.FAILED.value,
            GoalStatus.ARCHIVED.value,
        }:
            return False
        return not goal.blockers and self.dependencies_completed(goal_id)

    def list_goals(
        self,
        status: str | None = None,
        priority: str | None = None,
        goal_type: str | None = None,
        timeframe: str | None = None,
        parent_goal_id: str | None = None,
        tag: str | None = None,
        ready_only: bool = False,
    ) -> list[dict[str, Any]]:
        filters = {
            "status": self._optional_upper(status),
            "priority": self._optional_upper(priority),
            "goal_type": self._optional_upper(goal_type),
            "timeframe": self._optional_upper(timeframe),
        }
        normalized_tag = self._optional_string(tag)
        normalized_tag = normalized_tag.lower() if normalized_tag else None

        result: list[Goal] = []
        for goal in self._goals.values():
            if filters["status"] and goal.status != filters["status"]:
                continue
            if filters["priority"] and goal.priority != filters["priority"]:
                continue
            if filters["goal_type"] and goal.goal_type != filters["goal_type"]:
                continue
            if filters["timeframe"] and goal.timeframe != filters["timeframe"]:
                continue
            if parent_goal_id is not None and goal.parent_goal_id != parent_goal_id:
                continue
            if normalized_tag and normalized_tag not in {item.lower() for item in goal.tags}:
                continue
            if ready_only and not self.is_ready(goal.goal_id):
                continue
            result.append(goal)

        result.sort(key=self._sort_key)
        return [goal.to_dict() for goal in result]

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        normalized = str(query).strip().lower()
        if not normalized:
            return []

        matches: list[tuple[int, Goal]] = []
        for goal in self._goals.values():
            score = 0
            if normalized in goal.title.lower():
                score += 5
            if normalized in goal.description.lower():
                score += 3
            if any(normalized in item.lower() for item in goal.tags):
                score += 2
            if any(normalized in item.lower() for item in goal.notes):
                score += 1
            if score:
                matches.append((score, goal))

        matches.sort(key=lambda item: (-item[0], self._sort_key(item[1])))
        return [goal.to_dict() for _, goal in matches[: max(1, int(limit))]]

    def delete_goal(self, goal_id: str, delete_children: bool = False) -> bool:
        goal = self._goal(goal_id)
        if goal is None:
            return False
        if goal.child_goal_ids and not delete_children:
            raise ValueError("Cel posiada cele podrzędne. Użyj delete_children=True.")

        if delete_children:
            for child_id in list(goal.child_goal_ids):
                self.delete_goal(child_id, delete_children=True)

        if goal.parent_goal_id in self._goals:
            parent = self._goals[goal.parent_goal_id]
            parent.child_goal_ids = [item for item in parent.child_goal_ids if item != goal.goal_id]
            parent.updated_at = self._utc_now()

        for item in self._goals.values():
            item.dependencies = [dep for dep in item.dependencies if dep != goal.goal_id]

        del self._goals[goal.goal_id]
        self._save_if_enabled()
        return True

    def summary(self) -> dict[str, Any]:
        status_counts = {item.value: 0 for item in GoalStatus}
        priority_counts = {item.value: 0 for item in GoalPriority}

        for goal in self._goals.values():
            status_counts[goal.status] = status_counts.get(goal.status, 0) + 1
            priority_counts[goal.priority] = priority_counts.get(goal.priority, 0) + 1

        average_progress = 0.0
        if self._goals:
            average_progress = sum(goal.progress for goal in self._goals.values()) / len(self._goals)

        return {
            "goals_count": len(self._goals),
            "ready_goals_count": sum(1 for goal in self._goals.values() if self.is_ready(goal.goal_id)),
            "blocked_goals_count": status_counts.get(GoalStatus.BLOCKED.value, 0),
            "completed_goals_count": status_counts.get(GoalStatus.COMPLETED.value, 0),
            "average_progress": round(average_progress, 4),
            "status_counts": status_counts,
            "priority_counts": priority_counts,
            "storage_path": str(self.storage_path),
            "manager_version": "1.0.0",
        }

    def save(self) -> None:
        self._ensure_storage()
        payload = {
            "version": "1.0.0",
            "saved_at": self._utc_now(),
            "goals": [goal.to_dict() for goal in self._goals.values()],
        }
        temporary = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.storage_path)

    def load(self) -> None:
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
            raw_goals = payload.get("goals", [])
            loaded: dict[str, Goal] = {}
            if isinstance(raw_goals, list):
                for raw in raw_goals:
                    if not isinstance(raw, dict):
                        continue
                    try:
                        goal = self._from_dict(raw)
                        loaded[goal.goal_id] = goal
                    except (TypeError, ValueError):
                        continue
            self._goals = loaded
            self._repair_relations()
        except (OSError, json.JSONDecodeError):
            self._goals = {}

    def clear(self) -> None:
        self._goals = {}
        self._save_if_enabled()

    def _from_dict(self, data: dict[str, Any]) -> Goal:
        return Goal(
            goal_id=str(data.get("goal_id", f"goal_{uuid4().hex}")),
            title=str(data.get("title", "Nieznany cel")),
            description=str(data.get("description", "")),
            goal_type=self._enum_value(data.get("goal_type"), GoalType, GoalType.UNKNOWN.value),
            priority=self._enum_value(data.get("priority"), GoalPriority, GoalPriority.MEDIUM.value),
            timeframe=self._enum_value(
                data.get("timeframe"),
                GoalTimeframe,
                GoalTimeframe.MEDIUM_TERM.value,
            ),
            status=self._enum_value(data.get("status"), GoalStatus, GoalStatus.CREATED.value),
            progress=max(0.0, min(1.0, self._safe_float(data.get("progress"), 0.0))),
            parent_goal_id=self._optional_string(data.get("parent_goal_id")),
            child_goal_ids=self._unique_strings(data.get("child_goal_ids", [])),
            dependencies=self._unique_strings(data.get("dependencies", [])),
            blockers=self._unique_strings(data.get("blockers", [])),
            tags=self._unique_strings(data.get("tags", [])),
            success_criteria=self._unique_strings(data.get("success_criteria", [])),
            notes=self._unique_strings(data.get("notes", [])),
            created_at=str(data.get("created_at", self._utc_now())),
            updated_at=str(data.get("updated_at", self._utc_now())),
            started_at=self._optional_string(data.get("started_at")),
            completed_at=self._optional_string(data.get("completed_at")),
            deadline=self._optional_string(data.get("deadline")),
            estimated_effort=self._optional_float(data.get("estimated_effort")),
            owner=str(data.get("owner", "JARVIS")),
            metadata=dict(data.get("metadata")) if isinstance(data.get("metadata"), dict) else {},
        )

    def _goal(self, goal_id: str) -> Goal | None:
        return self._goals.get(str(goal_id).strip())

    def _update_parent_progress(self, child_goal_id: str) -> None:
        child = self._goal(child_goal_id)
        if child is None or child.parent_goal_id not in self._goals:
            return

        parent = self._goals[child.parent_goal_id]
        children = [self._goals[item] for item in parent.child_goal_ids if item in self._goals]
        if not children:
            return

        parent.progress = round(sum(item.progress for item in children) / len(children), 4)
        now = self._utc_now()

        if all(item.status == GoalStatus.COMPLETED.value for item in children):
            parent.status = GoalStatus.COMPLETED.value
            parent.completed_at = now
        elif parent.progress > 0.0:
            parent.status = GoalStatus.ACTIVE.value
            parent.started_at = parent.started_at or now

        parent.updated_at = now
        self._save_if_enabled()

        if parent.parent_goal_id:
            self._update_parent_progress(parent.goal_id)

    def _would_create_cycle(self, goal_id: str, dependency_goal_id: str) -> bool:
        stack = [dependency_goal_id]
        visited: set[str] = set()
        while stack:
            current = stack.pop()
            if current == goal_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            goal = self._goals.get(current)
            if goal:
                stack.extend(goal.dependencies)
        return False

    def _repair_relations(self) -> None:
        for goal in self._goals.values():
            goal.child_goal_ids = [item for item in goal.child_goal_ids if item in self._goals]
            goal.dependencies = [
                item
                for item in goal.dependencies
                if item in self._goals and item != goal.goal_id
            ]
            if goal.parent_goal_id not in self._goals:
                goal.parent_goal_id = None

        for goal in self._goals.values():
            if goal.parent_goal_id:
                parent = self._goals[goal.parent_goal_id]
                if goal.goal_id not in parent.child_goal_ids:
                    parent.child_goal_ids.append(goal.goal_id)

    def _valid_goal_ids(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in self._unique_strings(values):
            if value not in self._goals:
                raise ValueError(f"Nie znaleziono celu zależnego: {value}")
            result.append(value)
        return result

    def _sort_key(self, goal: Goal) -> tuple[int, int, str]:
        priority_order = {
            GoalPriority.CRITICAL.value: 0,
            GoalPriority.HIGH.value: 1,
            GoalPriority.MEDIUM.value: 2,
            GoalPriority.LOW.value: 3,
        }
        status_order = {
            GoalStatus.ACTIVE.value: 0,
            GoalStatus.BLOCKED.value: 1,
            GoalStatus.PLANNED.value: 2,
            GoalStatus.CREATED.value: 3,
            GoalStatus.PAUSED.value: 4,
            GoalStatus.FAILED.value: 5,
            GoalStatus.CANCELLED.value: 6,
            GoalStatus.COMPLETED.value: 7,
            GoalStatus.ARCHIVED.value: 8,
        }
        return (
            priority_order.get(goal.priority, 99),
            status_order.get(goal.status, 99),
            goal.created_at,
        )

    def _enum_value(self, value: Any, enum_class: type[Enum], default: str) -> str:
        normalized = str(value or "").strip().upper()
        valid = {item.value for item in enum_class}
        return normalized if normalized in valid else default

    def _unique_strings(self, values: Any) -> list[str]:
        if not isinstance(values, (list, tuple, set)):
            return []
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
        return result

    def _optional_string(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _optional_upper(self, value: Any) -> str | None:
        text = self._optional_string(value)
        return text.upper() if text else None

    def _optional_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text(
                json.dumps(
                    {
                        "version": "1.0.0",
                        "saved_at": self._utc_now(),
                        "goals": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def _save_if_enabled(self) -> None:
        if self.auto_save:
            self.save()

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
