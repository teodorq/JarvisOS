"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class CycleMemoryEntry:
    memory_id: str
    cycle_id: str
    objective: str
    project_root: str
    status: str
    result: str
    progress: float
    iteration: int
    selected_improvement_id: str | None
    selected_improvement_title: str | None
    errors: list[str]
    warnings: list[str]
    lessons: list[str]
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CycleMemorySummary:
    entries_count: int
    successful_cycles: int
    failed_cycles: int
    rolled_back_cycles: int
    cancelled_cycles: int
    average_progress: float
    average_iterations: float
    recent_lessons: list[str]
    recent_errors: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CycleMemory:

    def __init__(
        self,
        storage_path: str | Path = (
            "data/continuous_dev/cycle_memory.json"
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
            CycleMemoryEntry
        ] = []

        self._ensure_storage()
        self.load()

    def remember(
        self,
        cycle: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_cycle = self._safe_dict(
            cycle
        )

        normalized_result = self._safe_dict(
            result
        )

        selected_improvement = self._safe_dict(
            normalized_cycle.get(
                "selected_improvement",
                {},
            )
        )

        entry = CycleMemoryEntry(
            memory_id=f"cycle_memory_{uuid4().hex}",
            cycle_id=str(
                normalized_cycle.get(
                    "cycle_id",
                    "",
                )
            ),
            objective=str(
                normalized_cycle.get(
                    "objective",
                    "",
                )
            ),
            project_root=str(
                normalized_cycle.get(
                    "project_root",
                    "",
                )
            ),
            status=self._resolve_status(
                normalized_cycle,
                normalized_result,
            ),
            result=self._resolve_result(
                normalized_cycle,
                normalized_result,
            ),
            progress=self._resolve_progress(
                normalized_cycle,
                normalized_result,
            ),
            iteration=max(
                0,
                self._safe_int(
                    normalized_cycle.get(
                        "iteration",
                        0,
                    ),
                    0,
                ),
            ),
            selected_improvement_id=(
                self._optional_string(
                    selected_improvement.get(
                        "improvement_id",
                        selected_improvement.get(
                            "id"
                        ),
                    )
                )
            ),
            selected_improvement_title=(
                self._optional_string(
                    selected_improvement.get(
                        "title",
                        selected_improvement.get(
                            "name"
                        ),
                    )
                )
            ),
            errors=self._collect_errors(
                normalized_cycle,
                normalized_result,
            ),
            warnings=self._collect_warnings(
                normalized_cycle,
                normalized_result,
            ),
            lessons=self._collect_lessons(
                normalized_cycle,
                normalized_result,
            ),
            created_at=self._utc_now(),
            metadata={
                "memory_version": "1.0.0",
                "stage": normalized_cycle.get(
                    "current_stage"
                ),
                "report_available": bool(
                    normalized_cycle.get(
                        "report"
                    )
                ),
                "validation_available": bool(
                    normalized_cycle.get(
                        "validation"
                    )
                ),
                "rollback_available": bool(
                    normalized_cycle.get(
                        "rollback"
                    )
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
        cycle: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.remember(
            cycle=cycle,
            result=result,
        )

    def record(
        self,
        cycle: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.remember(
            cycle=cycle,
            result=result,
        )

    def update(
        self,
        cycle_id: str,
        status: str | None = None,
        result: str | None = None,
        progress: float | None = None,
        iteration: int | None = None,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        lessons: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        entry = self._find(
            cycle_id
        )

        if entry is None:
            return None

        if status is not None:
            entry.status = str(
                status
            ).strip().upper()

        if result is not None:
            entry.result = str(
                result
            ).strip().upper()

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

        if iteration is not None:
            entry.iteration = max(
                0,
                int(iteration),
            )

        if errors is not None:
            entry.errors = self._unique_strings(
                entry.errors + errors
            )

        if warnings is not None:
            entry.warnings = self._unique_strings(
                entry.warnings + warnings
            )

        if lessons is not None:
            entry.lessons = self._unique_strings(
                entry.lessons + lessons
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
        cycle_id: str,
    ) -> dict[str, Any] | None:

        entry = self._find(
            cycle_id
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
        result: str | None = None,
        objective_query: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        normalized_status = (
            str(status).strip().upper()
            if status is not None
            else None
        )

        normalized_result = (
            str(result).strip().upper()
            if result is not None
            else None
        )

        normalized_query = (
            str(objective_query).strip().lower()
            if objective_query is not None
            else None
        )

        found: list[
            CycleMemoryEntry
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
                normalized_result
                and entry.result
                != normalized_result
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
            tuple[float, CycleMemoryEntry]
        ] = []

        for entry in self._entries:
            entry_words = {
                word
                for word in entry.objective.lower().split()
                if word
            }

            overlap = len(
                objective_words & entry_words
            )

            score = float(
                overlap
            )

            if entry.result == "SUCCESS":
                score += 1.0

            if entry.result == "ROLLED_BACK":
                score += 0.25

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
            if entry.result
            in {
                "SUCCESS",
                "PARTIAL_SUCCESS",
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
            if entry.result
            in {
                "FAILED",
                "ROLLED_BACK",
            }
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

        successful = [
            entry
            for entry in self._entries
            if entry.result
            in {
                "SUCCESS",
                "PARTIAL_SUCCESS",
            }
        ]

        failed = [
            entry
            for entry in self._entries
            if entry.result == "FAILED"
        ]

        rolled_back = [
            entry
            for entry in self._entries
            if entry.result == "ROLLED_BACK"
        ]

        cancelled = [
            entry
            for entry in self._entries
            if entry.result == "CANCELLED"
        ]

        average_progress = 0.0
        average_iterations = 0.0

        if self._entries:
            average_progress = sum(
                entry.progress
                for entry in self._entries
            ) / len(self._entries)

            average_iterations = sum(
                entry.iteration
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

        result = CycleMemorySummary(
            entries_count=len(
                self._entries
            ),
            successful_cycles=len(
                successful
            ),
            failed_cycles=len(
                failed
            ),
            rolled_back_cycles=len(
                rolled_back
            ),
            cancelled_cycles=len(
                cancelled
            ),
            average_progress=round(
                average_progress,
                4,
            ),
            average_iterations=round(
                average_iterations,
                2,
            ),
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
                CycleMemoryEntry
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
    ) -> CycleMemoryEntry:

        return CycleMemoryEntry(
            memory_id=str(
                data.get(
                    "memory_id",
                    f"cycle_memory_{uuid4().hex}",
                )
            ),
            cycle_id=str(
                data.get(
                    "cycle_id",
                    "",
                )
            ),
            objective=str(
                data.get(
                    "objective",
                    "",
                )
            ),
            project_root=str(
                data.get(
                    "project_root",
                    "",
                )
            ),
            status=str(
                data.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper(),
            result=str(
                data.get(
                    "result",
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
            iteration=max(
                0,
                self._safe_int(
                    data.get(
                        "iteration",
                        0,
                    ),
                    0,
                ),
            ),
            selected_improvement_id=(
                self._optional_string(
                    data.get(
                        "selected_improvement_id"
                    )
                )
            ),
            selected_improvement_title=(
                self._optional_string(
                    data.get(
                        "selected_improvement_title"
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
            lessons=self._unique_strings(
                self._safe_list(
                    data.get(
                        "lessons",
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
        cycle: dict[str, Any],
        result: dict[str, Any],
    ) -> str:

        for value in [
            result.get("status"),
            cycle.get("status"),
        ]:
            if value is None:
                continue

            normalized = str(
                value
            ).strip().upper()

            if normalized:
                return normalized

        return "UNKNOWN"

    def _resolve_result(
        self,
        cycle: dict[str, Any],
        result: dict[str, Any],
    ) -> str:

        for value in [
            result.get("result"),
            cycle.get("result"),
        ]:
            if value is None:
                continue

            normalized = str(
                value
            ).strip().upper()

            if normalized:
                return normalized

        success = result.get(
            "success"
        )

        if success is True:
            return "SUCCESS"

        if success is False:
            return "FAILED"

        return "UNKNOWN"

    def _resolve_progress(
        self,
        cycle: dict[str, Any],
        result: dict[str, Any],
    ) -> float:

        for value in [
            result.get("progress"),
            cycle.get("progress"),
        ]:
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

    def _collect_errors(
        self,
        cycle: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                cycle.get(
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

        for source in [
            cycle,
            result,
        ]:
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
        cycle: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                cycle.get(
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

    def _collect_lessons(
        self,
        cycle: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                cycle.get(
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

        return self._unique_strings(
            values
        )

    def _find(
        self,
        cycle_id: str,
    ) -> CycleMemoryEntry | None:

        normalized_cycle_id = str(
            cycle_id
        ).strip()

        for entry in reversed(
            self._entries
        ):
            if entry.cycle_id == normalized_cycle_id:
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

    def _safe_int(
        self,
        value: Any,
        default: int,
    ) -> int:

        try:
            return int(
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
