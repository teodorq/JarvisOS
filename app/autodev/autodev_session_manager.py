from __future__ import annotations

import uuid
from typing import Any

from app.autodev.autodev_intelligence_orchestrator import (
    AutoDevIntelligenceOrchestrator,
)
from app.autodev.execution_guard import (
    ExecutionGuard,
)
from app.autodev.progress_tracker import (
    ProgressTracker,
)
from app.autodev.task_execution_planner import (
    TaskExecutionPlanner,
)


class AutoDevSessionManager:
    """
    Zarządza pełną sesją AutoDev w bezpiecznym trybie.

    Domyślne zachowanie:
    - analiza,
    - plan,
    - preview,
    - brak automatycznego wykonania.
    """

    def __init__(
        self,
        orchestrator: AutoDevIntelligenceOrchestrator,
        planner: TaskExecutionPlanner | None = None,
        guard: ExecutionGuard | None = None,
        tracker: ProgressTracker | None = None,
    ) -> None:

        self.orchestrator = orchestrator
        self.planner = (
            planner
            or TaskExecutionPlanner()
        )
        self.guard = (
            guard
            or ExecutionGuard()
        )
        self.tracker = (
            tracker
            or ProgressTracker()
        )

        self.last_result: dict[str, Any] | None = None

    def run_preview_session(
        self,
    ) -> dict[str, Any]:

        session_id = str(
            uuid.uuid4()
        )

        self.tracker.start(
            session_id=session_id,
            total_steps=4,
        )

        self.tracker.update(
            step_id="analysis",
            status="RUNNING",
        )

        analysis = self.orchestrator.analyze()

        self.tracker.update(
            step_id="analysis",
            status="COMPLETED",
        )

        selected = (
            analysis.get(
                "cycle",
                {},
            )
            or {}
        ).get(
            "selected"
        )

        if not isinstance(
            selected,
            dict,
        ):
            return self._finish(
                {
                    "success": True,
                    "status": "NO_SELECTED_TASK",
                    "session_id": session_id,
                    "analysis": analysis,
                    "progress": self.tracker.status(),
                    "writes_code": False,
                }
            )

        task = selected.get(
            "task"
        )

        if not isinstance(
            task,
            dict,
        ):
            return self._finish(
                {
                    "success": False,
                    "status": "INVALID_SELECTED_TASK",
                    "session_id": session_id,
                    "analysis": analysis,
                    "progress": self.tracker.status(),
                    "writes_code": False,
                }
            )

        self.tracker.update(
            step_id="plan",
            status="RUNNING",
        )

        plan = self.planner.build_plan(
            task
        )

        self.tracker.update(
            step_id="plan",
            status=(
                "COMPLETED"
                if plan.success
                else "FAILED"
            ),
        )

        if not plan.success:
            return self._finish(
                {
                    "success": False,
                    "status": plan.status,
                    "session_id": session_id,
                    "analysis": analysis,
                    "plan": plan.to_dict(),
                    "progress": self.tracker.status(),
                    "writes_code": False,
                }
            )

        prediction = {
            "risk_score": selected.get(
                "predicted_risk",
                0.0,
            ),
            "risk_level": selected.get(
                "risk_level",
                "",
            ),
        }

        self.tracker.update(
            step_id="guard",
            status="RUNNING",
        )

        guard = self.guard.evaluate(
            task=task,
            prediction=prediction,
            validation={
                "success": True,
                "status": "VALID",
            },
            approved=False,
        )

        self.tracker.update(
            step_id="guard",
            status="COMPLETED",
        )

        if guard.status == "EXECUTION_BLOCKED":
            return self._finish(
                {
                    "success": True,
                    "status": "RISK_BLOCKED",
                    "session_id": session_id,
                    "analysis": analysis,
                    "plan": plan.to_dict(),
                    "guard": guard.to_dict(),
                    "progress": self.tracker.status(),
                    "writes_code": False,
                }
            )

        self.tracker.update(
            step_id="preview",
            status="RUNNING",
        )

        preview = self.orchestrator.preview_selected()

        self.tracker.update(
            step_id="preview",
            status="COMPLETED",
        )

        result = {
            "success": bool(
                preview.get(
                    "success",
                    False,
                )
            ),
            "status": str(
                preview.get(
                    "status",
                    "PREVIEW_FINISHED",
                )
            ),
            "session_id": session_id,
            "analysis": analysis,
            "plan": plan.to_dict(),
            "guard": guard.to_dict(),
            "preview": preview,
            "progress": self.tracker.status(),
            "writes_code": False,
            "approved": False,
        }

        return self._finish(
            result
        )

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        self.last_result = dict(
            result
        )

        return dict(
            result
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": self.last_result,
            "planner": self.planner.status(),
            "guard": self.guard.status(),
            "progress": self.tracker.status(),
            "orchestrator": self.orchestrator.status(),
        }
