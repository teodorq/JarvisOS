from __future__ import annotations

from typing import Any


class AutoDevExecutionGraph:
    def build(
        self,
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []

        previous_id = ""

        for step in steps:
            if not isinstance(step, dict):
                continue

            step_id = str(
                step.get(
                    "step_id",
                    "",
                )
            ).strip()

            if not step_id:
                continue

            nodes.append(dict(step))

            if previous_id:
                edges.append(
                    {
                        "from": previous_id,
                        "to": step_id,
                    }
                )

            previous_id = step_id

        return {
            "success": True,
            "status": "EXECUTION_GRAPH_READY",
            "nodes": nodes,
            "edges": edges,
        }
