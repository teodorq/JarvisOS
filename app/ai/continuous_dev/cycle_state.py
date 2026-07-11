from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class CycleStateStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class CycleStateSnapshot:
    snapshot_id: str
    cycle_id: str
    status: str
    stage: str | None
    progress: float
    iteration: int
    timestamp: str
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CycleStateData:
    cycle_id: str
    status: str
    stage: str | None
    progress: float
    iteration: int
    max_iterations: int
    paused: bool
    waiting_for_approval: bool
    blocked: bool
    block_reason: str | None
    current_task_id: str | None
    current_improvement_id: str | None
    current_execution_id: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    snapshots: list[dict[str, Any]]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CycleState:

    def __init__(
        self,
        cycle_id: str,
        max_iterations: int = 10,
        storage_path: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        normalized_cycle_id = str(
            cycle_id
        ).strip()

        if not normalized_cycle_id:
            raise ValueError(
                "CycleState wymaga cycle_id."
            )

        now = self._utc_now()

        self.cycle_id = normalized_cycle_id
        self.status = CycleStateStatus.CREATED.value
        self.stage: str | None = None
        self.progress = 0.0
        self.iteration = 0
        self.max_iterations = max(
            1,
            int(max_iterations),
        )

        self.paused = False
        self.waiting_for_approval = False
        self.blocked = False
        self.block_reason: str | None = None

        self.current_task_id: str | None = None
        self.current_improvement_id: str | None = None
        self.current_execution_id: str | None = None

        self.created_at = now
        self.updated_at = now
        self.completed_at: str | None = None

        self.snapshots: list[
            CycleStateSnapshot
        ] = []

        self.metadata: dict[str, Any] = {
            "state_version": "1.0.0",
            **(metadata or {}),
        }

        self.storage_path = (
            Path(storage_path)
            if storage_path is not None
            else Path(
                "data/continuous_dev/states"
            ) / f"{self.cycle_id}.json"
        )

        self._ensure_storage_directory()
        self.snapshot(
            data={
                "event": "STATE_CREATED",
            }
        )

    def activate(
        self,
        stage: str | None = None,
    ) -> dict[str, Any]:

        self.status = CycleStateStatus.ACTIVE.value
        self.paused = False
        self.blocked = False
        self.block_reason = None

        if stage is not None:
            self.stage = str(
                stage
            ).strip().upper() or None

        self._touch()

        self.snapshot(
            data={
                "event": "STATE_ACTIVATED",
            }
        )

        return self.to_dict()

    def set_stage(
        self,
        stage: str,
        progress: float | None = None,
    ) -> dict[str, Any]:

        normalized_stage = str(
            stage
        ).strip().upper()

        if not normalized_stage:
            raise ValueError(
                "Etap CycleState nie może być pusty."
            )

        self.stage = normalized_stage

        if progress is not None:
            self.progress = round(
                max(
                    0.0,
                    min(
                        1.0,
                        float(progress),
                    ),
                ),
                4,
            )

        if self.status not in {
            CycleStateStatus.COMPLETED.value,
            CycleStateStatus.FAILED.value,
            CycleStateStatus.CANCELLED.value,
        }:
            self.status = CycleStateStatus.ACTIVE.value

        self._touch()

        self.snapshot(
            data={
                "event": "STAGE_CHANGED",
                "stage": self.stage,
            }
        )

        return self.to_dict()

    def next_iteration(
        self,
    ) -> dict[str, Any]:

        if self.iteration >= self.max_iterations:
            raise RuntimeError(
                "Osiągnięto maksymalną liczbę iteracji."
            )

        self.iteration += 1

        self._touch()

        self.snapshot(
            data={
                "event": "ITERATION_CHANGED",
                "iteration": self.iteration,
            }
        )

        return self.to_dict()

    def set_progress(
        self,
        progress: float,
    ) -> dict[str, Any]:

        self.progress = round(
            max(
                0.0,
                min(
                    1.0,
                    float(progress),
                ),
            ),
            4,
        )

        self._touch()

        self.snapshot(
            data={
                "event": "PROGRESS_CHANGED",
                "progress": self.progress,
            }
        )

        return self.to_dict()

    def pause(
        self,
        reason: str | None = None,
    ) -> dict[str, Any]:

        self.status = CycleStateStatus.PAUSED.value
        self.paused = True

        if reason:
            self.metadata["pause_reason"] = str(
                reason
            ).strip()

        self._touch()

        self.snapshot(
            data={
                "event": "STATE_PAUSED",
                "reason": reason,
            }
        )

        return self.to_dict()

    def resume(
        self,
    ) -> dict[str, Any]:

        self.status = CycleStateStatus.ACTIVE.value
        self.paused = False

        self.metadata.pop(
            "pause_reason",
            None,
        )

        self._touch()

        self.snapshot(
            data={
                "event": "STATE_RESUMED",
            }
        )

        return self.to_dict()

    def wait_for_approval(
        self,
        task_id: str | None = None,
    ) -> dict[str, Any]:

        self.status = (
            CycleStateStatus.WAITING_FOR_APPROVAL.value
        )
        self.waiting_for_approval = True

        if task_id is not None:
            self.current_task_id = str(
                task_id
            ).strip() or None

        self._touch()

        self.snapshot(
            data={
                "event": "WAITING_FOR_APPROVAL",
                "task_id": self.current_task_id,
            }
        )

        return self.to_dict()

    def approve(
        self,
        approved: bool,
        note: str | None = None,
    ) -> dict[str, Any]:

        self.waiting_for_approval = False

        self.metadata["approval"] = {
            "approved": bool(approved),
            "note": (
                str(note).strip()
                if note
                else ""
            ),
            "timestamp": self._utc_now(),
        }

        if approved:
            self.status = CycleStateStatus.ACTIVE.value

        else:
            self.status = CycleStateStatus.CANCELLED.value
            self.completed_at = self._utc_now()

        self._touch()

        self.snapshot(
            data={
                "event": "APPROVAL_DECISION",
                "approved": bool(approved),
                "note": note,
            }
        )

        return self.to_dict()

    def block(
        self,
        reason: str,
    ) -> dict[str, Any]:

        normalized_reason = str(
            reason
        ).strip()

        self.status = CycleStateStatus.BLOCKED.value
        self.blocked = True
        self.block_reason = (
            normalized_reason
            or "Nieznana blokada."
        )

        self._touch()

        self.snapshot(
            data={
                "event": "STATE_BLOCKED",
                "reason": self.block_reason,
            }
        )

        return self.to_dict()

    def unblock(
        self,
    ) -> dict[str, Any]:

        self.status = CycleStateStatus.ACTIVE.value
        self.blocked = False
        self.block_reason = None

        self._touch()

        self.snapshot(
            data={
                "event": "STATE_UNBLOCKED",
            }
        )

        return self.to_dict()

    def set_current_task(
        self,
        task_id: str | None,
    ) -> dict[str, Any]:

        self.current_task_id = (
            str(task_id).strip()
            if task_id is not None
            and str(task_id).strip()
            else None
        )

        self._touch()

        return self.to_dict()

    def set_current_improvement(
        self,
        improvement_id: str | None,
    ) -> dict[str, Any]:

        self.current_improvement_id = (
            str(improvement_id).strip()
            if improvement_id is not None
            and str(improvement_id).strip()
            else None
        )

        self._touch()

        return self.to_dict()

    def set_current_execution(
        self,
        execution_id: str | None,
    ) -> dict[str, Any]:

        self.current_execution_id = (
            str(execution_id).strip()
            if execution_id is not None
            and str(execution_id).strip()
            else None
        )

        self._touch()

        return self.to_dict()

    def complete(
        self,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        self.status = CycleStateStatus.COMPLETED.value
        self.progress = 1.0
        self.completed_at = self._utc_now()
        self.paused = False
        self.blocked = False
        self.waiting_for_approval = False

        if metadata is not None:
            self.metadata.update(
                dict(metadata)
            )

        self._touch()

        self.snapshot(
            data={
                "event": "STATE_COMPLETED",
            }
        )

        return self.to_dict()

    def fail(
        self,
        error: str,
    ) -> dict[str, Any]:

        self.status = CycleStateStatus.FAILED.value
        self.completed_at = self._utc_now()
        self.paused = False
        self.blocked = False
        self.waiting_for_approval = False

        self.metadata["error"] = str(
            error
        ).strip()

        self._touch()

        self.snapshot(
            data={
                "event": "STATE_FAILED",
                "error": self.metadata["error"],
            }
        )

        return self.to_dict()

    def cancel(
        self,
        reason: str | None = None,
    ) -> dict[str, Any]:

        self.status = CycleStateStatus.CANCELLED.value
        self.completed_at = self._utc_now()
        self.paused = False
        self.blocked = False
        self.waiting_for_approval = False

        if reason:
            self.metadata["cancel_reason"] = str(
                reason
            ).strip()

        self._touch()

        self.snapshot(
            data={
                "event": "STATE_CANCELLED",
                "reason": reason,
            }
        )

        return self.to_dict()

    def can_continue(
        self,
    ) -> bool:

        return (
            self.status
            not in {
                CycleStateStatus.COMPLETED.value,
                CycleStateStatus.FAILED.value,
                CycleStateStatus.CANCELLED.value,
            }
            and not self.paused
            and not self.blocked
            and not self.waiting_for_approval
            and self.iteration < self.max_iterations
        )

    def snapshot(
        self,
        data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        snapshot = CycleStateSnapshot(
            snapshot_id=f"cycle_snapshot_{uuid4().hex}",
            cycle_id=self.cycle_id,
            status=self.status,
            stage=self.stage,
            progress=self.progress,
            iteration=self.iteration,
            timestamp=self._utc_now(),
            data=self._safe_dict(
                data
            ),
            metadata=self._safe_dict(
                metadata
            ),
        )

        self.snapshots.append(
            snapshot
        )

        return snapshot.to_dict()

    def latest_snapshot(
        self,
    ) -> dict[str, Any] | None:

        if not self.snapshots:
            return None

        return self.snapshots[-1].to_dict()

    def save(
        self,
    ) -> None:

        self._ensure_storage_directory()

        temporary_path = (
            self.storage_path.with_suffix(
                self.storage_path.suffix
                + ".tmp"
            )
        )

        temporary_path.write_text(
            json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(
            self.storage_path
        )

    @classmethod
    def load(
        cls,
        storage_path: str | Path,
    ) -> CycleState:

        path = Path(
            storage_path
        )

        raw_text = path.read_text(
            encoding="utf-8"
        )

        data = json.loads(
            raw_text
        )

        state = cls.from_dict(
            data
        )

        state.storage_path = path
        return state

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return CycleStateData(
            cycle_id=self.cycle_id,
            status=self.status,
            stage=self.stage,
            progress=self.progress,
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            paused=self.paused,
            waiting_for_approval=self.waiting_for_approval,
            blocked=self.blocked,
            block_reason=self.block_reason,
            current_task_id=self.current_task_id,
            current_improvement_id=(
                self.current_improvement_id
            ),
            current_execution_id=(
                self.current_execution_id
            ),
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
            snapshots=[
                snapshot.to_dict()
                for snapshot in self.snapshots
            ],
            metadata=dict(
                self.metadata
            ),
        ).to_dict()

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> CycleState:

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "CycleState.from_dict wymaga dict."
            )

        state = cls(
            cycle_id=str(
                data.get(
                    "cycle_id",
                    "",
                )
            ),
            max_iterations=int(
                data.get(
                    "max_iterations",
                    10,
                )
            ),
            metadata=(
                data.get("metadata")
                if isinstance(
                    data.get("metadata"),
                    dict,
                )
                else {}
            ),
        )

        state.status = str(
            data.get(
                "status",
                CycleStateStatus.CREATED.value,
            )
        ).upper()

        state.stage = state._optional_string(
            data.get(
                "stage"
            )
        )

        state.progress = max(
            0.0,
            min(
                1.0,
                state._safe_float(
                    data.get(
                        "progress",
                        0.0,
                    ),
                    0.0,
                ),
            ),
        )

        state.iteration = max(
            0,
            int(
                data.get(
                    "iteration",
                    0,
                )
            ),
        )

        state.paused = bool(
            data.get(
                "paused",
                False,
            )
        )

        state.waiting_for_approval = bool(
            data.get(
                "waiting_for_approval",
                False,
            )
        )

        state.blocked = bool(
            data.get(
                "blocked",
                False,
            )
        )

        state.block_reason = (
            state._optional_string(
                data.get(
                    "block_reason"
                )
            )
        )

        state.current_task_id = (
            state._optional_string(
                data.get(
                    "current_task_id"
                )
            )
        )

        state.current_improvement_id = (
            state._optional_string(
                data.get(
                    "current_improvement_id"
                )
            )
        )

        state.current_execution_id = (
            state._optional_string(
                data.get(
                    "current_execution_id"
                )
            )
        )

        state.created_at = str(
            data.get(
                "created_at",
                state.created_at,
            )
        )

        state.updated_at = str(
            data.get(
                "updated_at",
                state.updated_at,
            )
        )

        state.completed_at = (
            state._optional_string(
                data.get(
                    "completed_at"
                )
            )
        )

        state.snapshots = []

        raw_snapshots = data.get(
            "snapshots",
            [],
        )

        if isinstance(
            raw_snapshots,
            list,
        ):
            for raw_snapshot in raw_snapshots:
                if not isinstance(
                    raw_snapshot,
                    dict,
                ):
                    continue

                state.snapshots.append(
                    CycleStateSnapshot(
                        snapshot_id=str(
                            raw_snapshot.get(
                                "snapshot_id",
                                f"cycle_snapshot_{uuid4().hex}",
                            )
                        ),
                        cycle_id=str(
                            raw_snapshot.get(
                                "cycle_id",
                                state.cycle_id,
                            )
                        ),
                        status=str(
                            raw_snapshot.get(
                                "status",
                                state.status,
                            )
                        ),
                        stage=state._optional_string(
                            raw_snapshot.get(
                                "stage"
                            )
                        ),
                        progress=max(
                            0.0,
                            min(
                                1.0,
                                state._safe_float(
                                    raw_snapshot.get(
                                        "progress",
                                        0.0,
                                    ),
                                    0.0,
                                ),
                            ),
                        ),
                        iteration=max(
                            0,
                            int(
                                raw_snapshot.get(
                                    "iteration",
                                    0,
                                )
                            ),
                        ),
                        timestamp=str(
                            raw_snapshot.get(
                                "timestamp",
                                state._utc_now(),
                            )
                        ),
                        data=state._safe_dict(
                            raw_snapshot.get(
                                "data"
                            )
                        ),
                        metadata=state._safe_dict(
                            raw_snapshot.get(
                                "metadata"
                            )
                        ),
                    )
                )

        return state

    def _ensure_storage_directory(
        self,
    ) -> None:

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _touch(
        self,
    ) -> None:

        self.updated_at = self._utc_now()

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

    def _utc_now(
        self,
    ) -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()
