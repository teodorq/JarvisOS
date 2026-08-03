"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class EvolutionMemoryEntry:
    memory_id: str
    evolution_id: str
    objective: str
    mode: str
    status: str
    decision: str
    iteration: int
    max_iterations: int
    continuous_cycle_id: str | None
    result: dict[str, Any]
    lessons: list[str]
    errors: list[str]
    warnings: list[str]
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionMemorySummary:
    entries_count: int
    completed_runs: int
    failed_runs: int
    cancelled_runs: int
    no_change_runs: int
    average_iterations: float
    recent_lessons: list[str]
    recent_errors: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvolutionMemory:

    def __init__(
        self,
        storage_path: str | Path = (
            "data/evolution/evolution_memory.json"
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
            EvolutionMemoryEntry
        ] = []

        self._ensure_storage()
        self.load()

    def remember(
        self,
        evolution_run: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_run = self._safe_dict(
            evolution_run
        )

        normalized_result = self._safe_dict(
            result
        )

        entry = EvolutionMemoryEntry(
            memory_id=f"evolution_memory_{uuid4().hex}",
            evolution_id=str(
                normalized_run.get(
                    "evolution_id",
                    "",
                )
            ),
            objective=str(
                normalized_run.get(
                    "objective",
                    "",
                )
            ),
            mode=str(
                normalized_run.get(
                    "mode",
                    "UNKNOWN",
                )
            ).upper(),
            status=self._resolve_status(
                normalized_run,
                normalized_result,
            ),
            decision=self._resolve_decision(
                normalized_run,
                normalized_result,
            ),
            iteration=max(
                0,
                self._safe_int(
                    normalized_run.get(
                        "iteration",
                        0,
                    ),
                    0,
                ),
            ),
            max_iterations=max(
                1,
                self._safe_int(
                    normalized_run.get(
                        "max_iterations",
                        1,
                    ),
                    1,
                ),
            ),
            continuous_cycle_id=(
                self._optional_string(
                    normalized_run.get(
                        "continuous_cycle_id"
                    )
                )
            ),
            result=normalized_result,
            lessons=self._collect_lessons(
                normalized_run,
                normalized_result,
            ),
            errors=self._collect_errors(
                normalized_run,
                normalized_result,
            ),
            warnings=self._collect_warnings(
                normalized_run,
                normalized_result,
            ),
            created_at=self._utc_now(),
            metadata={
                "memory_version": "1.0.0",
                "project_root": normalized_run.get(
                    "project_root"
                ),
                "history_count": len(
                    self._safe_list(
                        normalized_run.get(
                            "history",
                            [],
                        )
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
        evolution_run: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.remember(
            evolution_run=evolution_run,
            result=result,
        )

    def record(
        self,
        evolution_run: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.remember(
            evolution_run=evolution_run,
            result=result,
        )

    def update(
        self,
        evolution_id: str,
        status: str | None = None,
        decision: str | None = None,
        iteration: int | None = None,
        result: dict[str, Any] | None = None,
        lessons: list[str] | None = None,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        entry = self._find(
            evolution_id
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

        if iteration is not None:
            entry.iteration = max(
                0,
                int(iteration),
            )

        if result is not None:
            entry.result = self._safe_dict(
                result
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
        evolution_id: str,
    ) -> dict[str, Any] | None:

        entry = self._find(
            evolution_id
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
        mode: str | None = None,
        objective_query: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        normalized_status = (
            str(status).strip().upper()
            if status is not None
            else None
        )

        normalized_mode = (
            str(mode).strip().upper()
            if mode is not None
            else None
        )

        normalized_query = (
            str(objective_query).strip().lower()
            if objective_query is not None
            else None
        )

        found: list[
            EvolutionMemoryEntry
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
                normalized_mode
                and entry.mode
                != normalized_mode
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
                EvolutionMemoryEntry,
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
                    objective_words & entry_words
                )
            )

            if entry.status == "COMPLETED":
                score += 1.0

            if entry.status == "NO_CHANGES":
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
            if entry.status
            in {
                "COMPLETED",
                "NO_CHANGES",
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

        cancelled = [
            entry
            for entry in self._entries
            if entry.status == "CANCELLED"
        ]

        no_changes = [
            entry
            for entry in self._entries
            if entry.status == "NO_CHANGES"
        ]

        average_iterations = 0.0

        if self._entries:
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

        result = EvolutionMemorySummary(
            entries_count=len(
                self._entries
            ),
            completed_runs=len(
                completed
            ),
            failed_runs=len(
                failed
            ),
            cancelled_runs=len(
                cancelled
            ),
            no_change_runs=len(
                no_changes
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
                EvolutionMemoryEntry
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
    ) -> EvolutionMemoryEntry:

        return EvolutionMemoryEntry(
            memory_id=str(
                data.get(
                    "memory_id",
                    f"evolution_memory_{uuid4().hex}",
                )
            ),
            evolution_id=str(
                data.get(
                    "evolution_id",
                    "",
                )
            ),
            objective=str(
                data.get(
                    "objective",
                    "",
                )
            ),
            mode=str(
                data.get(
                    "mode",
                    "UNKNOWN",
                )
            ).upper(),
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
            max_iterations=max(
                1,
                self._safe_int(
                    data.get(
                        "max_iterations",
                        1,
                    ),
                    1,
                ),
            ),
            continuous_cycle_id=(
                self._optional_string(
                    data.get(
                        "continuous_cycle_id"
                    )
                )
            ),
            result=self._safe_dict(
                data.get(
                    "result",
                    {},
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
        evolution_run: dict[str, Any],
        result: dict[str, Any],
    ) -> str:

        for value in (
            result.get("status"),
            evolution_run.get("status"),
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
        evolution_run: dict[str, Any],
        result: dict[str, Any],
    ) -> str:

        for value in (
            result.get("decision"),
            evolution_run.get("decision"),
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
        evolution_run: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                evolution_run.get(
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

        nested_result = result.get(
            "result"
        )

        if isinstance(
            nested_result,
            dict,
        ):
            values.extend(
                self._safe_list(
                    nested_result.get(
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
        evolution_run: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                evolution_run.get(
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
            evolution_run,
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
        evolution_run: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                evolution_run.get(
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
        evolution_id: str,
    ) -> EvolutionMemoryEntry | None:

        normalized = str(
            evolution_id
        ).strip()

        for entry in reversed(
            self._entries
        ):
            if entry.evolution_id == normalized:
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
