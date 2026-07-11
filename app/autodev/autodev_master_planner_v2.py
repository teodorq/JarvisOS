from __future__ import annotations

from typing import Any

from app.autodev.autodev_cycle_optimizer_v2 import (
    AutoDevCycleOptimizerV2,
)
from app.autodev.autodev_history_analyzer_v2 import (
    AutoDevHistoryAnalyzerV2,
)
from app.autodev.autodev_priority_scheduler_v2 import (
    AutoDevPrioritySchedulerV2,
)
from app.autodev.autodev_task_ranker_v2 import (
    AutoDevTaskRankerV2,
)


class AutoDevMasterPlannerV2:
    def __init__(self) -> None:
        self.ranker = AutoDevTaskRankerV2()
        self.history = AutoDevHistoryAnalyzerV2()
        self.optimizer = AutoDevCycleOptimizerV2()
        self.scheduler = AutoDevPrioritySchedulerV2()
        self.last_result: dict[str, Any] | None = None

    def plan(
        self,
        *,
        goals: list[dict[str, Any]],
        history_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ranking = self.ranker.rank(goals)
        history = self.history.analyze(
            history_records
        )
        optimized = self.optimizer.optimize(
            ranking=ranking,
            history=history,
        )
        schedule = self.scheduler.build_schedule(
            ranking.get(
                "ranked",
                [],
            )
        )

        result = {
            "success": True,
            "status": "MASTER_PLAN_READY",
            "ranking": ranking,
            "history": history,
            "optimized": optimized,
            "schedule": schedule,
            "writes_code": False,
            "approved": False,
        }

        self.last_result = dict(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
        }
