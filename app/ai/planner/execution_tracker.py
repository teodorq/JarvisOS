from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionEventType(str, Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    BLOCKED = "BLOCKED"
    UNBLOCKED = "UNBLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NOTE = "NOTE"


@dataclass
class ExecutionEvent:
    event_id: str
    event_type: str
    timestamp: str
    message: str
    progress: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionRecord:
    execution_id: str
    goal_id: str
    title: str
    status: str
    progress: float
    started_at: str | None
    updated_at: str
    completed_at: str | None
    estimated_effort: float
    actual_effort: float
    current_step: str | None
    blockers: list[str]
    errors: list[str]
    events: list[dict[str, Any]]
    result: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionTracker:

    def __init__(
        self,
        storage_path: str | Path = (
            "data/planning/executions.json"
        ),
        auto_save: bool = True,
    ) -> None:

        self.storage_path = Path(storage_path)
        self.auto_save = bool(auto_save)
        self._records: dict[str, ExecutionRecord] = {}

        self._ensure_storage()
        self.load()

    def create(
        self,
        goal_id: str,
        title: str,
        estimated_effort: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_goal_id = str(goal_id).strip()
        normalized_title = str(title).strip()

        if not normalized_goal_id:
            raise ValueError(
                "ExecutionTracker wymaga goal_id."
            )

        if not normalized_title:
            raise ValueError(
                "ExecutionTracker wymaga tytułu."
            )

        execution_id = f"execution_{uuid4().hex}"
        now = self._utc_now()

        record = ExecutionRecord(
            execution_id=execution_id,
            goal_id=normalized_goal_id,
            title=normalized_title,
            status=ExecutionStatus.PENDING.value,
            progress=0.0,
            started_at=None,
            updated_at=now,
            completed_at=None,
            estimated_effort=max(
                0.0,
                self._safe_float(
                    estimated_effort,
                    0.0,
                ),
            ),
            actual_effort=0.0,
            current_step=None,
            blockers=[],
            errors=[],
            events=[],
            result={},
            metadata={
                "tracker_version": "1.0.0",
                **(metadata or {}),
            },
        )

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.CREATED,
                message="Utworzono śledzenie wykonania.",
                progress=0.0,
            ).to_dict()
        )

        self._records[execution_id] = record
        self._save_if_enabled()

        return record.to_dict()

    def start(
        self,
        execution_id: str,
        current_step: str | None = None,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        now = self._utc_now()

        record.status = ExecutionStatus.RUNNING.value
        record.started_at = record.started_at or now
        record.updated_at = now

        if current_step is not None:
            record.current_step = str(
                current_step
            ).strip() or None

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.STARTED,
                message="Rozpoczęto wykonanie celu.",
                progress=record.progress,
                metadata={
                    "current_step": record.current_step,
                },
            ).to_dict()
        )

        self._save_if_enabled()
        return record.to_dict()

    def update_progress(
        self,
        execution_id: str,
        progress: float,
        current_step: str | None = None,
        actual_effort_delta: float = 0.0,
        message: str | None = None,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        normalized_progress = max(
            0.0,
            min(
                1.0,
                float(progress),
            ),
        )

        record.progress = round(
            normalized_progress,
            4,
        )

        if current_step is not None:
            record.current_step = str(
                current_step
            ).strip() or None

        record.actual_effort = round(
            max(
                0.0,
                record.actual_effort
                + float(actual_effort_delta),
            ),
            2,
        )

        if record.status == ExecutionStatus.PENDING.value:
            record.status = ExecutionStatus.RUNNING.value
            record.started_at = (
                record.started_at
                or self._utc_now()
            )

        record.updated_at = self._utc_now()

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.PROGRESS,
                message=(
                    str(message).strip()
                    if message
                    else (
                        "Zaktualizowano postęp wykonania."
                    )
                ),
                progress=record.progress,
                metadata={
                    "current_step": record.current_step,
                    "actual_effort": (
                        record.actual_effort
                    ),
                },
            ).to_dict()
        )

        if record.progress >= 1.0:
            return self.complete(
                execution_id=execution_id,
                result=record.result,
            )

        self._save_if_enabled()
        return record.to_dict()

    def pause(
        self,
        execution_id: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        record.status = ExecutionStatus.PAUSED.value
        record.updated_at = self._utc_now()

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.PAUSED,
                message=(
                    f"Wstrzymano wykonanie: {reason}"
                    if reason
                    else "Wstrzymano wykonanie."
                ),
                progress=record.progress,
            ).to_dict()
        )

        self._save_if_enabled()
        return record.to_dict()

    def resume(
        self,
        execution_id: str,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        record.status = ExecutionStatus.RUNNING.value
        record.started_at = (
            record.started_at
            or self._utc_now()
        )
        record.updated_at = self._utc_now()

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.RESUMED,
                message="Wznowiono wykonanie.",
                progress=record.progress,
            ).to_dict()
        )

        self._save_if_enabled()
        return record.to_dict()

    def block(
        self,
        execution_id: str,
        blocker: str,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        normalized_blocker = str(
            blocker
        ).strip()

        if normalized_blocker:
            record.blockers = self._unique_strings(
                record.blockers
                + [normalized_blocker]
            )

        record.status = ExecutionStatus.BLOCKED.value
        record.updated_at = self._utc_now()

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.BLOCKED,
                message=(
                    f"Zablokowano wykonanie: "
                    f"{normalized_blocker}"
                ),
                progress=record.progress,
            ).to_dict()
        )

        self._save_if_enabled()
        return record.to_dict()

    def unblock(
        self,
        execution_id: str,
        blocker: str | None = None,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        if blocker is None:
            record.blockers = []

        else:
            normalized = str(
                blocker
            ).strip().lower()

            record.blockers = [
                item
                for item in record.blockers
                if item.lower() != normalized
            ]

        if not record.blockers:
            record.status = (
                ExecutionStatus.RUNNING.value
                if record.started_at
                else ExecutionStatus.PENDING.value
            )

        record.updated_at = self._utc_now()

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.UNBLOCKED,
                message="Usunięto blokadę wykonania.",
                progress=record.progress,
            ).to_dict()
        )

        self._save_if_enabled()
        return record.to_dict()

    def complete(
        self,
        execution_id: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        now = self._utc_now()

        record.status = ExecutionStatus.COMPLETED.value
        record.progress = 1.0
        record.completed_at = now
        record.updated_at = now
        record.result = (
            dict(result)
            if isinstance(result, dict)
            else {}
        )

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.COMPLETED,
                message="Wykonanie zakończone sukcesem.",
                progress=1.0,
            ).to_dict()
        )

        self._save_if_enabled()
        return record.to_dict()

    def fail(
        self,
        execution_id: str,
        error: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        normalized_error = str(
            error
        ).strip()

        if normalized_error:
            record.errors = self._unique_strings(
                record.errors
                + [normalized_error]
            )

        now = self._utc_now()

        record.status = ExecutionStatus.FAILED.value
        record.completed_at = now
        record.updated_at = now
        record.result = (
            dict(result)
            if isinstance(result, dict)
            else {}
        )

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.FAILED,
                message=(
                    f"Wykonanie zakończone błędem: "
                    f"{normalized_error}"
                ),
                progress=record.progress,
            ).to_dict()
        )

        self._save_if_enabled()
        return record.to_dict()

    def cancel(
        self,
        execution_id: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        now = self._utc_now()

        record.status = ExecutionStatus.CANCELLED.value
        record.completed_at = now
        record.updated_at = now

        record.events.append(
            self._make_event(
                event_type=ExecutionEventType.CANCELLED,
                message=(
                    f"Anulowano wykonanie: {reason}"
                    if reason
                    else "Anulowano wykonanie."
                ),
                progress=record.progress,
            ).to_dict()
        )

        self._save_if_enabled()
        return record.to_dict()

    def add_note(
        self,
        execution_id: str,
        note: str,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        normalized_note = str(
            note
        ).strip()

        if normalized_note:
            record.events.append(
                self._make_event(
                    event_type=ExecutionEventType.NOTE,
                    message=normalized_note,
                    progress=record.progress,
                ).to_dict()
            )

            record.updated_at = self._utc_now()

        self._save_if_enabled()
        return record.to_dict()

    def get(
        self,
        execution_id: str,
    ) -> dict[str, Any] | None:

        record = self._get_record(
            execution_id
        )

        if record is None:
            return None

        return record.to_dict()

    def get_by_goal(
        self,
        goal_id: str,
    ) -> list[dict[str, Any]]:

        normalized_goal_id = str(
            goal_id
        ).strip()

        records = [
            record
            for record in self._records.values()
            if record.goal_id == normalized_goal_id
        ]

        records.sort(
            key=lambda item: item.updated_at,
            reverse=True,
        )

        return [
            record.to_dict()
            for record in records
        ]

    def list(
        self,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:

        normalized_status = (
            str(status).strip().upper()
            if status is not None
            else None
        )

        records = list(
            self._records.values()
        )

        records.sort(
            key=lambda item: item.updated_at,
            reverse=True,
        )

        result: list[dict[str, Any]] = []

        for record in records:
            if (
                normalized_status
                and record.status
                != normalized_status
            ):
                continue

            result.append(
                record.to_dict()
            )

            if len(result) >= max(
                1,
                int(limit),
            ):
                break

        return result

    def active(
        self,
    ) -> list[dict[str, Any]]:

        return [
            record.to_dict()
            for record in self._records.values()
            if record.status
            in {
                ExecutionStatus.RUNNING.value,
                ExecutionStatus.PAUSED.value,
                ExecutionStatus.BLOCKED.value,
            }
        ]

    def summary(
        self,
    ) -> dict[str, Any]:

        status_counts = {
            status.value: 0
            for status in ExecutionStatus
        }

        for record in self._records.values():
            status_counts[record.status] = (
                status_counts.get(
                    record.status,
                    0,
                )
                + 1
            )

        records = list(
            self._records.values()
        )

        average_progress = 0.0

        if records:
            average_progress = (
                sum(
                    record.progress
                    for record in records
                )
                / len(records)
            )

        total_estimated_effort = sum(
            record.estimated_effort
            for record in records
        )

        total_actual_effort = sum(
            record.actual_effort
            for record in records
        )

        return {
            "records_count": len(records),
            "active_count": sum(
                1
                for record in records
                if record.status
                in {
                    ExecutionStatus.RUNNING.value,
                    ExecutionStatus.PAUSED.value,
                    ExecutionStatus.BLOCKED.value,
                }
            ),
            "completed_count": (
                status_counts.get(
                    ExecutionStatus.COMPLETED.value,
                    0,
                )
            ),
            "failed_count": (
                status_counts.get(
                    ExecutionStatus.FAILED.value,
                    0,
                )
            ),
            "average_progress": round(
                average_progress,
                4,
            ),
            "total_estimated_effort": round(
                total_estimated_effort,
                2,
            ),
            "total_actual_effort": round(
                total_actual_effort,
                2,
            ),
            "status_counts": status_counts,
            "storage_path": str(
                self.storage_path
            ),
            "tracker_version": "1.0.0",
        }

    def save(
        self,
    ) -> None:

        self._ensure_storage()

        payload = {
            "version": "1.0.0",
            "saved_at": self._utc_now(),
            "records": [
                record.to_dict()
                for record in self._records.values()
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
            self._records = {}
            return

        try:
            raw_text = self.storage_path.read_text(
                encoding="utf-8"
            )

            if not raw_text.strip():
                self._records = {}
                return

            payload = json.loads(
                raw_text
            )

            raw_records = payload.get(
                "records",
                [],
            )

            loaded: dict[
                str,
                ExecutionRecord,
            ] = {}

            if isinstance(
                raw_records,
                list,
            ):
                for raw_record in raw_records:
                    if not isinstance(
                        raw_record,
                        dict,
                    ):
                        continue

                    try:
                        record = self._record_from_dict(
                            raw_record
                        )

                        loaded[
                            record.execution_id
                        ] = record

                    except (
                        TypeError,
                        ValueError,
                    ):
                        continue

            self._records = loaded

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self._records = {}

    def clear(
        self,
    ) -> None:

        self._records = {}
        self._save_if_enabled()

    def _record_from_dict(
        self,
        data: dict[str, Any],
    ) -> ExecutionRecord:

        return ExecutionRecord(
            execution_id=str(
                data.get(
                    "execution_id",
                    f"execution_{uuid4().hex}",
                )
            ),
            goal_id=str(
                data.get(
                    "goal_id",
                    "",
                )
            ),
            title=str(
                data.get(
                    "title",
                    "Nieznane wykonanie",
                )
            ),
            status=str(
                data.get(
                    "status",
                    ExecutionStatus.PENDING.value,
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
            started_at=self._optional_string(
                data.get(
                    "started_at"
                )
            ),
            updated_at=str(
                data.get(
                    "updated_at",
                    self._utc_now(),
                )
            ),
            completed_at=self._optional_string(
                data.get(
                    "completed_at"
                )
            ),
            estimated_effort=max(
                0.0,
                self._safe_float(
                    data.get(
                        "estimated_effort",
                        0.0,
                    ),
                    0.0,
                ),
            ),
            actual_effort=max(
                0.0,
                self._safe_float(
                    data.get(
                        "actual_effort",
                        0.0,
                    ),
                    0.0,
                ),
            ),
            current_step=self._optional_string(
                data.get(
                    "current_step"
                )
            ),
            blockers=self._unique_strings(
                self._safe_list(
                    data.get(
                        "blockers",
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
            events=[
                dict(event)
                for event in self._safe_list(
                    data.get(
                        "events",
                        [],
                    )
                )
                if isinstance(event, dict)
            ],
            result=self._safe_dict(
                data.get(
                    "result",
                    {},
                )
            ),
            metadata=self._safe_dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )

    def _make_event(
        self,
        event_type: ExecutionEventType,
        message: str,
        progress: float | None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionEvent:

        return ExecutionEvent(
            event_id=f"execution_event_{uuid4().hex}",
            event_type=event_type.value,
            timestamp=self._utc_now(),
            message=str(message),
            progress=progress,
            metadata=(
                dict(metadata)
                if isinstance(metadata, dict)
                else {}
            ),
        )

    def _get_record(
        self,
        execution_id: str,
    ) -> ExecutionRecord | None:

        return self._records.get(
            str(execution_id).strip()
        )

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
                        "records": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def _save_if_enabled(
        self,
    ) -> None:

        if self.auto_save:
            self.save()

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
            text = str(value).strip()

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
