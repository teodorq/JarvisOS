from __future__ import annotations

import uuid
from typing import Any

from app.autodev.autodev_cycle_report import (
    AutoDevCycleReport,
)
from app.autodev.autodev_goal_manager import (
    AutoDevGoalManager,
)
from app.autodev.autodev_history_service import (
    AutoDevHistoryService,
)
from app.autodev.autodev_metrics_service import (
    AutoDevMetricsService,
)
from app.autodev.autodev_runtime_memory import (
    AutoDevRuntimeMemory,
)
from app.autodev.autodev_state_manager import (
    AutoDevStateManager,
)


class AutoDevCycleManager:
    def __init__(
        self,
        runtime_service: Any,
        goal_manager: AutoDevGoalManager | None = None,
        state_manager: AutoDevStateManager | None = None,
        memory: AutoDevRuntimeMemory | None = None,
    ) -> None:
        self.runtime_service = runtime_service
        self.goal_manager = (
            goal_manager
            or AutoDevGoalManager()
        )
        self.state_manager = (
            state_manager
            or AutoDevStateManager()
        )
        self.memory = (
            memory
            or AutoDevRuntimeMemory()
        )
        self.history = AutoDevHistoryService(
            self.memory
        )
        self.metrics = AutoDevMetricsService(
            self.memory
        )
        self.last_result: dict[str, Any] | None = None

    def run_preview_cycle(
        self,
        goal: str,
    ) -> dict[str, Any]:
        goal_result = self.goal_manager.normalize(
            goal
        )

        if not goal_result["success"]:
            return self._finish(
                {
                    "success": False,
                    "status": "EMPTY_GOAL",
                    "writes_code": False,
                    "approved": False,
                }
            )

        cycle_id = str(uuid.uuid4())

        self.state_manager.start(
            cycle_id=cycle_id,
            goal=goal_result["goal"],
        )

        self.state_manager.update(
            step="PREVIEW"
        )

        try:
            preview = self.runtime_service.preview()

            success = bool(
                preview.get(
                    "success",
                    False,
                )
            )

            status = str(
                preview.get(
                    "status",
                    "UNKNOWN",
                )
            )

            self.state_manager.finish(
                status=status
            )

            report = AutoDevCycleReport(
                cycle_id=cycle_id,
                goal=goal_result["goal"],
                success=success,
                status=status,
                writes_code=False,
                approved=False,
            )

            result = {
                "success": success,
                "status": status,
                "cycle_id": cycle_id,
                "goal": goal_result["goal"],
                "preview": preview,
                "report": report.to_dict(),
                "summary": report.summary(),
                "state": self.state_manager.status(),
                "writes_code": False,
                "approved": False,
            }

        except Exception as error:
            error_text = (
                f"{type(error).__name__}: {error}"
            )

            self.state_manager.finish(
                status="FAILED",
                error=error_text,
            )

            result = {
                "success": False,
                "status": "FAILED",
                "cycle_id": cycle_id,
                "goal": goal_result["goal"],
                "error": error_text,
                "state": self.state_manager.status(),
                "writes_code": False,
                "approved": False,
            }

        self.memory.remember(result)

        return self._finish(
            result
        )

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
            "state": self.state_manager.status(),
            "history": self.history.report(),
            "metrics": self.metrics.calculate(),
        }

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.last_result = dict(result)
        return dict(result)
