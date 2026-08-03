"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from .evolution_iteration_service import EvolutionIterationService

from app.core.project_paths import default_project_root

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.ai.continuous_dev.continuous_dev_controller import (
    ContinuousDevController,
)


class EvolutionStatus(str, Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    LEARNING = "LEARNING"
    COMPLETED = "COMPLETED"
    NO_CHANGES = "NO_CHANGES"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class EvolutionMode(str, Enum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    AUTONOMOUS = "AUTONOMOUS"
    SAFE_AUTONOMOUS = "SAFE_AUTONOMOUS"


class EvolutionDecision(str, Enum):
    START_CYCLE = "START_CYCLE"
    WAIT_FOR_APPROVAL = "WAIT_FOR_APPROVAL"
    CONTINUE = "CONTINUE"
    RETRY = "RETRY"
    STOP = "STOP"
    NO_ACTION = "NO_ACTION"
    ROLLBACK = "ROLLBACK"


@dataclass
class EvolutionEvent:
    event_id: str
    event_type: str
    message: str
    timestamp: str
    status: str
    iteration: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionRun:
    evolution_id: str
    objective: str
    project_root: str
    mode: str
    status: str
    decision: str
    iteration: int
    max_iterations: int
    continuous_cycle_id: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    last_result: dict[str, Any]
    history: list[dict[str, Any]]
    lessons: list[str]
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_EVOLUTION_ITERATION_SERVICE = EvolutionIterationService()


class EvolutionEngine:

    TERMINAL_STATUSES = {
        EvolutionStatus.COMPLETED.value,
        EvolutionStatus.NO_CHANGES.value,
        EvolutionStatus.FAILED.value,
        EvolutionStatus.CANCELLED.value,
    }

    def __init__(
        self,
        project_root: str | None = None,
        continuous_dev_controller: (
            ContinuousDevController | None
        ) = None,
        storage_path: str | Path = (
            "data/evolution/evolution_runs.json"
        ),
        default_mode: str = (
            EvolutionMode.SAFE_AUTONOMOUS.value
        ),
        default_max_iterations: int = 5,
    ) -> None:

        self.project_root = str(
            project_root
            or default_project_root()
        ).strip()

        if not self.project_root:
            raise ValueError(
                "EvolutionEngine wymaga project_root."
            )

        self.continuous_dev_controller = (
            continuous_dev_controller
            if continuous_dev_controller is not None
            else ContinuousDevController(
                project_root=self.project_root
            )
        )

        self.storage_path = Path(
            storage_path
        )

        self.default_mode = self._normalize_mode(
            default_mode
        )

        self.default_max_iterations = max(
            1,
            int(default_max_iterations),
        )

        self._runs: dict[
            str,
            EvolutionRun,
        ] = {}

        self._ensure_storage()
        self.load()

    def create_run(
        self,
        objective: str,
        mode: str | None = None,
        max_iterations: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_objective = str(
            objective
        ).strip()

        if not normalized_objective:
            raise ValueError(
                "EvolutionEngine wymaga celu rozwoju."
            )

        now = self._utc_now()

        evolution_id = (
            f"evolution_{uuid4().hex}"
        )

        run = EvolutionRun(
            evolution_id=evolution_id,
            objective=normalized_objective,
            project_root=self.project_root,
            mode=self._normalize_mode(
                mode or self.default_mode
            ),
            status=EvolutionStatus.CREATED.value,
            decision=EvolutionDecision.NO_ACTION.value,
            iteration=0,
            max_iterations=max(
                1,
                int(
                    max_iterations
                    if max_iterations is not None
                    else self.default_max_iterations
                ),
            ),
            continuous_cycle_id=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
            last_result={},
            history=[],
            lessons=[],
            errors=[],
            warnings=[],
            metadata={
                "engine_version": "1.0.0",
                **(metadata or {}),
            },
        )

        self._runs[
            evolution_id
        ] = run

        self._add_event(
            run=run,
            event_type="CREATED",
            message="Utworzono nowy proces ewolucji.",
        )

        self.save()

        return run.to_dict()

    def start(
        self,
        evolution_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        run = self._get_run(
            evolution_id
        )

        if run is None:
            return self._not_found(
                evolution_id
            )

        if run.status in self.TERMINAL_STATUSES:
            return {
                "success": False,
                "status": run.status,
                "evolution_id": evolution_id,
                "error": (
                    "Zakończonego procesu ewolucji "
                    "nie można uruchomić ponownie."
                ),
            }

        run.status = EvolutionStatus.ANALYZING.value
        run.decision = (
            EvolutionDecision.START_CYCLE.value
        )
        run.updated_at = self._utc_now()

        self._add_event(
            run=run,
            event_type="STARTED",
            message="Rozpoczęto proces ewolucji.",
        )

        self.save()

        return self.run_iteration(
            evolution_id=evolution_id,
            context=context,
        )

    def create_and_start(
        self,
        objective: str,
        mode: str | None = None,
        max_iterations: int | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        created = self.create_run(
            objective=objective,
            mode=mode,
            max_iterations=max_iterations,
            metadata=metadata,
        )

        return self.start(
            evolution_id=created[
                "evolution_id"
            ],
            context=context,
        )

    def run_iteration(self, evolution_id: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        return _EVOLUTION_ITERATION_SERVICE.run_iteration(self, evolution_id, context)


    def approve(self, evolution_id: str, approved: bool, note: str | None=None, context: dict[str, Any] | None=None) -> dict[str, Any]:
        return _EVOLUTION_ITERATION_SERVICE.approve(self, evolution_id, approved, note, context)


    def continue_run(
        self,
        evolution_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        run = self._get_run(
            evolution_id
        )

        if run is None:
            return self._not_found(
                evolution_id
            )

        if run.status == (
            EvolutionStatus
            .WAITING_FOR_APPROVAL
            .value
        ):
            return {
                "success": False,
                "status": run.status,
                "evolution_id": evolution_id,
                "error": (
                    "Najpierw zaakceptuj lub "
                    "odrzuć oczekującą zmianę."
                ),
            }

        return self.run_iteration(
            evolution_id=evolution_id,
            context=context,
        )

    def pause(
        self,
        evolution_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        run = self._get_run(
            evolution_id
        )

        if run is None:
            return self._not_found(
                evolution_id
            )

        run.status = EvolutionStatus.PAUSED.value
        run.decision = EvolutionDecision.STOP.value
        run.updated_at = self._utc_now()

        if reason:
            run.warnings = self._unique_strings(
                run.warnings
                + [str(reason).strip()]
            )

        self._add_event(
            run=run,
            event_type="PAUSED",
            message=(
                str(reason).strip()
                if reason
                else "Proces ewolucji został wstrzymany."
            ),
        )

        self.save()

        return self._response(
            run=run,
            success=True,
            result={},
        )

    def resume(
        self,
        evolution_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        run = self._get_run(
            evolution_id
        )

        if run is None:
            return self._not_found(
                evolution_id
            )

        if run.status != EvolutionStatus.PAUSED.value:
            return {
                "success": False,
                "status": run.status,
                "evolution_id": evolution_id,
                "error": (
                    "Proces ewolucji nie jest wstrzymany."
                ),
            }

        run.status = EvolutionStatus.ANALYZING.value
        run.decision = EvolutionDecision.CONTINUE.value
        run.updated_at = self._utc_now()

        self._add_event(
            run=run,
            event_type="RESUMED",
            message="Wznowiono proces ewolucji.",
        )

        self.save()

        return self.run_iteration(
            evolution_id=evolution_id,
            context=context,
        )

    def cancel(
        self,
        evolution_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        run = self._get_run(
            evolution_id
        )

        if run is None:
            return self._not_found(
                evolution_id
            )

        run.status = EvolutionStatus.CANCELLED.value
        run.decision = EvolutionDecision.STOP.value
        run.completed_at = self._utc_now()
        run.updated_at = run.completed_at

        if reason:
            run.warnings = self._unique_strings(
                run.warnings
                + [str(reason).strip()]
            )

        if run.continuous_cycle_id:
            try:
                self.continuous_dev_controller.cancel_cycle(
                    cycle_id=run.continuous_cycle_id,
                    reason=reason,
                )
            except Exception as error:
                run.warnings = self._unique_strings(
                    run.warnings
                    + [
                        (
                            "Nie udało się anulować "
                            "Continuous Developer: "
                            f"{type(error).__name__}: {error}"
                        )
                    ]
                )

        self._add_event(
            run=run,
            event_type="CANCELLED",
            message=(
                str(reason).strip()
                if reason
                else "Proces ewolucji został anulowany."
            ),
        )

        self.save()

        return self._response(
            run=run,
            success=False,
            result={},
        )

    def get_run(
        self,
        evolution_id: str,
    ) -> dict[str, Any] | None:

        run = self._get_run(
            evolution_id
        )

        if run is None:
            return None

        return run.to_dict()

    def list_runs(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        runs = list(
            self._runs.values()
        )

        runs.sort(
            key=lambda item: item.updated_at,
            reverse=True,
        )

        return [
            run.to_dict()
            for run in runs[
                :max(
                    1,
                    int(limit),
                )
            ]
        ]

    def summary(
        self,
    ) -> dict[str, Any]:

        status_counts: dict[str, int] = {}

        for run in self._runs.values():
            status_counts[
                run.status
            ] = status_counts.get(
                run.status,
                0,
            ) + 1

        active_count = sum(
            1
            for run in self._runs.values()
            if run.status not in self.TERMINAL_STATUSES
        )

        return {
            "runs_count": len(
                self._runs
            ),
            "active_count": active_count,
            "status_counts": status_counts,
            "engine_version": "1.0.0",
            "project_root": self.project_root,
            "storage_path": str(
                self.storage_path
            ),
        }

    def save(
        self,
    ) -> None:

        self._ensure_storage()

        payload = {
            "version": "1.0.0",
            "saved_at": self._utc_now(),
            "runs": [
                run.to_dict()
                for run in self._runs.values()
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
            self._runs = {}
            return

        try:
            raw_text = self.storage_path.read_text(
                encoding="utf-8"
            )

            if not raw_text.strip():
                self._runs = {}
                return

            payload = json.loads(
                raw_text
            )

            raw_runs = payload.get(
                "runs",
                [],
            )

            loaded: dict[
                str,
                EvolutionRun,
            ] = {}

            if isinstance(
                raw_runs,
                list,
            ):
                for raw_run in raw_runs:
                    if not isinstance(
                        raw_run,
                        dict,
                    ):
                        continue

                    try:
                        run = self._run_from_dict(
                            raw_run
                        )

                        loaded[
                            run.evolution_id
                        ] = run

                    except (
                        TypeError,
                        ValueError,
                    ):
                        continue

            self._runs = loaded

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self._runs = {}

    def clear(
        self,
    ) -> None:

        self._runs = {}
        self.save()

    def _run_from_dict(
        self,
        data: dict[str, Any],
    ) -> EvolutionRun:

        return EvolutionRun(
            evolution_id=str(
                data.get(
                    "evolution_id",
                    f"evolution_{uuid4().hex}",
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
                    self.project_root,
                )
            ),
            mode=self._normalize_mode(
                data.get(
                    "mode",
                    self.default_mode,
                )
            ),
            status=str(
                data.get(
                    "status",
                    EvolutionStatus.CREATED.value,
                )
            ).upper(),
            decision=str(
                data.get(
                    "decision",
                    EvolutionDecision.NO_ACTION.value,
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
                        self.default_max_iterations,
                    ),
                    self.default_max_iterations,
                ),
            ),
            continuous_cycle_id=(
                self._optional_string(
                    data.get(
                        "continuous_cycle_id"
                    )
                )
            ),
            created_at=str(
                data.get(
                    "created_at",
                    self._utc_now(),
                )
            ),
            updated_at=str(
                data.get(
                    "updated_at",
                    self._utc_now(),
                )
            ),
            completed_at=(
                self._optional_string(
                    data.get(
                        "completed_at"
                    )
                )
            ),
            last_result=self._safe_dict(
                data.get(
                    "last_result",
                    {},
                )
            ),
            history=[
                dict(item)
                for item in self._safe_list(
                    data.get(
                        "history",
                        [],
                    )
                )
                if isinstance(
                    item,
                    dict,
                )
            ],
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
            metadata=self._safe_dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )

    def _complete_run(
        self,
        run: EvolutionRun,
        status: str,
        decision: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        run.status = status
        run.decision = decision
        run.last_result = self._safe_dict(
            result
        )
        run.completed_at = self._utc_now()
        run.updated_at = run.completed_at

        self._collect_lessons(
            run=run,
            result=result,
        )

        self._add_event(
            run=run,
            event_type="COMPLETED",
            message=(
                f"Proces ewolucji zakończono "
                f"ze statusem {status}."
            ),
        )

        self.save()

        return self._response(
            run=run,
            success=(
                status
                in {
                    EvolutionStatus.COMPLETED.value,
                    EvolutionStatus.NO_CHANGES.value,
                }
            ),
            result=result,
        )

    def _fail_run(
        self,
        run: EvolutionRun,
        error: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_error = str(
            error
        ).strip()

        if normalized_error:
            run.errors = self._unique_strings(
                run.errors
                + [normalized_error]
            )

        run.status = EvolutionStatus.FAILED.value
        run.decision = EvolutionDecision.STOP.value
        run.completed_at = self._utc_now()
        run.updated_at = run.completed_at
        run.last_result = self._safe_dict(
            result
        )

        self._add_event(
            run=run,
            event_type="FAILED",
            message=(
                normalized_error
                or "Proces ewolucji zakończył się błędem."
            ),
        )

        self.save()

        return self._response(
            run=run,
            success=False,
            result=result or {},
        )

    def _response(
        self,
        run: EvolutionRun,
        success: bool,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "success": bool(
                success
            ),
            "status": run.status,
            "decision": run.decision,
            "evolution_id": run.evolution_id,
            "continuous_cycle_id": (
                run.continuous_cycle_id
            ),
            "iteration": run.iteration,
            "max_iterations": run.max_iterations,
            "mode": run.mode,
            "result": dict(
                result
            ),
            "summary": {
                "objective": run.objective,
                "status": run.status,
                "decision": run.decision,
                "iteration": run.iteration,
                "max_iterations": (
                    run.max_iterations
                ),
                "lessons_count": len(
                    run.lessons
                ),
                "errors_count": len(
                    run.errors
                ),
                "warnings_count": len(
                    run.warnings
                ),
            },
        }

    def _should_auto_approve(
        self,
        run: EvolutionRun,
    ) -> bool:

        return run.mode == (
            EvolutionMode.AUTONOMOUS.value
        )

    def _build_iteration_objective(
        self,
        run: EvolutionRun,
    ) -> str:

        if run.iteration <= 1:
            return run.objective

        previous_lessons = "; ".join(
            run.lessons[-5:]
        )

        objective = (
            f"{run.objective}. "
            f"To jest iteracja {run.iteration}. "
            "Uwzględnij wyniki poprzednich iteracji."
        )

        if previous_lessons:
            objective += (
                f" Poprzednie wnioski: "
                f"{previous_lessons}"
            )

        return objective

    def _collect_lessons(
        self,
        run: EvolutionRun,
        result: dict[str, Any],
    ) -> None:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                result.get(
                    "lessons",
                    [],
                )
            )
        )

        summary = result.get(
            "summary"
        )

        if isinstance(
            summary,
            dict,
        ):
            values.extend(
                self._safe_list(
                    summary.get(
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

        run.lessons = self._unique_strings(
            run.lessons + values
        )

    def _collect_errors(
        self,
        run: EvolutionRun,
        result: dict[str, Any],
    ) -> None:

        values: list[Any] = []

        values.extend(
            self._safe_list(
                result.get(
                    "errors",
                    [],
                )
            )
        )

        error = result.get(
            "error"
        )

        if error:
            values.append(
                error
            )

        run.errors = self._unique_strings(
            run.errors + values
        )

    def _extract_error(
        self,
        result: dict[str, Any],
    ) -> str:

        for key in (
            "error",
            "message",
            "details",
        ):
            value = result.get(
                key
            )

            if value:
                return str(
                    value
                )

        nested = result.get(
            "result"
        )

        if isinstance(
            nested,
            dict,
        ):
            for key in (
                "error",
                "message",
                "details",
            ):
                value = nested.get(
                    key
                )

                if value:
                    return str(
                        value
                    )

        return (
            "EvolutionEngine otrzymał "
            "nieudany wynik."
        )

    def _add_event(
        self,
        run: EvolutionRun,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        event = EvolutionEvent(
            event_id=f"evolution_event_{uuid4().hex}",
            event_type=str(
                event_type
            ).upper(),
            message=str(
                message
            ),
            timestamp=self._utc_now(),
            status=run.status,
            iteration=run.iteration,
            metadata=self._safe_dict(
                metadata
            ),
        )

        run.history.append(
            {
                "event": event.to_dict(),
            }
        )

        run.updated_at = self._utc_now()

    def _normalize_mode(
        self,
        value: Any,
    ) -> str:

        normalized = str(
            value
        ).strip().upper()

        valid_modes = {
            mode.value
            for mode in EvolutionMode
        }

        if normalized in valid_modes:
            return normalized

        return EvolutionMode.SAFE_AUTONOMOUS.value

    def _get_run(
        self,
        evolution_id: str,
    ) -> EvolutionRun | None:

        return self._runs.get(
            str(
                evolution_id
            ).strip()
        )

    def _not_found(
        self,
        evolution_id: str,
    ) -> dict[str, Any]:

        return {
            "success": False,
            "status": "NOT_FOUND",
            "evolution_id": evolution_id,
            "error": (
                "Nie znaleziono procesu ewolucji."
            ),
        }

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
                        "runs": [],
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
