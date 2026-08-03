from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass(slots=True)
class ChangeCampaignStage:
    stage_id: str
    objective: str
    targets: list[str]
    replacements: dict[str, str] = field(
        default_factory=dict
    )
    depends_on: list[str] = field(
        default_factory=list
    )
    required_subsystems: list[str] = field(
        default_factory=list
    )
    allow_same_subsystem: bool = False
    allow_public_symbol_removal: bool = False
    auto_approve: bool = False
    status: str = "PENDING"
    attempt_count: int = 0
    started_at: str = ""
    completed_at: str = ""
    result: dict[str, Any] = field(
        default_factory=dict
    )
    errors: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def terminal(self) -> bool:
        return self.status in {
            "COMPLETED",
            "FAILED",
            "ROLLED_BACK",
            "PREVIEW_READY",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "objective": self.objective,
            "targets": list(self.targets),
            "replacements": dict(
                self.replacements
            ),
            "depends_on": list(
                self.depends_on
            ),
            "required_subsystems": list(
                self.required_subsystems
            ),
            "allow_same_subsystem": (
                self.allow_same_subsystem
            ),
            "allow_public_symbol_removal": (
                self.allow_public_symbol_removal
            ),
            "auto_approve": self.auto_approve,
            "status": self.status,
            "attempt_count": self.attempt_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": dict(self.result),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
    ) -> "ChangeCampaignStage":
        replacements = value.get(
            "replacements",
            {},
        )

        return cls(
            stage_id=str(
                value.get(
                    "stage_id",
                    "",
                )
            ),
            objective=str(
                value.get(
                    "objective",
                    "",
                )
            ),
            targets=[
                str(item)
                for item in value.get(
                    "targets",
                    [],
                )
            ],
            replacements={
                str(path): str(content)
                for path, content in (
                    replacements.items()
                    if isinstance(
                        replacements,
                        dict,
                    )
                    else []
                )
            },
            depends_on=[
                str(item)
                for item in value.get(
                    "depends_on",
                    [],
                )
            ],
            required_subsystems=[
                str(item)
                for item in value.get(
                    "required_subsystems",
                    [],
                )
            ],
            allow_same_subsystem=bool(
                value.get(
                    "allow_same_subsystem",
                    False,
                )
            ),
            allow_public_symbol_removal=bool(
                value.get(
                    "allow_public_symbol_removal",
                    False,
                )
            ),
            auto_approve=bool(
                value.get(
                    "auto_approve",
                    False,
                )
            ),
            status=str(
                value.get(
                    "status",
                    "PENDING",
                )
            ).upper(),
            attempt_count=max(
                0,
                int(
                    value.get(
                        "attempt_count",
                        0,
                    )
                    or 0
                ),
            ),
            started_at=str(
                value.get(
                    "started_at",
                    "",
                )
            ),
            completed_at=str(
                value.get(
                    "completed_at",
                    "",
                )
            ),
            result=dict(
                value.get(
                    "result",
                    {},
                )
                or {}
            ),
            errors=[
                str(item)
                for item in value.get(
                    "errors",
                    [],
                )
            ],
            metadata=dict(
                value.get(
                    "metadata",
                    {},
                )
                or {}
            ),
        )


@dataclass(slots=True)
class ChangeCampaign:
    campaign_id: str
    objective: str
    stages: list[ChangeCampaignStage]
    execution_order: list[str]
    fingerprint: str
    status: str = "PLANNED"
    current_stage_id: str = ""
    created_at: str = field(
        default_factory=utc_now
    )
    updated_at: str = field(
        default_factory=utc_now
    )
    completed_at: str = ""
    checkpoints: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )
    final_validation: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )
    rollback: dict[str, Any] = field(
        default_factory=dict
    )
    warnings: list[str] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def completed_stage_ids(
        self,
    ) -> list[str]:
        return [
            stage.stage_id
            for stage in self.stages
            if stage.status == "COMPLETED"
        ]

    @property
    def pending_stage_ids(
        self,
    ) -> list[str]:
        return [
            stage.stage_id
            for stage in self.stages
            if stage.status in {
                "PENDING",
                "RUNNING",
            }
        ]

    def stage(
        self,
        stage_id: str,
    ) -> ChangeCampaignStage:
        for stage in self.stages:
            if stage.stage_id == stage_id:
                return stage

        raise KeyError(
            f"Nie znaleziono etapu: {stage_id}"
        )

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "objective": self.objective,
            "status": self.status,
            "current_stage_id": (
                self.current_stage_id
            ),
            "execution_order": list(
                self.execution_order
            ),
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "stages": [
                stage.to_dict()
                for stage in self.stages
            ],
            "completed_stage_ids": (
                self.completed_stage_ids
            ),
            "pending_stage_ids": (
                self.pending_stage_ids
            ),
            "checkpoints": [
                dict(item)
                for item in self.checkpoints
            ],
            "final_validation": dict(
                self.final_validation
            ),
            "rollback": dict(
                self.rollback
            ),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
    ) -> "ChangeCampaign":
        stages = value.get(
            "stages",
            [],
        )

        return cls(
            campaign_id=str(
                value.get(
                    "campaign_id",
                    "",
                )
            ),
            objective=str(
                value.get(
                    "objective",
                    "",
                )
            ),
            stages=[
                ChangeCampaignStage.from_dict(
                    item
                )
                for item in stages
                if isinstance(
                    item,
                    dict,
                )
            ],
            execution_order=[
                str(item)
                for item in value.get(
                    "execution_order",
                    [],
                )
            ],
            fingerprint=str(
                value.get(
                    "fingerprint",
                    "",
                )
            ),
            status=str(
                value.get(
                    "status",
                    "PLANNED",
                )
            ).upper(),
            current_stage_id=str(
                value.get(
                    "current_stage_id",
                    "",
                )
            ),
            created_at=str(
                value.get(
                    "created_at",
                    "",
                )
                or utc_now()
            ),
            updated_at=str(
                value.get(
                    "updated_at",
                    "",
                )
                or utc_now()
            ),
            completed_at=str(
                value.get(
                    "completed_at",
                    "",
                )
            ),
            checkpoints=[
                dict(item)
                for item in value.get(
                    "checkpoints",
                    [],
                )
                if isinstance(
                    item,
                    dict,
                )
            ],
            final_validation=dict(
                value.get(
                    "final_validation",
                    {},
                )
                or {}
            ),
            rollback=dict(
                value.get(
                    "rollback",
                    {},
                )
                or {}
            ),
            warnings=[
                str(item)
                for item in value.get(
                    "warnings",
                    [],
                )
            ],
            errors=[
                str(item)
                for item in value.get(
                    "errors",
                    [],
                )
            ],
            metadata=dict(
                value.get(
                    "metadata",
                    {},
                )
                or {}
            ),
        )
