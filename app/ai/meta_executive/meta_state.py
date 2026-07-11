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
class MetaState:

    objective: str
    mode: str = "SAFE_AUTONOMOUS"
    max_cycles: int = 5
    meta_id: str = field(
        default_factory=lambda: (
            f"meta-{uuid4().hex[:12]}"
        )
    )
    status: str = "CREATED"
    current_stage: str = "INITIALIZATION"
    selected_layer: str = ""
    selected_strategy: str = ""
    priority: str = "MEDIUM"
    risk_level: str = "UNKNOWN"
    cycle: int = 0
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
    roadmap: list[dict[str, Any]] = field(
        default_factory=list
    )
    decisions: list[dict[str, Any]] = field(
        default_factory=list
    )
    delegations: list[dict[str, Any]] = field(
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
                "MetaState wymaga objective."
            )

        self.mode = str(
            self.mode
        ).strip().upper()

        if self.mode not in self.VALID_MODES:
            raise ValueError(
                "Nieprawidłowy tryb Meta Executive: "
                f"{self.mode}"
            )

        self.max_cycles = int(
            self.max_cycles
        )

        if self.max_cycles < 1:
            raise ValueError(
                "max_cycles musi być większe od 0."
            )

        self.status = str(
            self.status
        ).strip().upper() or "CREATED"

        self.current_stage = str(
            self.current_stage
        ).strip().upper() or "INITIALIZATION"

        self.selected_layer = str(
            self.selected_layer
        ).strip().upper()

        self.selected_strategy = str(
            self.selected_strategy
        ).strip().upper()

        self.priority = str(
            self.priority
        ).strip().upper() or "MEDIUM"

        self.risk_level = str(
            self.risk_level
        ).strip().upper() or "UNKNOWN"

        self.cycle = max(
            0,
            int(
                self.cycle
            ),
        )

        self.context = self._safe_dict(
            self.context
        )

        self.metadata = self._safe_dict(
            self.metadata
        )

        self.roadmap = self._safe_dict_list(
            self.roadmap
        )

        self.decisions = self._safe_dict_list(
            self.decisions
        )

        self.delegations = self._safe_dict_list(
            self.delegations
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
                "Status Meta Executive nie może być pusty."
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

        normalized = str(
            stage
        ).strip().upper()

        if not normalized:
            raise ValueError(
                "Etap Meta Executive nie może być pusty."
            )

        self.current_stage = normalized
        self.touch()

    def increment_cycle(
        self,
    ) -> int:

        if self.is_terminal():
            raise RuntimeError(
                "Nie można zwiększyć cyklu "
                "dla zakończonego procesu."
            )

        if self.cycle >= self.max_cycles:
            raise RuntimeError(
                "Osiągnięto maksymalną liczbę cykli."
            )

        self.cycle += 1
        self.touch()

        return self.cycle

    def select_layer(
        self,
        layer_name: str,
        reason: str = "",
        confidence: float | None = None,
    ) -> None:

        normalized = str(
            layer_name
        ).strip().upper()

        if not normalized:
            raise ValueError(
                "Warstwa Meta Executive nie może być pusta."
            )

        self.selected_layer = normalized

        decision: dict[str, Any] = {
            "type": "LAYER_SELECTION",
            "layer": normalized,
            "reason": str(
                reason
            ).strip(),
            "cycle": self.cycle,
            "created_at": _utc_now(),
        }

        if confidence is not None:
            decision["confidence"] = self._normalize_score(
                confidence
            )

        self.decisions.append(
            decision
        )

        self.touch()

    def select_strategy(
        self,
        strategy: str,
        reason: str = "",
        confidence: float | None = None,
    ) -> None:

        normalized = str(
            strategy
        ).strip().upper()

        if not normalized:
            raise ValueError(
                "Strategia Meta Executive nie może być pusta."
            )

        self.selected_strategy = normalized

        decision: dict[str, Any] = {
            "type": "STRATEGY_SELECTION",
            "strategy": normalized,
            "reason": str(
                reason
            ).strip(),
            "cycle": self.cycle,
            "created_at": _utc_now(),
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
                "Nieprawidłowy priorytet Meta Executive: "
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

    def add_roadmap_step(
        self,
        name: str,
        description: str = "",
        layer: str = "",
        priority: str = "MEDIUM",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_name = str(
            name
        ).strip()

        if not normalized_name:
            raise ValueError(
                "Krok roadmapy Meta Executive wymaga nazwy."
            )

        step = {
            "step_id": f"meta-step-{uuid4().hex[:10]}",
            "name": normalized_name,
            "description": str(
                description
            ).strip(),
            "layer": str(
                layer
            ).strip().upper(),
            "priority": str(
                priority
            ).strip().upper() or "MEDIUM",
            "status": "PENDING",
            "created_at": _utc_now(),
            "metadata": self._safe_dict(
                metadata
            ),
        }

        self.roadmap.append(
            step
        )

        self.touch()

        return deepcopy(
            step
        )

    def update_roadmap_step(
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

        for step in self.roadmap:
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

        normalized = str(
            decision
        ).strip()

        if not normalized:
            raise ValueError(
                "Decyzja Meta Executive nie może być pusta."
            )

        item: dict[str, Any] = {
            "type": "META_DECISION",
            "decision": normalized,
            "reason": str(
                reason
            ).strip(),
            "cycle": self.cycle,
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

    def delegate(
        self,
        layer_name: str,
        command: str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        layer = str(
            layer_name
        ).strip().upper()

        normalized_command = str(
            command
        ).strip()

        if not layer:
            raise ValueError(
                "Delegacja Meta Executive wymaga warstwy."
            )

        if not normalized_command:
            raise ValueError(
                "Delegacja Meta Executive wymaga polecenia."
            )

        self.selected_layer = layer

        delegation = {
            "delegation_id": f"meta-delegation-{uuid4().hex[:10]}",
            "layer": layer,
            "command": normalized_command,
            "reason": str(
                reason
            ).strip(),
            "status": "CREATED",
            "cycle": self.cycle,
            "created_at": _utc_now(),
            "metadata": self._safe_dict(
                metadata
            ),
        }

        self.delegations.append(
            delegation
        )

        self.touch()

        return deepcopy(
            delegation
        )

    def update_delegation(
        self,
        delegation_id: str,
        status: str,
        result: Any = None,
    ) -> bool:

        normalized_id = str(
            delegation_id
        ).strip()

        normalized_status = str(
            status
        ).strip().upper()

        for delegation in self.delegations:
            if str(
                delegation.get(
                    "delegation_id",
                    "",
                )
            ).strip() != normalized_id:
                continue

            delegation["status"] = normalized_status
            delegation["updated_at"] = _utc_now()

            if result is not None:
                delegation["result"] = deepcopy(
                    result
                )

            self.touch()
            return True

        return False

    def add_result(
        self,
        source: str,
        status: str,
        result: Any = None,
        success: bool | None = None,
    ) -> dict[str, Any]:

        item = {
            "source": str(
                source
            ).strip().upper(),
            "status": str(
                status
            ).strip().upper(),
            "result": deepcopy(
                result
            ),
            "cycle": self.cycle,
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
            and self.cycle < self.max_cycles
        )

    def summary(
        self,
    ) -> dict[str, Any]:

        completed_steps = sum(
            1
            for step in self.roadmap
            if str(
                step.get(
                    "status",
                    "",
                )
            ).upper() == "COMPLETED"
        )

        failed_steps = sum(
            1
            for step in self.roadmap
            if str(
                step.get(
                    "status",
                    "",
                )
            ).upper() == "FAILED"
        )

        return {
            "meta_id": self.meta_id,
            "objective": self.objective,
            "mode": self.mode,
            "status": self.status,
            "current_stage": self.current_stage,
            "selected_layer": self.selected_layer,
            "selected_strategy": self.selected_strategy,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "cycle": self.cycle,
            "max_cycles": self.max_cycles,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "roadmap_steps": len(
                self.roadmap
            ),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "decisions_count": len(
                self.decisions
            ),
            "delegations_count": len(
                self.delegations
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
            "meta_id": self.meta_id,
            "objective": self.objective,
            "mode": self.mode,
            "max_cycles": self.max_cycles,
            "status": self.status,
            "current_stage": self.current_stage,
            "selected_layer": self.selected_layer,
            "selected_strategy": self.selected_strategy,
            "priority": self.priority,
            "risk_level": self.risk_level,
            "cycle": self.cycle,
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
            "roadmap": deepcopy(
                self.roadmap
            ),
            "decisions": deepcopy(
                self.decisions
            ),
            "delegations": deepcopy(
                self.delegations
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
    ) -> MetaState:

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "MetaState.from_dict wymaga dict."
            )

        return cls(
            meta_id=str(
                data.get(
                    "meta_id",
                    f"meta-{uuid4().hex[:12]}",
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
            max_cycles=int(
                data.get(
                    "max_cycles",
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
            selected_layer=str(
                data.get(
                    "selected_layer",
                    "",
                )
            ),
            selected_strategy=str(
                data.get(
                    "selected_strategy",
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
            cycle=int(
                data.get(
                    "cycle",
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
            roadmap=deepcopy(
                data.get(
                    "roadmap",
                    [],
                )
            ),
            decisions=deepcopy(
                data.get(
                    "decisions",
                    [],
                )
            ),
            delegations=deepcopy(
                data.get(
                    "delegations",
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
