from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class ReasoningMemoryEntry:
    memory_id: str
    session_id: str
    goal_type: str
    goal_text: str
    selected_option_id: str | None
    selected_strategy_type: str | None
    risk_level: str
    risk_score: float
    decision: str
    success: bool | None
    execution_status: str
    validation_success: bool | None
    rollback_used: bool
    confidence: float
    lessons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReasoningMemorySummary:
    entries_count: int
    successful_count: int
    failed_count: int
    pending_count: int
    rollback_count: int
    average_risk_score: float
    average_confidence: float
    most_successful_strategy: str | None
    most_failed_strategy: str | None
    recent_lessons: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReasoningMemory:

    def __init__(
        self,
        storage_path: str | Path = (
            "data/reasoning/reasoning_memory.json"
        ),
        max_entries: int = 1000,
    ) -> None:

        self.storage_path = Path(storage_path)
        self.max_entries = max(
            1,
            int(max_entries),
        )

        self._entries: list[
            ReasoningMemoryEntry
        ] = []

        self._ensure_storage()
        self.load()

    def remember(
        self,
        session: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_session = self._normalize_session(
            session
        )

        normalized_result = self._normalize_result(
            result
        )

        goal = normalized_session.get(
            "goal",
            {},
        )

        strategy = normalized_session.get(
            "strategy",
            {},
        )

        risk_assessment = strategy.get(
            "risk_assessment",
            {},
        )

        selected_option = strategy.get(
            "selected_option",
            {},
        )

        execution = normalized_session.get(
            "execution",
            {},
        )

        validation = normalized_session.get(
            "validation",
            {},
        )

        rollback = normalized_session.get(
            "rollback",
            {},
        )

        success = self._detect_success(
            normalized_session,
            normalized_result,
        )

        lessons = self._collect_lessons(
            normalized_session,
            normalized_result,
        )

        errors = self._collect_errors(
            normalized_session,
            normalized_result,
        )

        entry = ReasoningMemoryEntry(
            memory_id=f"reasoning_memory_{uuid4().hex}",
            session_id=str(
                normalized_session.get(
                    "session_id",
                    "",
                )
            ),
            goal_type=str(
                goal.get(
                    "goal_type",
                    "UNKNOWN",
                )
            ),
            goal_text=str(
                goal.get(
                    "goal",
                    goal.get(
                        "original_request",
                        "",
                    ),
                )
            ),
            selected_option_id=self._optional_string(
                selected_option.get(
                    "option_id"
                )
            ),
            selected_strategy_type=self._optional_string(
                selected_option.get(
                    "strategy_type"
                )
            ),
            risk_level=str(
                risk_assessment.get(
                    "risk_level",
                    "UNKNOWN",
                )
            ),
            risk_score=self._safe_float(
                risk_assessment.get(
                    "normalized_score",
                    0.0,
                ),
                0.0,
            ),
            decision=str(
                risk_assessment.get(
                    "decision",
                    "UNKNOWN",
                )
            ),
            success=success,
            execution_status=str(
                execution.get(
                    "status",
                    normalized_result.get(
                        "status",
                        "PENDING",
                    ),
                )
            ),
            validation_success=self._detect_validation_success(
                validation,
                normalized_result,
            ),
            rollback_used=self._detect_rollback_used(
                rollback,
                normalized_result,
            ),
            confidence=self._safe_float(
                strategy.get(
                    "confidence",
                    normalized_session.get(
                        "confidence",
                        0.0,
                    ),
                ),
                0.0,
            ),
            lessons=lessons,
            errors=errors,
            metadata={
                "memory_version": "1.0.0",
                "strategy_id": strategy.get(
                    "strategy_id"
                ),
                "reasoning_status": (
                    normalized_session.get(
                        "status"
                    )
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

    def update_result(
        self,
        session_id: str,
        success: bool | None = None,
        execution_status: str | None = None,
        validation_success: bool | None = None,
        rollback_used: bool | None = None,
        lessons: list[str] | None = None,
        errors: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        entry = self._find_entry_object(
            session_id=session_id
        )

        if entry is None:
            return None

        if success is not None:
            entry.success = bool(success)

        if execution_status is not None:
            entry.execution_status = str(
                execution_status
            )

        if validation_success is not None:
            entry.validation_success = bool(
                validation_success
            )

        if rollback_used is not None:
            entry.rollback_used = bool(
                rollback_used
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

        entry.metadata["updated_at"] = self._utc_now()

        self.save()

        return entry.to_dict()

    def get(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        entry = self._find_entry_object(
            session_id=session_id
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
        goal_type: str | None = None,
        strategy_type: str | None = None,
        risk_level: str | None = None,
        success: bool | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        results: list[
            ReasoningMemoryEntry
        ] = []

        normalized_goal_type = self._normalize_filter(
            goal_type
        )

        normalized_strategy_type = self._normalize_filter(
            strategy_type
        )

        normalized_risk_level = self._normalize_filter(
            risk_level
        )

        for entry in reversed(
            self._entries
        ):
            if (
                normalized_goal_type
                and entry.goal_type.upper()
                != normalized_goal_type
            ):
                continue

            if (
                normalized_strategy_type
                and (
                    entry.selected_strategy_type
                    or ""
                ).upper()
                != normalized_strategy_type
            ):
                continue

            if (
                normalized_risk_level
                and entry.risk_level.upper()
                != normalized_risk_level
            ):
                continue

            if (
                success is not None
                and entry.success is not success
            ):
                continue

            results.append(entry)

            if len(results) >= max(
                1,
                int(limit),
            ):
                break

        return [
            entry.to_dict()
            for entry in results
        ]

    def find_similar(
        self,
        goal: dict[str, Any],
        limit: int = 5,
    ) -> list[dict[str, Any]]:

        if not isinstance(goal, dict):
            return []

        goal_type = str(
            goal.get(
                "goal_type",
                "UNKNOWN",
            )
        ).upper()

        detected_modules = {
            str(module).lower()
            for module in goal.get(
                "detected_modules",
                [],
            )
        }

        keywords = {
            str(keyword).lower()
            for keyword in goal.get(
                "keywords",
                [],
            )
        }

        scored_entries: list[
            tuple[float, ReasoningMemoryEntry]
        ] = []

        for entry in self._entries:
            score = 0.0

            if entry.goal_type.upper() == goal_type:
                score += 3.0

            metadata_modules = {
                str(module).lower()
                for module in entry.metadata.get(
                    "detected_modules",
                    [],
                )
            }

            metadata_keywords = {
                str(keyword).lower()
                for keyword in entry.metadata.get(
                    "keywords",
                    [],
                )
            }

            score += len(
                detected_modules
                & metadata_modules
            ) * 1.5

            score += len(
                keywords
                & metadata_keywords
            ) * 0.5

            if (
                entry.success is True
                and score > 0
            ):
                score += 0.5

            if score > 0:
                scored_entries.append(
                    (
                        score,
                        entry,
                    )
                )

        scored_entries.sort(
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
            for score, entry in scored_entries[
                :max(
                    1,
                    int(limit),
                )
            ]
        ]

    def get_strategy_statistics(
        self,
        strategy_type: str,
    ) -> dict[str, Any]:

        normalized_strategy = str(
            strategy_type
        ).upper()

        matching = [
            entry
            for entry in self._entries
            if (
                entry.selected_strategy_type
                or ""
            ).upper()
            == normalized_strategy
        ]

        successes = sum(
            1
            for entry in matching
            if entry.success is True
        )

        failures = sum(
            1
            for entry in matching
            if entry.success is False
        )

        pending = sum(
            1
            for entry in matching
            if entry.success is None
        )

        completed = successes + failures

        success_rate = 0.0

        if completed > 0:
            success_rate = (
                successes / completed
            )

        average_risk = self._average(
            [
                entry.risk_score
                for entry in matching
            ]
        )

        average_confidence = self._average(
            [
                entry.confidence
                for entry in matching
            ]
        )

        return {
            "strategy_type": normalized_strategy,
            "entries_count": len(matching),
            "successful_count": successes,
            "failed_count": failures,
            "pending_count": pending,
            "success_rate": round(
                success_rate,
                3,
            ),
            "average_risk_score": round(
                average_risk,
                2,
            ),
            "average_confidence": round(
                average_confidence,
                2,
            ),
            "rollback_count": sum(
                1
                for entry in matching
                if entry.rollback_used
            ),
        }

    def recommend_strategy(
        self,
        available_strategy_types: list[str],
    ) -> dict[str, Any] | None:

        candidates: list[
            dict[str, Any]
        ] = []

        for strategy_type in available_strategy_types:
            statistics = self.get_strategy_statistics(
                strategy_type
            )

            completed = (
                statistics["successful_count"]
                + statistics["failed_count"]
            )

            if completed == 0:
                continue

            score = (
                statistics["success_rate"] * 60.0
                + statistics["average_confidence"] * 20.0
                - statistics["average_risk_score"] * 0.2
                - statistics["rollback_count"] * 2.0
            )

            candidates.append(
                {
                    "strategy_type": (
                        statistics[
                            "strategy_type"
                        ]
                    ),
                    "historical_score": round(
                        score,
                        2,
                    ),
                    "statistics": statistics,
                }
            )

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda candidate: (
                candidate["historical_score"]
            ),
        )

    def summary(
        self,
    ) -> dict[str, Any]:

        successes = [
            entry
            for entry in self._entries
            if entry.success is True
        ]

        failures = [
            entry
            for entry in self._entries
            if entry.success is False
        ]

        pending = [
            entry
            for entry in self._entries
            if entry.success is None
        ]

        successful_strategy = (
            self._most_common_strategy(
                successes
            )
        )

        failed_strategy = (
            self._most_common_strategy(
                failures
            )
        )

        recent_lessons: list[str] = []

        for entry in reversed(
            self._entries
        ):
            recent_lessons.extend(
                entry.lessons
            )

            if len(recent_lessons) >= 10:
                break

        result = ReasoningMemorySummary(
            entries_count=len(
                self._entries
            ),
            successful_count=len(
                successes
            ),
            failed_count=len(
                failures
            ),
            pending_count=len(
                pending
            ),
            rollback_count=sum(
                1
                for entry in self._entries
                if entry.rollback_used
            ),
            average_risk_score=round(
                self._average(
                    [
                        entry.risk_score
                        for entry in self._entries
                    ]
                ),
                2,
            ),
            average_confidence=round(
                self._average(
                    [
                        entry.confidence
                        for entry in self._entries
                    ]
                ),
                2,
            ),
            most_successful_strategy=(
                successful_strategy
            ),
            most_failed_strategy=(
                failed_strategy
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

    def clear(
        self,
    ) -> None:

        self._entries = []
        self.save()

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

        temporary_path = self.storage_path.with_suffix(
            self.storage_path.suffix
            + ".tmp"
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

            if not isinstance(
                raw_entries,
                list,
            ):
                self._entries = []
                return

            loaded_entries: list[
                ReasoningMemoryEntry
            ] = []

            for raw_entry in raw_entries:
                if not isinstance(
                    raw_entry,
                    dict,
                ):
                    continue

                try:
                    loaded_entries.append(
                        self._entry_from_dict(
                            raw_entry
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

            self._entries = loaded_entries
            self._trim_entries()

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self._entries = []

    def _entry_from_dict(
        self,
        data: dict[str, Any],
    ) -> ReasoningMemoryEntry:

        return ReasoningMemoryEntry(
            memory_id=str(
                data.get(
                    "memory_id",
                    f"reasoning_memory_{uuid4().hex}",
                )
            ),
            session_id=str(
                data.get(
                    "session_id",
                    "",
                )
            ),
            goal_type=str(
                data.get(
                    "goal_type",
                    "UNKNOWN",
                )
            ),
            goal_text=str(
                data.get(
                    "goal_text",
                    "",
                )
            ),
            selected_option_id=self._optional_string(
                data.get(
                    "selected_option_id"
                )
            ),
            selected_strategy_type=self._optional_string(
                data.get(
                    "selected_strategy_type"
                )
            ),
            risk_level=str(
                data.get(
                    "risk_level",
                    "UNKNOWN",
                )
            ),
            risk_score=self._safe_float(
                data.get(
                    "risk_score",
                    0.0,
                ),
                0.0,
            ),
            decision=str(
                data.get(
                    "decision",
                    "UNKNOWN",
                )
            ),
            success=self._optional_bool(
                data.get(
                    "success"
                )
            ),
            execution_status=str(
                data.get(
                    "execution_status",
                    "PENDING",
                )
            ),
            validation_success=self._optional_bool(
                data.get(
                    "validation_success"
                )
            ),
            rollback_used=bool(
                data.get(
                    "rollback_used",
                    False,
                )
            ),
            confidence=self._safe_float(
                data.get(
                    "confidence",
                    0.0,
                ),
                0.0,
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

    def _normalize_session(
        self,
        session: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(
            session,
            dict,
        ):
            raise TypeError(
                "ReasoningMemory wymaga sesji typu dict."
            )

        normalized = dict(session)

        goal = self._safe_dict(
            normalized.get(
                "goal",
                {},
            )
        )

        strategy = self._safe_dict(
            normalized.get(
                "strategy",
                {},
            )
        )

        goal_metadata = self._safe_dict(
            goal.get(
                "metadata",
                {},
            )
        )

        strategy_metadata = self._safe_dict(
            strategy.get(
                "metadata",
                {},
            )
        )

        normalized["goal"] = goal
        normalized["strategy"] = strategy
        normalized["execution"] = self._safe_dict(
            normalized.get(
                "execution",
                {},
            )
        )
        normalized["validation"] = self._safe_dict(
            normalized.get(
                "validation",
                {},
            )
        )
        normalized["rollback"] = self._safe_dict(
            normalized.get(
                "rollback",
                {},
            )
        )

        normalized.setdefault(
            "session_id",
            f"reasoning_session_{uuid4().hex}",
        )

        normalized["strategy"].setdefault(
            "metadata",
            strategy_metadata,
        )

        normalized["goal"].setdefault(
            "metadata",
            goal_metadata,
        )

        return normalized

    def _normalize_result(
        self,
        result: dict[str, Any] | None,
    ) -> dict[str, Any]:

        if not isinstance(
            result,
            dict,
        ):
            return {}

        return dict(result)

    def _detect_success(
        self,
        session: dict[str, Any],
        result: dict[str, Any],
    ) -> bool | None:

        for source in [
            result,
            session.get(
                "execution",
                {},
            ),
            session,
        ]:
            if not isinstance(
                source,
                dict,
            ):
                continue

            value = source.get(
                "success"
            )

            if isinstance(
                value,
                bool,
            ):
                return value

        status_candidates = [
            result.get(
                "status"
            ),
            session.get(
                "status"
            ),
            session.get(
                "execution",
                {},
            ).get(
                "status"
            ),
        ]

        for status in status_candidates:
            if status is None:
                continue

            normalized = str(
                status
            ).upper()

            if normalized in {
                "SUCCESS",
                "COMPLETED",
                "DONE",
                "VALIDATED",
            }:
                return True

            if normalized in {
                "FAILED",
                "ERROR",
                "REJECTED",
                "ROLLED_BACK",
            }:
                return False

        return None

    def _detect_validation_success(
        self,
        validation: dict[str, Any],
        result: dict[str, Any],
    ) -> bool | None:

        for source in [
            validation,
            result.get(
                "validation",
                {},
            ),
        ]:
            if not isinstance(
                source,
                dict,
            ):
                continue

            for key in [
                "success",
                "valid",
                "passed",
            ]:
                value = source.get(key)

                if isinstance(
                    value,
                    bool,
                ):
                    return value

        return None

    def _detect_rollback_used(
        self,
        rollback: dict[str, Any],
        result: dict[str, Any],
    ) -> bool:

        if rollback:
            for key in [
                "used",
                "executed",
                "success",
                "rolled_back",
            ]:
                if rollback.get(key) is True:
                    return True

        result_rollback = result.get(
            "rollback",
            {}
        )

        if isinstance(
            result_rollback,
            dict,
        ):
            return any(
                result_rollback.get(key) is True
                for key in [
                    "used",
                    "executed",
                    "success",
                    "rolled_back",
                ]
            )

        return bool(
            result.get(
                "rollback_used",
                False,
            )
        )

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

        strategy = self._safe_dict(
            session.get(
                "strategy",
                {},
            )
        )

        selected_option = self._safe_dict(
            strategy.get(
                "selected_option",
                {},
            )
        )

        lessons.extend(
            self._safe_list(
                selected_option.get(
                    "expected_benefits",
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
            session.get(
                "execution",
                {},
            ),
            session.get(
                "validation",
                {},
            ),
            session.get(
                "rollback",
                {},
            ),
            result,
        ]:
            if not isinstance(
                source,
                dict,
            ):
                continue

            error = source.get(
                "error"
            )

            if error:
                errors.append(error)

            message = source.get(
                "message"
            )

            status = str(
                source.get(
                    "status",
                    "",
                )
            ).upper()

            if (
                message
                and status in {
                    "FAILED",
                    "ERROR",
                    "REJECTED",
                }
            ):
                errors.append(message)

        return self._unique_strings(
            errors
        )

    def _find_entry_object(
        self,
        session_id: str,
    ) -> ReasoningMemoryEntry | None:

        normalized_session_id = str(
            session_id
        ).strip()

        for entry in reversed(
            self._entries
        ):
            if (
                entry.session_id
                == normalized_session_id
            ):
                return entry

        return None

    def _most_common_strategy(
        self,
        entries: list[ReasoningMemoryEntry],
    ) -> str | None:

        counts: dict[str, int] = {}

        for entry in entries:
            strategy_type = (
                entry.selected_strategy_type
            )

            if not strategy_type:
                continue

            normalized = strategy_type.upper()

            counts[normalized] = (
                counts.get(
                    normalized,
                    0,
                )
                + 1
            )

        if not counts:
            return None

        return max(
            counts,
            key=counts.get,
        )

    def _average(
        self,
        values: list[float],
    ) -> float:

        if not values:
            return 0.0

        return sum(values) / len(values)

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

    def _normalize_filter(
        self,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip().upper()

        if not normalized:
            return None

        return normalized

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        if not normalized:
            return None

        return normalized

    def _optional_bool(
        self,
        value: Any,
    ) -> bool | None:

        if isinstance(
            value,
            bool,
        ):
            return value

        if isinstance(
            value,
            str,
        ):
            normalized = value.strip().lower()

            if normalized in {
                "true",
                "yes",
                "tak",
                "1",
            }:
                return True

            if normalized in {
                "false",
                "no",
                "nie",
                "0",
            }:
                return False

        return None

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

        if isinstance(
            value,
            list,
        ):
            return list(value)

        if isinstance(
            value,
            tuple,
        ):
            return list(value)

        if isinstance(
            value,
            set,
        ):
            return list(value)

        if value is None:
            return []

        return [value]

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(value)

        return {}

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