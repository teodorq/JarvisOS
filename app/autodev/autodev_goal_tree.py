from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AutoDevGoalNode:
    node_id: str
    goal: str
    parent_id: str = ""
    order: int = 0
    status: str = "PENDING"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutoDevGoalTree:
    def __init__(self) -> None:
        self.nodes: list[AutoDevGoalNode] = []

    def build(
        self,
        *,
        root_goal: str,
        steps: list[str],
    ) -> dict[str, Any]:
        normalized_goal = str(root_goal).strip()

        if not normalized_goal:
            return {
                "success": False,
                "status": "EMPTY_GOAL",
                "nodes": [],
            }

        self.nodes = [
            AutoDevGoalNode(
                node_id="root",
                goal=normalized_goal,
                order=0,
            )
        ]

        for index, step in enumerate(steps, start=1):
            normalized_step = str(step).strip()

            if not normalized_step:
                continue

            self.nodes.append(
                AutoDevGoalNode(
                    node_id=f"step-{index}",
                    goal=normalized_step,
                    parent_id="root",
                    order=index,
                )
            )

        return {
            "success": True,
            "status": "GOAL_TREE_READY",
            "nodes": [
                node.to_dict()
                for node in self.nodes
            ],
        }

    def status(self) -> dict[str, Any]:
        return {
            "count": len(self.nodes),
            "nodes": [
                node.to_dict()
                for node in self.nodes
            ],
        }
