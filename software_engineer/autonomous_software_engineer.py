from __future__ import annotations

from .software_engineer_command_router import SoftwareEngineerCommandRouter
from .software_engineer_result_utils import (
    collect_execution_errors,
    effective_execution_status,
)

from app.core.project_paths import default_project_root

import re
from pathlib import Path
from typing import Any

from .decomposition_controller import DecompositionController
from .execution_recovery import (
    ExecutionRecoveryOrchestrator,
    ExecutionRecoveryPolicy,
)
from .implementation_executor import ImplementationExecutor
from .implementation_graph import ImplementationGraph
from .feature_planner import FeaturePlanner
from .multi_file_feature_executor import (
    MultiFileFeatureExecutor,
)
from .multi_file_feature_workflow import (
    MultiFileFeatureWorkflow,
)
from .multi_file_refactor_workflow import (
    MultiFileRefactorWorkflow,
)
from .cross_module_change_workflow import (
    CrossModuleChangeWorkflow,
)
from .models import ImplementationPlan


_SOFTWARE_ENGINEER_COMMAND_ROUTER = SoftwareEngineerCommandRouter()


class AutonomousSoftwareEngineerController:

    COMMAND_PHRASES = (
        "autonomous software engineer",
        "autonomiczny software engineer",
        "autonomiczny programista",
        "zaimplementuj autonomicznie",
        "zbuduj funkcję autonomicznie",
        "zbuduj funkcje autonomicznie",
        "napisz funkcję autonomicznie",
        "napisz funkcje autonomicznie",
        "stwórz funkcjonalność autonomicznie",
        "stworz funkcjonalnosc autonomicznie",
        "zbuduj wieloplikową funkcjonalność autonomicznie",
        "zbuduj wieloplikowa funkcjonalnosc autonomicznie",
        "zrefaktoryzuj wieloplikowo",
        "zrefaktoryzuj autonomicznie wiele plików",
        "zmodyfikuj wieloplikowo",
        "multi file refactor",
        "refactor multi file",
        "zmiana między modułami",
        "zmianę między modułami",
        "zmiane miedzy modulami",
        "zmiana miedzy modulami",
        "zmień moduły autonomicznie",
        "zmien moduly autonomicznie",
        "cross module change",
        "cross-module change",
        "kampania zmian",
        "kampanię zmian",
        "kampanie zmian",
        "wieloetapowa kampania",
        "wznów kampanię",
        "change campaign",
        "resume campaign",
        "portfolio kampanii", "wiele kampanii", "multi campaign", "uczenie autonomii", "uczenia autonomii", "naucz jarvisa", "naucz jarvis-a", "historia autonomii", "profil uczenia", "zastosuj naukę", "zastosuj nauke", "autonomous learning",
        "optymalizuj portfolio", "dyrektor kampanii", "dyrektora kampanii", "campaign director", "pełna autonomia", "pełną autonomię", "pelna autonomia", "pelna autonomie", "full autonomy", "duży cel autonomicznie",
    )

    CODE_CATEGORIES = (
        "implementation",
        "integration",
        "refactor",
        "bugfix",
        "maintenance",
    )

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        task_queue: object | None = None,
        decomposition_controller: object | None = None,
        implementation_executor: object | None = None,
        feature_planner: FeaturePlanner | None = None,
        multi_file_executor: MultiFileFeatureExecutor | None = None,
        multi_file_workflow: MultiFileFeatureWorkflow | None = None,
        multi_file_refactor_workflow: (
            MultiFileRefactorWorkflow | None
        ) = None,
        cross_module_workflow: (
            CrossModuleChangeWorkflow | None
        ) = None,
    ) -> None:
        self.project_root = Path(
            project_root
            or default_project_root()
        ).expanduser().resolve(
            strict=False
        )
        self.decomposition_controller = (
            decomposition_controller
            or DecompositionController(
                task_queue=task_queue
            )
        )
        self.implementation_executor = (
            implementation_executor
            or ImplementationExecutor(
                project_root=self.project_root
            )
        )
        self.feature_planner = (
            feature_planner
            or FeaturePlanner()
        )
        self.multi_file_executor = (
            multi_file_executor
            or MultiFileFeatureExecutor(
                project_root=self.project_root
            )
        )
        self.multi_file_workflow = (
            multi_file_workflow
            or MultiFileFeatureWorkflow(
                project_root=self.project_root,
                feature_planner=self.feature_planner,
                feature_executor=self.multi_file_executor,
            )
        )
        self.multi_file_refactor_workflow = (
            multi_file_refactor_workflow
            or MultiFileRefactorWorkflow(
                project_root=self.project_root,
            )
        )
        self.cross_module_workflow = (
            cross_module_workflow
            or CrossModuleChangeWorkflow(
                project_root=self.project_root,
                refactor_workflow=(
                    self.multi_file_refactor_workflow
                ),
            )
        )

    @classmethod
    def can_handle(
        cls,
        command: str,
    ) -> bool:
        normalized = cls._normalize(
            command
        )

        return any(
            phrase in normalized
            for phrase in cls.COMMAND_PHRASES
        )

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _SOFTWARE_ENGINEER_COMMAND_ROUTER.handle(
            self,
            command,
            context,
        )

    def _schedule_code_task(
        self,
        *,
        plan: ImplementationPlan,
        target_path: str,
        proposed_content: str,
    ) -> dict[str, Any]:
        code_task = next(
            (
                task
                for task in plan.tasks
                if task.category.lower()
                in self.CODE_CATEGORIES
            ),
            None,
        )

        if code_task is None:
            return {
                "success": False,
                "status": "NO_CODE_TASK",
                "scheduled_task": None,
            }

        code_index = plan.execution_order.index(
            code_task.task_id
        )
        completed = set(
            plan.execution_order[
                :code_index
            ]
        )

        scheduling = (
            self.decomposition_controller
            .scheduler
            .schedule_next(
                plan,
                completed_task_ids=completed,
                failed_task_ids=set(),
                enqueue=False,
            )
        )

        scheduled_task = scheduling.get(
            "scheduled_task"
        )

        if not isinstance(
            scheduled_task,
            dict,
        ):
            scheduled_task = {
                "task_id": code_task.task_id,
                "title": code_task.title,
                "score": 0.0,
                "estimated_minutes": (
                    code_task.estimated_minutes
                ),
                "category": code_task.category,
                "payload": {
                    "objective": plan.objective,
                    "task_id": code_task.task_id,
                    "title": code_task.title,
                    "description": (
                        code_task.description
                    ),
                    "category": code_task.category,
                    "priority": code_task.priority,
                    "estimated_roi": (
                        code_task.estimated_roi
                    ),
                    "estimated_risk": (
                        code_task.estimated_risk
                    ),
                    "acceptance_criteria": list(
                        code_task.acceptance_criteria
                    ),
                    "metadata": dict(
                        code_task.metadata
                    ),
                },
            }

        payload = dict(
            scheduled_task.get(
                "payload",
                {},
            )
            or {}
        )
        metadata = dict(
            payload.get(
                "metadata",
                {},
            )
            or {}
        )

        if target_path:
            payload["path"] = target_path
            payload["target_path"] = (
                target_path
            )

        if proposed_content:
            payload["proposed_content"] = (
                proposed_content
            )

        metadata.update(
            {
                "source": (
                    "autonomous_software_engineer"
                ),
                "full_autonomous_flow": True,
            }
        )
        payload["metadata"] = metadata
        payload["description"] = (
            plan.objective
        )
        scheduled_task["payload"] = payload

        return {
            **dict(scheduling),
            "success": True,
            "status": "SCHEDULED",
            "scheduled_task": scheduled_task,
        }

    @classmethod
    def _is_multi_file_request(
        cls,
        command: str,
        context: dict[str, Any],
    ) -> bool:
        explicit = context.get(
            "multi_file"
        )

        if explicit is not None:
            return bool(
                explicit
            )

        normalized = cls._normalize(
            command
        )

        return any(
            phrase in normalized
            for phrase in (
                "wieloplik",
                "multi-file",
                "multi file",
                "funkcjonalność autonomicznie",
                "funkcjonalnosc autonomicznie",
            )
        )

    @classmethod
    def _extract_objective(
        cls,
        command: str,
    ) -> str:
        normalized = " ".join(
            str(command).strip().split()
        )
        lowered = normalized.lower()

        for phrase in sorted(
            cls.COMMAND_PHRASES,
            key=len,
            reverse=True,
        ):
            index = lowered.find(
                phrase
            )

            if index >= 0:
                normalized = (
                    normalized[
                        :index
                    ]
                    + normalized[
                        index
                        + len(phrase):
                    ]
                )
                break

        return normalized.strip(
            " :-|"
        )

    @staticmethod
    def _extract_target_path(
        command: str,
    ) -> str:
        value = str(command)

        patterns = (
            (
                r"(?P<path>[A-Za-z]:[\\/]"
                r"[^:*?\"<>|\r\n]+?\.py)"
            ),
            (
                r"(?P<path>(?:app|tests)[\\/]"
                r"[A-Za-z0-9_.\-/\\]+?\.py)"
            ),
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                value,
                flags=re.IGNORECASE,
            )

            if match:
                return match.group(
                    "path"
                ).replace(
                    "\\",
                    "/",
                )

        return ""

    @staticmethod
    def _execution_errors(
        execution: dict[str, Any],
    ) -> list[str]:
        return collect_execution_errors(
            execution
        )


    @staticmethod
    def _effective_status(
        execution: dict[str, Any],
    ) -> str:
        return effective_execution_status(
            execution
        )


    @staticmethod
    def _normalize(
        command: str,
    ) -> str:
        return " ".join(
            str(command).lower().split()
        )
