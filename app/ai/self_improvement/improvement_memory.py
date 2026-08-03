"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class ImprovementMemoryEntry:
    memory_id: str
    session_id: str
    objective: str
    status: str
    decision: str
    selected_proposal_id: str | None
    selected_proposal_title: str | None
    selected_category: str | None
    selected_priority: str | None
    proposal_score: float
    execution_status: str | None
    lessons: list[str]
    errors: list[str]
    warnings: list[str]
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImprovementMemorySummary:
    entries_count: int
    completed_sessions: int
    failed_sessions: int
    waiting_sessions: int
    no_action_sessions: int
    average_score: float
    categories: dict[str, int]
    priorities: dict[str, int]
    recent_lessons: list[str]
    recent_errors: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImprovementMemory:

    def __init__(
        self,
        storage_path: str | Path = (
            "data/self_improvement/"
            "improvement_memory.json"
        ),
        max_entries: int = 1000,
    ) -> None:

        self.storage_path = Path(
            storage_path
        )

        self.max_entries = max(
            1,
            int(max_entries),
        )

        self._entries: list[
            ImprovementMemoryEntry
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

        selected = self._safe_dict(
            normalized_session.get(
                "selected_proposal",
                normalized_result.get(
                    "selected_proposal",
                    {},
                ),
            )
        )

        execution = self._safe_dict(
            normalized_session.get(
                "execution",
                normalized_result.get(
                    "execution",
                    {},
                ),
            )
        )

        entry = ImprovementMemoryEntry(
            memory_id=(
                f"improvement_memory_{uuid4().hex}"
            ),
            session_id=str(
                normalized_session.get(
                    "session_id",
                    normalized_result.get(
                        "session_id",
                        "",
                    ),
                )
            ),
            objective=str(
                self._safe_dict(
                    normalized_session.get(
                        "metadata",
                        {},
                    )
                ).get(
                    "objective",
                    normalized_session.get(
                        "objective",
                        "",
                    ),
                )
            ),
            status=self._resolve_status(
                normalized_session,
                normalized_result,
            ),
            decision=self._resolve_decision(
                normalized_session,
                normalized_result,
            ),
            selected_proposal_id=(
                self._optional_string(
                    selected.get(
                        "proposal_id"
                    )
                )
            ),
            selected_proposal_title=(
                self._optional_string(
                    selected.get(
                        "title"
                    )
                )
            ),
            selected_category=(
                self._optional_string(
                    selected.get(
                        "category"
                    )
                )
            ),
            selected_priority=(
                self._optional_string(
                    selected.get(
                        "priority"
                    )
                )
            ),
            proposal_score=round(
                max(
                    0.0,
                    min(
                        100.0,
                        self._safe_float(
                            selected.get(
                                "score",
                                0.0,
                            ),
                            0.0,
                        ),
                    ),
                ),
                2,
            ),
            execution_status=(
                self._optional_string(
                    execution.get(
                        "status"
                    )
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
            warnings=self._collect_warnings(
                normalized_session,
                normalized_result,
            ),
            created_at=self._utc_now(),
            metadata={
                "memory_version": "1.0.0",
                "proposal_count": len(
                    self._safe_list(
                        normalized_session.get(
                            "proposals",
                            normalized_result.get(
                                "proposals",
                                [],
                            ),
                        )
                    )
                ),
                "research_available": bool(
                    normalized_session.get(
                        "research"
                    )
                    or normalized_result.get(
                        "research"
                    )
                ),
                "reasoning_available": bool(
                    normalized_session.get(
                        "reasoning"
                    )
                    or normalized_result.get(
                        "reasoning"
                    )
                ),
                "execution_available": bool(
                    execution
                ),
            },
        )

        self._entries.append(
            entry
        )

        self._trim()
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
        status: str | None = None,
        decision: str | None = None,
        execution_status: str | None = None,
        lessons: list[str] | None = None,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        entry = self._find(
            session_id
        )

        if entry is None:
            return None

        if status is not None:
            entry.status = str(
                status
            ).strip().upper()

        if decision is not None:
            entry.decision = str(
                decision
            ).strip().upper()

        if execution_status is not None:
            entry.execution_status = (
                self._optional_string(
                    execution_status
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

        if warnings is not None:
            entry.warnings = self._unique_strings(
                entry.warnings + warnings
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

        entry = self._find(
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
        status: str | None = None,
        decision: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        objective_query: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        normalized_status = (
            str(status).strip().upper()
            if status is not None
            else None
        )

        normalized_decision = (
            str(decision).strip().upper()
            if decision is not None
            else None
        )

        normalized_category = (
            str(category).strip().upper()
            if category is not None
            else None
        )

        normalized_priority = (
            str(priority).strip().upper()
            if priority is not None
            else None
        )

        normalized_query = (
            str(objective_query).strip().lower()
            if objective_query is not None
            else None
        )

        found: list[
            ImprovementMemoryEntry
        ] = []

        for entry in reversed(
            self._entries
        ):
            if (
                normalized_status
                and entry.status
                != normalized_status
            ):
                continue

            if (
                normalized_decision
                and entry.decision
                != normalized_decision
            ):
                continue

            if (
                normalized_category
                and (
                    entry.selected_category
                    or ""
                ).upper()
                != normalized_category
            ):
                continue

            if (
                normalized_priority
                and (
                    entry.selected_priority
                    or ""
                ).upper()
                != normalized_priority
            ):
                continue

            if (
                normalized_query
                and normalized_query
                not in entry.objective.lower()
            ):
                continue

            found.append(
                entry
            )

            if len(found) >= max(
                1,
                int(limit),
            ):
                break

        return [
            entry.to_dict()
            for entry in found
        ]

    def find_similar(
        self,
        objective: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:

        normalized_objective = str(
            objective
        ).strip().lower()

        if not normalized_objective:
            return []

        objective_words = {
            word
            for word in normalized_objective.split()
            if word
        }

        scored: list[
            tuple[
                float,
                ImprovementMemoryEntry,
            ]
        ] = []

        for entry in self._entries:
            entry_words = {
                word
                for word in entry.objective.lower().split()
                if word
            }

            score = float(
                len(
                    objective_words
                    & entry_words
                )
            )

            if entry.status == "COMPLETED":
                score += 1.0

            if entry.status == "FAILED":
                score += 0.25

            if entry.selected_priority == "CRITICAL":
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

    def successful_patterns(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:

        successful = [
            entry
            for entry in reversed(
                self._entries
            )
            if entry.status
            in {
                "COMPLETED",
                "NO_ACTION",
            }
        ]

        return [
            entry.to_dict()
            for entry in successful[
                :max(
                    1,
                    int(limit),
                )
            ]
        ]

    def failure_patterns(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:

        failed = [
            entry
            for entry in reversed(
                self._entries
            )
            if entry.status == "FAILED"
        ]

        return [
            entry.to_dict()
            for entry in failed[
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
            if entry.status == "COMPLETED"
        ]

        failed = [
            entry
            for entry in self._entries
            if entry.status == "FAILED"
        ]

        waiting = [
            entry
            for entry in self._entries
            if entry.status
            == "WAITING_FOR_APPROVAL"
        ]

        no_action = [
            entry
            for entry in self._entries
            if entry.status == "NO_ACTION"
        ]

        categories: dict[str, int] = {}
        priorities: dict[str, int] = {}

        for entry in self._entries:
            category = (
                entry.selected_category
                or "UNKNOWN"
            ).upper()

            priority = (
                entry.selected_priority
                or "UNKNOWN"
            ).upper()

            categories[
                category
            ] = categories.get(
                category,
                0,
            ) + 1

            priorities[
                priority
            ] = priorities.get(
                priority,
                0,
            ) + 1

        average_score = 0.0

        if self._entries:
            average_score = sum(
                entry.proposal_score
                for entry in self._entries
            ) / len(self._entries)

        recent_lessons: list[str] = []
        recent_errors: list[str] = []

        for entry in reversed(
            self._entries
        ):
            recent_lessons.extend(
                entry.lessons
            )

            recent_errors.extend(
                entry.errors
            )

            if (
                len(recent_lessons) >= 10
                and len(recent_errors) >= 10
            ):
                break

        summary = ImprovementMemorySummary(
            entries_count=len(
                self._entries
            ),
            completed_sessions=len(
                completed
            ),
            failed_sessions=len(
                failed
            ),
            waiting_sessions=len(
                waiting
            ),
            no_action_sessions=len(
                no_action
            ),
            average_score=round(
                average_score,
                2,
            ),
            categories=categories,
            priorities=priorities,
            recent_lessons=self._unique_strings(
                recent_lessons
            )[:10],
            recent_errors=self._unique_strings(
                recent_errors
            )[:10],
            metadata={
                "memory_version": "1.0.0",
                "storage_path": str(
                    self.storage_path
                ),
                "max_entries": self.max_entries,
            },
        )

        return summary.to_dict()

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
                ImprovementMemoryEntry
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
            self._trim()

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
    ) -> ImprovementMemoryEntry:

        return ImprovementMemoryEntry(
            memory_id=str(
                data.get(
                    "memory_id",
                    f"improvement_memory_{uuid4().hex}",
                )
            ),
            session_id=str(
                data.get(
                    "session_id",
                    "",
                )
            ),
            objective=str(
                data.get(
                    "objective",
                    "",
                )
            ),
            status=str(
                data.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper(),
            decision=str(
                data.get(
                    "decision",
                    "NO_ACTION",
                )
            ).upper(),
            selected_proposal_id=(
                self._optional_string(
                    data.get(
                        "selected_proposal_id"
                    )
                )
            ),
            selected_proposal_title=(
                self._optional_string(
                    data.get(
                        "selected_proposal_title"
                    )
                )
            ),
            selected_category=(
                self._optional_string(
                    data.get(
                        "selected_category"
                    )
                )
            ),
            selected_priority=(
                self._optional_string(
                    data.get(
                        "selected_priority"
                    )
                )
            ),
            proposal_score=max(
                0.0,
                min(
                    100.0,
                    self._safe_float(
                        data.get(
                            "proposal_score",
                            0.0,
                        ),
                        0.0,
                    ),
                ),
            ),
            execution_status=(
                self._optional_string(
                    data.get(
                        "execution_status"
                    )
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
            warnings=self._unique_strings(
                self._safe_list(
                    data.get(
                        "warnings",
                        [],
                    )
                )
            ),
            created_at=str(
                data.get(
                    "created_at",
                    self._utc_now(),
                )
            ),
            metadata=self._safe_dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )

    def _resolve_status(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> str:

        for value in (
            result.get("status"),
            session.get("status"),
        ):
            if value is None:
                continue

            normalized = str(
                value
            ).strip().upper()

            if normalized:
                return normalized

        return "UNKNOWN"

    def _resolve_decision(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> str:

        for value in (
            result.get("decision"),
            session.get("decision"),
        ):
            if value is None:
                continue

            normalized = str(
                value
            ).strip().upper()

            if normalized:
                return normalized

        return "NO_ACTION"

    def _collect_lessons(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                session.get(
                    "lessons",
                    [],
                )
            )
        )

        values.extend(
            self._safe_list(
                result.get(
                    "lessons",
                    [],
                )
            )
        )

        execution = result.get(
            "execution"
        )

        if isinstance(
            execution,
            dict,
        ):
            values.extend(
                self._safe_list(
                    execution.get(
                        "lessons",
                        [],
                    )
                )
            )

        return self._unique_strings(
            values
        )

    def _collect_errors(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                session.get(
                    "errors",
                    [],
                )
            )
        )

        values.extend(
            self._safe_list(
                result.get(
                    "errors",
                    [],
                )
            )
        )

        for source in (
            session,
            result,
        ):
            error = source.get(
                "error"
            )

            if error:
                values.append(
                    error
                )

        return self._unique_strings(
            values
        )

    def _collect_warnings(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                session.get(
                    "warnings",
                    [],
                )
            )
        )

        values.extend(
            self._safe_list(
                result.get(
                    "warnings",
                    [],
                )
            )
        )

        return self._unique_strings(
            values
        )

    def _find(
        self,
        session_id: str,
    ) -> ImprovementMemoryEntry | None:

        normalized = str(
            session_id
        ).strip()

        for entry in reversed(
            self._entries
        ):
            if entry.session_id == normalized:
                return entry

        return None

    def _trim(
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
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(
            value,
            list,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            tuple,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            set,
        ):
            return list(
                value
            )

        if value is None:
            return []

        return [
            value
        ]

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(
                value
            )

        return {}

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

            seen.add(
                key
            )
            result.append(
                text
            )

        return result

    def _utc_now(
        self,
    ) -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()
