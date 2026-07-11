from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class PlanningMemoryEntry:
    memory_id: str
    session_id: str
    goal_id: str
    goal_title: str
    plan_status: str
    progress: float
    next_goal_id: str | None
    active_goal_ids: list[str]
    completed_goal_ids: list[str]
    blocked_goal_ids: list[str]
    lessons: list[str]
    errors: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanningMemorySummary:
    entries_count: int
    completed_plans: int
    failed_plans: int
    active_plans: int
    average_progress: float
    most_recent_goal_id: str | None
    recent_lessons: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlanningMemory:

    def __init__(
        self,
        storage_path: str | Path = (
            "data/planning/planning_memory.json"
        ),
        max_entries: int = 1000,
    ) -> None:

        self.storage_path = Path(storage_path)
        self.max_entries = max(
            1,
            int(max_entries),
        )

        self._entries: list[
            PlanningMemoryEntry
        ] = []

        self._ensure_storage()
        self.load()

    def remember(
        self,
        session: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_session = self._safe_dict(
            session
        )

        normalized_result = self._safe_dict(
            result
        )

        goal = self._safe_dict(
            normalized_session.get(
                "goal",
                {},
            )
        )

        plan = self._safe_dict(
            normalized_session.get(
                "plan",
                {},
            )
        )

        schedule = self._safe_dict(
            normalized_session.get(
                "schedule",
                {},
            )
        )

        execution = self._safe_dict(
            normalized_session.get(
                "execution",
                {},
            )
        )

        progress = self._resolve_progress(
            normalized_session,
            normalized_result,
        )

        status = self._resolve_status(
            normalized_session,
            normalized_result,
        )

        entry = PlanningMemoryEntry(
            memory_id=f"planning_memory_{uuid4().hex}",
            session_id=str(
                normalized_session.get(
                    "session_id",
                    "",
                )
            ),
            goal_id=str(
                goal.get(
                    "goal_id",
                    normalized_session.get(
                        "goal_id",
                        "",
                    ),
                )
            ),
            goal_title=str(
                goal.get(
                    "title",
                    goal.get(
                        "goal",
                        "",
                    ),
                )
            ),
            plan_status=status,
            progress=progress,
            next_goal_id=self._optional_string(
                schedule.get(
                    "next_goal_id",
                    plan.get(
                        "next_goal_id"
                    ),
                )
            ),
            active_goal_ids=self._safe_string_list(
                normalized_session.get(
                    "active_goal_ids",
                    execution.get(
                        "active_goal_ids",
                        [],
                    ),
                )
            ),
            completed_goal_ids=self._safe_string_list(
                normalized_session.get(
                    "completed_goal_ids",
                    execution.get(
                        "completed_goal_ids",
                        [],
                    ),
                )
            ),
            blocked_goal_ids=self._safe_string_list(
                normalized_session.get(
                    "blocked_goal_ids",
                    schedule.get(
                        "blocked_goal_ids",
                        [],
                    ),
                )
            ),
            lessons=self._collect_lessons(
                normalized_session,
                normalized_result,
            ),
            errors=self._collect_errors(
                normalized_session,
                normalized_result,
            ),
            metadata={
                "memory_version": "1.0.0",
                "plan_id": plan.get(
                    "plan_id"
                ),
                "schedule_batch_id": schedule.get(
                    "schedule_batch_id"
                ),
                "result_available": bool(
                    normalized_result
                ),
            },
            created_at=self._utc_now(),
        )

        self._entries.append(entry)
        self._trim_entries()
        self.save()

        return entry.to_dict()

    def add(
        self,
        session: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.remember(
            session=session,
            result=result,
        )

    def record(
        self,
        session: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.remember(
            session=session,
            result=result,
        )

    def update(
        self,
        session_id: str,
        plan_status: str | None = None,
        progress: float | None = None,
        next_goal_id: str | None = None,
        active_goal_ids: list[str] | None = None,
        completed_goal_ids: list[str] | None = None,
        blocked_goal_ids: list[str] | None = None,
        lessons: list[str] | None = None,
        errors: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        entry = self._find_entry(
            session_id
        )

        if entry is None:
            return None

        if plan_status is not None:
            entry.plan_status = str(
                plan_status
            ).upper()

        if progress is not None:
            entry.progress = round(
                max(
                    0.0,
                    min(
                        1.0,
                        float(progress),
                    ),
                ),
                4,
            )

        if next_goal_id is not None:
            entry.next_goal_id = (
                self._optional_string(
                    next_goal_id
                )
            )

        if active_goal_ids is not None:
            entry.active_goal_ids = (
                self._safe_string_list(
                    active_goal_ids
                )
            )

        if completed_goal_ids is not None:
            entry.completed_goal_ids = (
                self._safe_string_list(
                    completed_goal_ids
                )
            )

        if blocked_goal_ids is not None:
            entry.blocked_goal_ids = (
                self._safe_string_list(
                    blocked_goal_ids
                )
            )

        if lessons is not None:
            entry.lessons = self._unique_strings(
                entry.lessons + lessons
            )

        if errors is not None:
            entry.errors = self._unique_strings(
                entry.errors + errors
            )

        if metadata is not None:
            entry.metadata.update(
                dict(metadata)
            )

        entry.metadata["updated_at"] = (
            self._utc_now()
        )

        self.save()
        return entry.to_dict()

    def get(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        entry = self._find_entry(
            session_id
        )

        if entry is None:
            return None

        return entry.to_dict()

    def last(
        self,
    ) -> dict[str, Any] | None:

        if not self._entries:
            return None

        return self._entries[-1].to_dict()

    def recent(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:

        normalized_limit = max(
            0,
            int(limit),
        )

        if normalized_limit == 0:
            return []

        return [
            entry.to_dict()
            for entry in self._entries[
                -normalized_limit:
            ]
        ]

    def search(
        self,
        goal_id: str | None = None,
        status: str | None = None,
        minimum_progress: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        normalized_goal_id = (
            str(goal_id).strip()
            if goal_id is not None
            else None
        )

        normalized_status = (
            str(status).strip().upper()
            if status is not None
            else None
        )

        result: list[
            PlanningMemoryEntry
        ] = []

        for entry in reversed(
            self._entries
        ):
            if (
                normalized_goal_id
                and entry.goal_id
                != normalized_goal_id
            ):
                continue

            if (
                normalized_status
                and entry.plan_status
                != normalized_status
            ):
                continue

            if (
                minimum_progress is not None
                and entry.progress
                < float(minimum_progress)
            ):
                continue

            result.append(entry)

            if len(result) >= max(
                1,
                int(limit),
            ):
                break

        return [
            entry.to_dict()
            for entry in result
        ]

    def find_similar(
        self,
        goal: dict[str, Any],
        limit: int = 5,
    ) -> list[dict[str, Any]]:

        normalized_goal = self._safe_dict(
            goal
        )

        goal_id = str(
            normalized_goal.get(
                "goal_id",
                "",
            )
        ).strip()

        title_words = {
            word.lower()
            for word in str(
                normalized_goal.get(
                    "title",
                    normalized_goal.get(
                        "goal",
                        "",
                    ),
                )
            ).split()
            if word.strip()
        }

        scored: list[
            tuple[float, PlanningMemoryEntry]
        ] = []

        for entry in self._entries:
            score = 0.0

            if goal_id and entry.goal_id == goal_id:
                score += 5.0

            entry_words = {
                word.lower()
                for word in entry.goal_title.split()
                if word.strip()
            }

            score += len(
                title_words & entry_words
            ) * 0.5

            if (
                entry.plan_status
                == "COMPLETED"
            ):
                score += 0.5

            if score > 0:
                scored.append(
                    (
                        score,
                        entry,
                    )
                )

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].created_at,
            ),
            reverse=True,
        )

        return [
            {
                "similarity_score": round(
                    score,
                    2,
                ),
                "entry": entry.to_dict(),
            }
            for score, entry in scored[
                :max(
                    1,
                    int(limit),
                )
            ]
        ]

    def summary(
        self,
    ) -> dict[str, Any]:

        completed = [
            entry
            for entry in self._entries
            if entry.plan_status
            == "COMPLETED"
        ]

        failed = [
            entry
            for entry in self._entries
            if entry.plan_status
            in {
                "FAILED",
                "CANCELLED",
            }
        ]

        active = [
            entry
            for entry in self._entries
            if entry.plan_status
            in {
                "RUNNING",
                "ACTIVE",
                "PAUSED",
                "BLOCKED",
                "READY",
            }
        ]

        average_progress = 0.0

        if self._entries:
            average_progress = sum(
                entry.progress
                for entry in self._entries
            ) / len(self._entries)

        recent_lessons: list[str] = []

        for entry in reversed(
            self._entries
        ):
            recent_lessons.extend(
                entry.lessons
            )

            if len(recent_lessons) >= 10:
                break

        result = PlanningMemorySummary(
            entries_count=len(
                self._entries
            ),
            completed_plans=len(
                completed
            ),
            failed_plans=len(
                failed
            ),
            active_plans=len(
                active
            ),
            average_progress=round(
                average_progress,
                4,
            ),
            most_recent_goal_id=(
                self._entries[-1].goal_id
                if self._entries
                else None
            ),
            recent_lessons=self._unique_strings(
                recent_lessons
            )[:10],
            metadata={
                "memory_version": "1.0.0",
                "storage_path": str(
                    self.storage_path
                ),
                "max_entries": self.max_entries,
            },
        )

        return result.to_dict()

    def save(
        self,
    ) -> None:

        self._ensure_storage()

        payload = {
            "version": "1.0.0",
            "saved_at": self._utc_now(),
            "entries": [
                entry.to_dict()
                for entry in self._entries
            ],
        }

        temporary_path = (
            self.storage_path.with_suffix(
                self.storage_path.suffix
                + ".tmp"
            )
        )

        temporary_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(
            self.storage_path
        )

    def load(
        self,
    ) -> None:

        if not self.storage_path.exists():
            self._entries = []
            return

        try:
            raw_text = self.storage_path.read_text(
                encoding="utf-8"
            )

            if not raw_text.strip():
                self._entries = []
                return

            payload = json.loads(
                raw_text
            )

            raw_entries = payload.get(
                "entries",
                [],
            )

            loaded: list[
                PlanningMemoryEntry
            ] = []

            if isinstance(
                raw_entries,
                list,
            ):
                for raw_entry in raw_entries:
                    if not isinstance(
                        raw_entry,
                        dict,
                    ):
                        continue

                    try:
                        loaded.append(
                            self._entry_from_dict(
                                raw_entry
                            )
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):
                        continue

            self._entries = loaded
            self._trim_entries()

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self._entries = []

    def clear(
        self,
    ) -> None:

        self._entries = []
        self.save()

    def _entry_from_dict(
        self,
        data: dict[str, Any],
    ) -> PlanningMemoryEntry:

        return PlanningMemoryEntry(
            memory_id=str(
                data.get(
                    "memory_id",
                    f"planning_memory_{uuid4().hex}",
                )
            ),
            session_id=str(
                data.get(
                    "session_id",
                    "",
                )
            ),
            goal_id=str(
                data.get(
                    "goal_id",
                    "",
                )
            ),
            goal_title=str(
                data.get(
                    "goal_title",
                    "",
                )
            ),
            plan_status=str(
                data.get(
                    "plan_status",
                    "UNKNOWN",
                )
            ).upper(),
            progress=max(
                0.0,
                min(
                    1.0,
                    self._safe_float(
                        data.get(
                            "progress",
                            0.0,
                        ),
                        0.0,
                    ),
                ),
            ),
            next_goal_id=self._optional_string(
                data.get(
                    "next_goal_id"
                )
            ),
            active_goal_ids=self._safe_string_list(
                data.get(
                    "active_goal_ids",
                    [],
                )
            ),
            completed_goal_ids=self._safe_string_list(
                data.get(
                    "completed_goal_ids",
                    [],
                )
            ),
            blocked_goal_ids=self._safe_string_list(
                data.get(
                    "blocked_goal_ids",
                    [],
                )
            ),
            lessons=self._unique_strings(
                self._safe_list(
                    data.get(
                        "lessons",
                        [],
                    )
                )
            ),
            errors=self._unique_strings(
                self._safe_list(
                    data.get(
                        "errors",
                        [],
                    )
                )
            ),
            metadata=self._safe_dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
            created_at=str(
                data.get(
                    "created_at",
                    self._utc_now(),
                )
            ),
        )

    def _resolve_progress(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> float:

        candidates = [
            result.get("progress"),
            session.get("progress"),
            self._safe_dict(
                session.get(
                    "execution",
                    {},
                )
            ).get("progress"),
            self._safe_dict(
                session.get(
                    "plan",
                    {},
                )
            ).get("progress"),
        ]

        for value in candidates:
            if value is None:
                continue

            return round(
                max(
                    0.0,
                    min(
                        1.0,
                        self._safe_float(
                            value,
                            0.0,
                        ),
                    ),
                ),
                4,
            )

        return 0.0

    def _resolve_status(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> str:

        candidates = [
            result.get("status"),
            session.get("status"),
            self._safe_dict(
                session.get(
                    "plan",
                    {},
                )
            ).get("status"),
        ]

        for value in candidates:
            if value is None:
                continue

            normalized = str(
                value
            ).strip().upper()

            if normalized:
                return normalized

        return "UNKNOWN"

    def _collect_lessons(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        lessons: list[Any] = []

        lessons.extend(
            self._safe_list(
                session.get(
                    "lessons",
                    [],
                )
            )
        )

        lessons.extend(
            self._safe_list(
                result.get(
                    "lessons",
                    [],
                )
            )
        )

        return self._unique_strings(
            lessons
        )

    def _collect_errors(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        errors: list[Any] = []

        errors.extend(
            self._safe_list(
                session.get(
                    "errors",
                    [],
                )
            )
        )

        errors.extend(
            self._safe_list(
                result.get(
                    "errors",
                    [],
                )
            )
        )

        for source in [
            session,
            result,
            self._safe_dict(
                session.get(
                    "execution",
                    {},
                )
            ),
        ]:
            error = source.get(
                "error"
            )

            if error:
                errors.append(error)

        return self._unique_strings(
            errors
        )

    def _find_entry(
        self,
        session_id: str,
    ) -> PlanningMemoryEntry | None:

        normalized_session_id = str(
            session_id
        ).strip()

        for entry in reversed(
            self._entries
        ):
            if entry.session_id == normalized_session_id:
                return entry

        return None

    def _trim_entries(
        self,
    ) -> None:

        if len(
            self._entries
        ) <= self.max_entries:
            return

        self._entries = self._entries[
            -self.max_entries:
        ]

    def _ensure_storage(
        self,
    ) -> None:

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.storage_path.exists():
            self.storage_path.write_text(
                json.dumps(
                    {
                        "version": "1.0.0",
                        "saved_at": self._utc_now(),
                        "entries": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def _safe_float(
        self,
        value: Any,
        default: float,
    ) -> float:

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(value, list):
            return list(value)

        if isinstance(value, tuple):
            return list(value)

        if isinstance(value, set):
            return list(value)

        if value is None:
            return []

        return [value]

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(value, dict):
            return dict(value)

        return {}

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        return self._unique_strings(
            self._safe_list(value)
        )

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return normalized or None

    def _unique_strings(
        self,
        values: list[Any],
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            text = str(
                value
            ).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(text)

        return result

    def _utc_now(
        self,
    ) -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()
