"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass
class DirectorState:

    objective: str
    mode: str = "SAFE_AUTONOMOUS"
    max_iterations: int = 5
    director_id: str = field(
        default_factory=lambda: (
            f"director-{uuid4().hex[:12]}"
        )
    )
    status: str = "CREATED"
    current_stage: str = "INITIALIZATION"
    selected_module: str = ""
    priority: str = "MEDIUM"
    risk_level: str = "UNKNOWN"
    iteration: int = 0
    requires_approval: bool = False
    approved: bool | None = None
    created_at: str = field(
        default_factory=_utc_now
    )
    updated_at: str = field(
        default_factory=_utc_now
    )
    context: dict[str, Any] = field(
        default_factory=dict
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    plan: list[dict[str, Any]] = field(
        default_factory=list
    )
    decisions: list[dict[str, Any]] = field(
        default_factory=list
    )
    results: list[dict[str, Any]] = field(
        default_factory=list
    )
    lessons: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )

    VALID_MODES = {
        "MANUAL",
        "SAFE_AUTONOMOUS",
        "AUTONOMOUS",
    }

    TERMINAL_STATUSES = {
        "COMPLETED",
        "NO_ACTION",
        "FAILED",
        "CANCELLED",
    }

    def __post_init__(
        self,
    ) -> None:

        self.objective = str(
            self.objective
        ).strip()

        if not self.objective:
            raise ValueError(
                "DirectorState wymaga objective."
            )

        self.mode = str(
            self.mode
        ).strip().upper()

        if self.mode not in self.VALID_MODES:
            raise ValueError(
                "Nieprawidłowy tryb Project Director: "
                f"{self.mode}"
            )

        self.max_iterations = int(
            self.max_iterations
        )

        if self.max_iterations < 1:
            raise ValueError(
                "max_iterations musi być większe od 0."
            )

        self.status = str(
            self.status
        ).strip().upper() or "CREATED"

        self.current_stage = str(
            self.current_stage
        ).strip().upper() or "INITIALIZATION"

        self.selected_module = str(
            self.selected_module
        ).strip().upper()

        self.priority = str(
            self.priority
        ).strip().upper() or "MEDIUM"

        self.risk_level = str(
            self.risk_level
        ).strip().upper() or "UNKNOWN"

        self.iteration = max(
            0,
            int(
                self.iteration
            ),
        )

        self.context = self._safe_dict(
            self.context
        )

        self.metadata = self._safe_dict(
            self.metadata
        )

        self.plan = self._safe_dict_list(
            self.plan
        )

        self.decisions = self._safe_dict_list(
            self.decisions
        )

        self.results = self._safe_dict_list(
            self.results
        )

        self.lessons = self._safe_string_list(
            self.lessons
        )

        self.warnings = self._safe_string_list(
            self.warnings
        )

        self.errors = self._safe_string_list(
            self.errors
        )

    def set_status(
        self,
        status: str,
        stage: str | None = None,
    ) -> None:

        normalized_status = str(
            status
        ).strip().upper()

        if not normalized_status:
            raise ValueError(
                "Status Project Director nie może być pusty."
            )

        self.status = normalized_status

        if stage is not None:
            normalized_stage = str(
                stage
            ).strip().upper()

            if normalized_stage:
                self.current_stage = normalized_stage

        self.touch()

    def set_stage(
        self,
        stage: str,
    ) -> None:

        normalized_stage = str(
            stage
        ).strip().upper()

        if not normalized_stage:
            raise ValueError(
                "Etap Project Director nie może być pusty."
            )

        self.current_stage = normalized_stage
        self.touch()

    def select_module(
        self,
        module_name: str,
        reason: str = "",
        confidence: float | None = None,
    ) -> None:

        normalized_module = str(
            module_name
        ).strip().upper()

        if not normalized_module:
            raise ValueError(
                "Nazwa wybranego modułu nie może być pusta."
            )

        self.selected_module = normalized_module

        decision: dict[str, Any] = {
            "type": "MODULE_SELECTION",
            "module": normalized_module,
            "reason": str(
                reason
            ).strip(),
            "created_at": _utc_now(),
            "iteration": self.iteration,
        }

        if confidence is not None:
            decision["confidence"] = self._normalize_score(
                confidence
            )

        self.decisions.append(
            decision
        )

        self.touch()

    def set_priority(
        self,
        priority: str,
    ) -> None:

        normalized = str(
            priority
        ).strip().upper()

        valid = {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }

        if normalized not in valid:
            raise ValueError(
                "Nieprawidłowy priorytet Project Director: "
                f"{normalized}"
            )

        self.priority = normalized
        self.touch()

    def set_risk(
        self,
        risk_level: str,
        requires_approval: bool | None = None,
    ) -> None:

        normalized = str(
            risk_level
        ).strip().upper()

        valid = {
            "UNKNOWN",
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }

        if normalized not in valid:
            raise ValueError(
                "Nieprawidłowy poziom ryzyka: "
                f"{normalized}"
            )

        self.risk_level = normalized

        if requires_approval is not None:
            self.requires_approval = bool(
                requires_approval
            )

        self.touch()

    def set_approval(
        self,
        approved: bool | None,
    ) -> None:

        self.approved = approved
        self.touch()

    def increment_iteration(
        self,
    ) -> int:

        if self.is_terminal():
            raise RuntimeError(
                "Nie można zwiększyć iteracji "
                "dla zakończonego procesu."
            )

        if self.iteration >= self.max_iterations:
            raise RuntimeError(
                "Osiągnięto maksymalną liczbę iteracji."
            )

        self.iteration += 1
        self.touch()

        return self.iteration

    def add_plan_step(
        self,
        name: str,
        module: str = "",
        description: str = "",
        priority: str = "MEDIUM",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_name = str(
            name
        ).strip()

        if not normalized_name:
            raise ValueError(
                "Krok planu wymaga nazwy."
            )

        step = {
            "step_id": f"step-{uuid4().hex[:10]}",
            "name": normalized_name,
            "module": str(
                module
            ).strip().upper(),
            "description": str(
                description
            ).strip(),
            "priority": str(
                priority
            ).strip().upper() or "MEDIUM",
            "status": "PENDING",
            "created_at": _utc_now(),
            "metadata": self._safe_dict(
                metadata
            ),
        }

        self.plan.append(
            step
        )

        self.touch()

        return deepcopy(
            step
        )

    def update_plan_step(
        self,
        step_id: str,
        status: str,
        result: Any = None,
    ) -> bool:

        normalized_id = str(
            step_id
        ).strip()

        normalized_status = str(
            status
        ).strip().upper()

        for step in self.plan:
            if str(
                step.get(
                    "step_id",
                    "",
                )
            ).strip() != normalized_id:
                continue

            step["status"] = normalized_status
            step["updated_at"] = _utc_now()

            if result is not None:
                step["result"] = deepcopy(
                    result
                )

            self.touch()
            return True

        return False

    def add_decision(
        self,
        decision: str,
        reason: str = "",
        score: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_decision = str(
            decision
        ).strip()

        if not normalized_decision:
            raise ValueError(
                "Decyzja nie może być pusta."
            )

        item: dict[str, Any] = {
            "type": "DIRECTOR_DECISION",
            "decision": normalized_decision,
            "reason": str(
                reason
            ).strip(),
            "iteration": self.iteration,
            "created_at": _utc_now(),
            "metadata": self._safe_dict(
                metadata
            ),
        }

        if score is not None:
            item["score"] = self._normalize_score(
                score
            )

        self.decisions.append(
            item
        )

        self.touch()

        return deepcopy(
            item
        )

    def add_result(
        self,
        module: str,
        status: str,
        result: Any = None,
        success: bool | None = None,
    ) -> dict[str, Any]:

        item = {
            "module": str(
                module
            ).strip().upper(),
            "status": str(
                status
            ).strip().upper(),
            "result": deepcopy(
                result
            ),
            "iteration": self.iteration,
            "created_at": _utc_now(),
        }

        if success is not None:
            item["success"] = bool(
                success
            )

        self.results.append(
            item
        )

        self.touch()

        return deepcopy(
            item
        )

    def add_lesson(
        self,
        lesson: str,
    ) -> None:

        self._append_unique_text(
            self.lessons,
            lesson,
        )

    def add_warning(
        self,
        warning: str,
    ) -> None:

        self._append_unique_text(
            self.warnings,
            warning,
        )

    def add_error(
        self,
        error: str,
    ) -> None:

        self._append_unique_text(
            self.errors,
            error,
        )

    def is_terminal(
        self,
    ) -> bool:

        return self.status in self.TERMINAL_STATUSES

    def can_continue(
        self,
    ) -> bool:

        return (
            not self.is_terminal()
            and self.iteration < self.max_iterations
        )

    def summary(
        self,
    ) -> dict[str, Any]:

        completed_steps = sum(
            1
            for step in self.plan
            if str(
                step.get(
                    "status",
                    "",
                )
            ).upper() == "COMPLETED"
        )

        failed_steps = sum(
            1
            for step in self.plan
            if str(
                step.get(
                    "status",
                    "",
                )
            ).upper() == "FAILED"
        )

        return {
            "director_id": self.director_id,
            "objective": self.objective,
            "mode": self.mode,
            "status": self.status,
            "current_stage": self.current_stage,
            "selected_module": self.selected_module,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "plan_steps": len(
                self.plan
            ),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "decisions_count": len(
                self.decisions
            ),
            "results_count": len(
                self.results
            ),
            "lessons_count": len(
                self.lessons
            ),
            "warnings_count": len(
                self.warnings
            ),
            "errors_count": len(
                self.errors
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "director_id": self.director_id,
            "objective": self.objective,
            "mode": self.mode,
            "max_iterations": self.max_iterations,
            "status": self.status,
            "current_stage": self.current_stage,
            "selected_module": self.selected_module,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "iteration": self.iteration,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "context": deepcopy(
                self.context
            ),
            "metadata": deepcopy(
                self.metadata
            ),
            "plan": deepcopy(
                self.plan
            ),
            "decisions": deepcopy(
                self.decisions
            ),
            "results": deepcopy(
                self.results
            ),
            "lessons": list(
                self.lessons
            ),
            "warnings": list(
                self.warnings
            ),
            "errors": list(
                self.errors
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DirectorState:

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "DirectorState.from_dict wymaga dict."
            )

        return cls(
            director_id=str(
                data.get(
                    "director_id",
                    f"director-{uuid4().hex[:12]}",
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
                    "SAFE_AUTONOMOUS",
                )
            ),
            max_iterations=int(
                data.get(
                    "max_iterations",
                    5,
                )
            ),
            status=str(
                data.get(
                    "status",
                    "CREATED",
                )
            ),
            current_stage=str(
                data.get(
                    "current_stage",
                    "INITIALIZATION",
                )
            ),
            selected_module=str(
                data.get(
                    "selected_module",
                    "",
                )
            ),
            priority=str(
                data.get(
                    "priority",
                    "MEDIUM",
                )
            ),
            risk_level=str(
                data.get(
                    "risk_level",
                    "UNKNOWN",
                )
            ),
            iteration=int(
                data.get(
                    "iteration",
                    0,
                )
            ),
            requires_approval=bool(
                data.get(
                    "requires_approval",
                    False,
                )
            ),
            approved=data.get(
                "approved"
            ),
            created_at=str(
                data.get(
                    "created_at",
                    _utc_now(),
                )
            ),
            updated_at=str(
                data.get(
                    "updated_at",
                    _utc_now(),
                )
            ),
            context=deepcopy(
                data.get(
                    "context",
                    {},
                )
            ),
            metadata=deepcopy(
                data.get(
                    "metadata",
                    {},
                )
            ),
            plan=deepcopy(
                data.get(
                    "plan",
                    [],
                )
            ),
            decisions=deepcopy(
                data.get(
                    "decisions",
                    [],
                )
            ),
            results=deepcopy(
                data.get(
                    "results",
                    [],
                )
            ),
            lessons=list(
                data.get(
                    "lessons",
                    [],
                )
            ),
            warnings=list(
                data.get(
                    "warnings",
                    [],
                )
            ),
            errors=list(
                data.get(
                    "errors",
                    [],
                )
            ),
        )

    def touch(
        self,
    ) -> None:

        self.updated_at = _utc_now()

    def _append_unique_text(
        self,
        collection: list[str],
        value: str,
    ) -> None:

        text = str(
            value
        ).strip()

        if not text:
            return

        existing = {
            item.lower()
            for item in collection
        }

        if text.lower() not in existing:
            collection.append(
                text
            )

        self.touch()

    def _normalize_score(
        self,
        value: float,
    ) -> float:

        score = float(
            value
        )

        return max(
            0.0,
            min(
                1.0,
                score,
            ),
        )

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return deepcopy(
                value
            )

        return {}

    def _safe_dict_list(
        self,
        value: Any,
    ) -> list[dict[str, Any]]:

        if not isinstance(
            value,
            (list, tuple),
        ):
            return []

        return [
            deepcopy(
                item
            )
            for item in value
            if isinstance(
                item,
                dict,
            )
        ]

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        if not isinstance(
            value,
            (list, tuple, set),
        ):
            return []

        result: list[str] = []
        seen: set[str] = set()

        for item in value:
            text = str(
                item
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
