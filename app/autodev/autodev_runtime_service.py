from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from typing import Any

from app.autodev.autodev_cycle_manager import (
    AutoDevCycleManager,
)
from app.autodev.autodev_intelligence_orchestrator import (
    AutoDevIntelligenceOrchestrator,
)
from app.autodev.autodev_intelligence_v2 import (
    AutoDevIntelligenceV2,
)
from app.autodev.autodev_session_manager import (
    AutoDevSessionManager,
)
from app.autodev.autonomous_improvement_pipeline import (
    AutonomousImprovementPipeline,
    AutonomousImprovementPolicy,
)


class AutoDevRuntimeService:
    def __init__(
        self,
        project_root: str = default_project_root(),
        intelligence: AutoDevIntelligenceV2 | None = None,
        improvement_pipeline: (
            AutonomousImprovementPipeline | None
        ) = None,
        orchestrator: (
            AutoDevIntelligenceOrchestrator | None
        ) = None,
        session_manager: AutoDevSessionManager | None = None,
    ) -> None:

        self.project_root = project_root

        self.intelligence = (
            intelligence
            or AutoDevIntelligenceV2(
                project_root=project_root
            )
        )

        self.improvement_pipeline = (
            improvement_pipeline
            or AutonomousImprovementPipeline(
                policy=AutonomousImprovementPolicy(
                    project_root=project_root,
                    dry_run=True,
                    require_approval=True,
                    run_py_compile=True,
                    run_unit_tests=True,
                    auto_rollback=True,
                )
            )
        )

        self.orchestrator = (
            orchestrator
            or AutoDevIntelligenceOrchestrator(
                intelligence=self.intelligence,
                improvement_pipeline=(
                    self.improvement_pipeline
                ),
            )
        )

        self.session_manager = (
            session_manager
            or AutoDevSessionManager(
                orchestrator=self.orchestrator
            )
        )

        self.cycle_manager = AutoDevCycleManager(
            runtime_service=self
        )

        self.last_result: dict[str, Any] | None = None

    def analyze(self) -> dict[str, Any]:
        result = self.orchestrator.analyze()

        normalized = {
            **dict(result),
            "runtime_mode": "ANALYZE",
            "dry_run": True,
            "approved": False,
            "writes_code": False,
        }

        self.last_result = dict(normalized)
        return normalized

    def preview(self) -> dict[str, Any]:
        result = self.session_manager.run_preview_session()

        normalized = {
            **dict(result),
            "runtime_mode": "PREVIEW",
            "dry_run": True,
            "approved": False,
            "writes_code": False,
        }

        self.last_result = dict(normalized)
        return normalized

    def run_goal(
        self,
        goal: str,
    ) -> dict[str, Any]:
        return self.cycle_manager.run_preview_cycle(
            goal
        )

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "AUTODEV_RUNTIME_STATUS",
            "project_root": self.project_root,
            "dry_run": True,
            "requires_approval": True,
            "writes_code": False,
            "last_result": self.last_result,
            "intelligence": self.intelligence.status(),
            "orchestrator": self.orchestrator.status(),
            "session_manager": self.session_manager.status(),
            "cycle_manager": self.cycle_manager.status(),
        }
