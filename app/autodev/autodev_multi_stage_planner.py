from __future__ import annotations

from typing import Any

from app.autodev.autodev_dependency_resolver import (
    AutoDevDependencyResolver,
)
from app.autodev.autodev_execution_graph import (
    AutoDevExecutionGraph,
)
from app.autodev.autodev_goal_tree import (
    AutoDevGoalTree,
)
from app.autodev.autodev_step_validator import (
    AutoDevStepValidator,
)
from app.autodev.autodev_task_decomposer import (
    AutoDevTaskDecomposer,
)


class AutoDevMultiStagePlanner:
    def __init__(self) -> None:
        self.decomposer = AutoDevTaskDecomposer()
        self.goal_tree = AutoDevGoalTree()
        self.graph = AutoDevExecutionGraph()
        self.resolver = AutoDevDependencyResolver()
        self.validator = AutoDevStepValidator()
        self.last_result: dict[str, Any] | None = None

    def plan(
        self,
        goal: str,
    ) -> dict[str, Any]:
        decomposition = self.decomposer.decompose(goal)

        if not decomposition.get("success", False):
            return self._finish(
                {
                    "success": False,
                    "status": "DECOMPOSITION_FAILED",
                    "decomposition": decomposition,
                }
            )

        steps = list(
            decomposition.get(
                "steps",
                [],
            )
        )

        validations = [
            self.validator.validate(step)
            for step in steps
        ]

        if not all(
            item.get("success", False)
            for item in validations
        ):
            return self._finish(
                {
                    "success": False,
                    "status": "STEP_VALIDATION_FAILED",
                    "validations": validations,
                }
            )

        tree = self.goal_tree.build(
            root_goal=goal,
            steps=[
                str(step.get("title", ""))
                for step in steps
            ],
        )

        graph = self.graph.build(steps)
        resolution = self.resolver.resolve(graph)

        result = {
            "success": bool(
                resolution.get(
                    "success",
                    False,
                )
            ),
            "status": (
                "MULTI_STAGE_PLAN_READY"
                if resolution.get(
                    "success",
                    False,
                )
                else "MULTI_STAGE_PLAN_BLOCKED"
            ),
            "goal": str(goal).strip(),
            "decomposition": decomposition,
            "tree": tree,
            "graph": graph,
            "resolution": resolution,
            "validations": validations,
            "approved": False,
            "writes_code": False,
        }

        return self._finish(result)

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.last_result = dict(result)
        return dict(result)

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
        }
