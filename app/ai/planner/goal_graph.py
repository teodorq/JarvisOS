from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class GoalGraphNodeStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    BLOCKED = "BLOCKED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GoalGraphEdgeType(str, Enum):
    PARENT_CHILD = "PARENT_CHILD"
    DEPENDENCY = "DEPENDENCY"
    BLOCKER = "BLOCKER"
    SEQUENCE = "SEQUENCE"


@dataclass
class GoalGraphNode:
    node_id: str
    goal_id: str
    title: str
    status: str
    priority: str
    progress: float
    parent_goal_id: str | None
    dependencies: list[str]
    child_goal_ids: list[str]
    blockers: list[str]
    ready: bool
    depth: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalGraphEdge:
    edge_id: str
    source_goal_id: str
    target_goal_id: str
    edge_type: str
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalGraphResult:
    graph_id: str
    root_goal_ids: list[str]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    execution_order: list[str]
    ready_goal_ids: list[str]
    blocked_goal_ids: list[str]
    cycle_paths: list[list[str]]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GoalGraph:

    TERMINAL_STATUSES = {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "ARCHIVED",
    }

    def __init__(
        self,
    ) -> None:

        self._goals: dict[str, dict[str, Any]] = {}
        self._nodes: dict[str, GoalGraphNode] = {}
        self._edges: list[GoalGraphEdge] = []
        self._graph_id = ""

    def build(
        self,
        goals: list[dict[str, Any]],
    ) -> dict[str, Any]:

        self._reset()
        self._graph_id = f"goal_graph_{uuid4().hex}"

        self._goals = self._normalize_goals(
            goals
        )

        self._repair_relations()
        self._build_nodes()
        self._build_edges()

        cycle_paths = self.detect_cycles()

        execution_order = (
            []
            if cycle_paths
            else self.topological_order()
        )

        ready_goal_ids = self.get_ready_goal_ids()
        blocked_goal_ids = self.get_blocked_goal_ids()
        root_goal_ids = self.get_root_goal_ids()

        result = GoalGraphResult(
            graph_id=self._graph_id,
            root_goal_ids=root_goal_ids,
            nodes=[
                node.to_dict()
                for node in self._nodes.values()
            ],
            edges=[
                edge.to_dict()
                for edge in self._edges
            ],
            execution_order=execution_order,
            ready_goal_ids=ready_goal_ids,
            blocked_goal_ids=blocked_goal_ids,
            cycle_paths=cycle_paths,
            metadata={
                "graph_version": "1.0.0",
                "nodes_count": len(self._nodes),
                "edges_count": len(self._edges),
                "roots_count": len(root_goal_ids),
                "ready_count": len(ready_goal_ids),
                "blocked_count": len(blocked_goal_ids),
                "has_cycles": bool(cycle_paths),
            },
        )

        return result.to_dict()

    def create(
        self,
        goals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.build(goals)

    def generate(
        self,
        goals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.build(goals)

    def get_node(
        self,
        goal_id: str,
    ) -> dict[str, Any] | None:

        node = self._nodes.get(
            str(goal_id).strip()
        )

        if node is None:
            return None

        return node.to_dict()

    def get_root_goal_ids(
        self,
    ) -> list[str]:

        roots = [
            goal_id
            for goal_id, goal in self._goals.items()
            if not goal.get("parent_goal_id")
        ]

        return self._sort_goal_ids(
            roots
        )

    def get_children(
        self,
        goal_id: str,
    ) -> list[str]:

        goal = self._goals.get(
            str(goal_id).strip()
        )

        if goal is None:
            return []

        return self._sort_goal_ids(
            goal.get(
                "child_goal_ids",
                [],
            )
        )

    def get_dependencies(
        self,
        goal_id: str,
    ) -> list[str]:

        goal = self._goals.get(
            str(goal_id).strip()
        )

        if goal is None:
            return []

        return self._sort_goal_ids(
            goal.get(
                "dependencies",
                [],
            )
        )

    def get_dependents(
        self,
        goal_id: str,
    ) -> list[str]:

        normalized_goal_id = str(
            goal_id
        ).strip()

        dependents = [
            current_goal_id
            for current_goal_id, goal
            in self._goals.items()
            if normalized_goal_id
            in goal.get(
                "dependencies",
                [],
            )
        ]

        return self._sort_goal_ids(
            dependents
        )

    def get_ancestors(
        self,
        goal_id: str,
    ) -> list[str]:

        normalized_goal_id = str(
            goal_id
        ).strip()

        ancestors: list[str] = []
        visited: set[str] = set()
        current_id = normalized_goal_id

        while current_id in self._goals:
            parent_id = self._goals[
                current_id
            ].get(
                "parent_goal_id"
            )

            if (
                not parent_id
                or parent_id in visited
            ):
                break

            visited.add(parent_id)
            ancestors.append(parent_id)
            current_id = parent_id

        return ancestors

    def get_descendants(
        self,
        goal_id: str,
    ) -> list[str]:

        normalized_goal_id = str(
            goal_id
        ).strip()

        if normalized_goal_id not in self._goals:
            return []

        descendants: list[str] = []
        stack = list(
            reversed(
                self.get_children(
                    normalized_goal_id
                )
            )
        )
        visited: set[str] = set()

        while stack:
            current_id = stack.pop()

            if current_id in visited:
                continue

            visited.add(current_id)
            descendants.append(current_id)

            children = self.get_children(
                current_id
            )

            stack.extend(
                reversed(children)
            )

        return descendants

    def get_ready_goal_ids(
        self,
    ) -> list[str]:

        ready = [
            goal_id
            for goal_id in self._goals
            if self.is_ready(goal_id)
        ]

        return self._sort_goal_ids(
            ready
        )

    def get_blocked_goal_ids(
        self,
    ) -> list[str]:

        blocked = []

        for goal_id, goal in self._goals.items():
            status = str(
                goal.get(
                    "status",
                    "CREATED",
                )
            ).upper()

            if status in self.TERMINAL_STATUSES:
                continue

            if (
                goal.get("blockers")
                or not self._dependencies_completed(
                    goal_id
                )
            ):
                blocked.append(goal_id)

        return self._sort_goal_ids(
            blocked
        )

    def is_ready(
        self,
        goal_id: str,
    ) -> bool:

        goal = self._goals.get(
            str(goal_id).strip()
        )

        if goal is None:
            return False

        status = str(
            goal.get(
                "status",
                "CREATED",
            )
        ).upper()

        if status in self.TERMINAL_STATUSES:
            return False

        if goal.get("blockers"):
            return False

        return self._dependencies_completed(
            goal["goal_id"]
        )

    def topological_order(
        self,
    ) -> list[str]:

        indegree = {
            goal_id: 0
            for goal_id in self._goals
        }

        adjacency = {
            goal_id: []
            for goal_id in self._goals
        }

        for goal_id, goal in self._goals.items():
            for dependency_id in goal.get(
                "dependencies",
                [],
            ):
                if dependency_id not in self._goals:
                    continue

                adjacency[dependency_id].append(
                    goal_id
                )
                indegree[goal_id] += 1

        queue = self._sort_goal_ids(
            [
                goal_id
                for goal_id, degree
                in indegree.items()
                if degree == 0
            ]
        )

        order: list[str] = []

        while queue:
            current_id = queue.pop(0)
            order.append(current_id)

            for dependent_id in self._sort_goal_ids(
                adjacency[current_id]
            ):
                indegree[dependent_id] -= 1

                if indegree[dependent_id] == 0:
                    queue.append(dependent_id)
                    queue = self._sort_goal_ids(
                        queue
                    )

        if len(order) != len(self._goals):
            return []

        return order

    def detect_cycles(
        self,
    ) -> list[list[str]]:

        cycles: list[list[str]] = []
        state: dict[str, int] = {
            goal_id: 0
            for goal_id in self._goals
        }
        path: list[str] = []
        path_index: dict[str, int] = {}

        def visit(
            goal_id: str,
        ) -> None:

            state[goal_id] = 1
            path_index[goal_id] = len(path)
            path.append(goal_id)

            dependencies = self._goals[
                goal_id
            ].get(
                "dependencies",
                [],
            )

            for dependency_id in dependencies:
                if dependency_id not in self._goals:
                    continue

                if state[dependency_id] == 0:
                    visit(dependency_id)

                elif state[dependency_id] == 1:
                    start_index = path_index[
                        dependency_id
                    ]

                    cycle = (
                        path[start_index:]
                        + [dependency_id]
                    )

                    normalized_cycle = (
                        self._normalize_cycle(
                            cycle
                        )
                    )

                    if normalized_cycle not in cycles:
                        cycles.append(
                            normalized_cycle
                        )

            path.pop()
            path_index.pop(
                goal_id,
                None,
            )
            state[goal_id] = 2

        for goal_id in self._sort_goal_ids(
            list(self._goals)
        ):
            if state[goal_id] == 0:
                visit(goal_id)

        return cycles

    def critical_path(
        self,
    ) -> list[str]:

        if self.detect_cycles():
            return []

        order = self.topological_order()

        if not order:
            return []

        distance = {
            goal_id: 0.0
            for goal_id in self._goals
        }

        predecessor: dict[
            str,
            str | None,
        ] = {
            goal_id: None
            for goal_id in self._goals
        }

        for goal_id in order:
            effort = self._goal_effort(
                goal_id
            )

            dependencies = self.get_dependencies(
                goal_id
            )

            if not dependencies:
                distance[goal_id] = effort
                continue

            best_dependency = max(
                dependencies,
                key=lambda dependency_id: (
                    distance[dependency_id]
                ),
            )

            distance[goal_id] = (
                distance[best_dependency]
                + effort
            )
            predecessor[goal_id] = (
                best_dependency
            )

        end_goal_id = max(
            order,
            key=lambda goal_id: (
                distance[goal_id]
            ),
        )

        path: list[str] = []
        current_id: str | None = end_goal_id

        while current_id is not None:
            path.append(current_id)
            current_id = predecessor[
                current_id
            ]

        path.reverse()
        return path

    def execution_layers(
        self,
    ) -> list[list[str]]:

        if self.detect_cycles():
            return []

        remaining = set(
            self._goals.keys()
        )
        completed: set[str] = set()
        layers: list[list[str]] = []

        while remaining:
            layer = [
                goal_id
                for goal_id in remaining
                if set(
                    self.get_dependencies(
                        goal_id
                    )
                ).issubset(completed)
            ]

            if not layer:
                return []

            layer = self._sort_goal_ids(
                layer
            )

            layers.append(layer)
            completed.update(layer)
            remaining.difference_update(layer)

        return layers

    def subgraph(
        self,
        root_goal_id: str,
    ) -> dict[str, Any]:

        normalized_root_id = str(
            root_goal_id
        ).strip()

        if normalized_root_id not in self._goals:
            return self._empty_graph_result()

        selected_ids = {
            normalized_root_id,
            *self.get_descendants(
                normalized_root_id
            ),
        }

        selected_goals = [
            self._goals[goal_id]
            for goal_id in selected_ids
        ]

        return GoalGraph().build(
            selected_goals
        )

    def validate(
        self,
    ) -> dict[str, Any]:

        errors: list[str] = []
        warnings: list[str] = []

        cycles = self.detect_cycles()

        if cycles:
            errors.append(
                "Wykryto cykle zależności."
            )

        for goal_id, goal in self._goals.items():
            parent_id = goal.get(
                "parent_goal_id"
            )

            if (
                parent_id
                and parent_id not in self._goals
            ):
                errors.append(
                    f"Brak celu nadrzędnego "
                    f"{parent_id} dla {goal_id}."
                )

            for dependency_id in goal.get(
                "dependencies",
                [],
            ):
                if dependency_id not in self._goals:
                    errors.append(
                        f"Brak zależności "
                        f"{dependency_id} dla {goal_id}."
                    )

                if dependency_id == goal_id:
                    errors.append(
                        f"Cel {goal_id} zależy "
                        "od samego siebie."
                    )

            if goal.get("blockers"):
                warnings.append(
                    f"Cel {goal_id} ma aktywne blokery."
                )

        return {
            "valid": not errors,
            "errors": self._unique_strings(
                errors
            ),
            "warnings": self._unique_strings(
                warnings
            ),
            "cycle_paths": cycles,
            "graph_id": self._graph_id,
        }

    def _build_nodes(
        self,
    ) -> None:

        for goal_id, goal in self._goals.items():
            depth = len(
                self.get_ancestors(
                    goal_id
                )
            )

            ready = self.is_ready(
                goal_id
            )

            node_status = self._node_status(
                goal,
                ready,
            )

            self._nodes[goal_id] = GoalGraphNode(
                node_id=f"goal_node_{uuid4().hex}",
                goal_id=goal_id,
                title=str(
                    goal.get(
                        "title",
                        "",
                    )
                ),
                status=node_status,
                priority=str(
                    goal.get(
                        "priority",
                        "MEDIUM",
                    )
                ).upper(),
                progress=self._safe_float(
                    goal.get(
                        "progress",
                        0.0,
                    ),
                    0.0,
                ),
                parent_goal_id=goal.get(
                    "parent_goal_id"
                ),
                dependencies=list(
                    goal.get(
                        "dependencies",
                        [],
                    )
                ),
                child_goal_ids=list(
                    goal.get(
                        "child_goal_ids",
                        [],
                    )
                ),
                blockers=list(
                    goal.get(
                        "blockers",
                        [],
                    )
                ),
                ready=ready,
                depth=depth,
                metadata={
                    "goal_type": goal.get(
                        "goal_type",
                        "UNKNOWN",
                    ),
                    "timeframe": goal.get(
                        "timeframe",
                        "MEDIUM_TERM",
                    ),
                    "deadline": goal.get(
                        "deadline"
                    ),
                    "estimated_effort": (
                        goal.get(
                            "estimated_effort"
                        )
                    ),
                },
            )

    def _build_edges(
        self,
    ) -> None:

        for goal_id, goal in self._goals.items():
            parent_id = goal.get(
                "parent_goal_id"
            )

            if (
                parent_id
                and parent_id in self._goals
            ):
                self._edges.append(
                    GoalGraphEdge(
                        edge_id=(
                            f"goal_edge_"
                            f"{uuid4().hex}"
                        ),
                        source_goal_id=parent_id,
                        target_goal_id=goal_id,
                        edge_type=(
                            GoalGraphEdgeType
                            .PARENT_CHILD
                            .value
                        ),
                        label="cel podrzędny",
                    )
                )

            for dependency_id in goal.get(
                "dependencies",
                [],
            ):
                if dependency_id not in self._goals:
                    continue

                self._edges.append(
                    GoalGraphEdge(
                        edge_id=(
                            f"goal_edge_"
                            f"{uuid4().hex}"
                        ),
                        source_goal_id=dependency_id,
                        target_goal_id=goal_id,
                        edge_type=(
                            GoalGraphEdgeType
                            .DEPENDENCY
                            .value
                        ),
                        label="zależność",
                    )
                )

    def _dependencies_completed(
        self,
        goal_id: str,
    ) -> bool:

        goal = self._goals.get(
            goal_id
        )

        if goal is None:
            return False

        for dependency_id in goal.get(
            "dependencies",
            [],
        ):
            dependency = self._goals.get(
                dependency_id
            )

            if dependency is None:
                return False

            if str(
                dependency.get(
                    "status",
                    "",
                )
            ).upper() != "COMPLETED":
                return False

        return True

    def _node_status(
        self,
        goal: dict[str, Any],
        ready: bool,
    ) -> str:

        status = str(
            goal.get(
                "status",
                "CREATED",
            )
        ).upper()

        mapping = {
            "ACTIVE": GoalGraphNodeStatus.ACTIVE.value,
            "COMPLETED": GoalGraphNodeStatus.COMPLETED.value,
            "FAILED": GoalGraphNodeStatus.FAILED.value,
            "CANCELLED": GoalGraphNodeStatus.CANCELLED.value,
        }

        if status in mapping:
            return mapping[status]

        if ready:
            return GoalGraphNodeStatus.READY.value

        if (
            goal.get("blockers")
            or not self._dependencies_completed(
                goal["goal_id"]
            )
        ):
            return GoalGraphNodeStatus.BLOCKED.value

        return GoalGraphNodeStatus.PENDING.value

    def _normalize_goals(
        self,
        goals: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:

        if not isinstance(goals, list):
            raise TypeError(
                "GoalGraph wymaga listy celów."
            )

        normalized: dict[
            str,
            dict[str, Any],
        ] = {}

        for raw_goal in goals:
            if not isinstance(
                raw_goal,
                dict,
            ):
                continue

            goal_id = str(
                raw_goal.get(
                    "goal_id",
                    "",
                )
            ).strip()

            if not goal_id:
                continue

            normalized[goal_id] = {
                "goal_id": goal_id,
                "title": str(
                    raw_goal.get(
                        "title",
                        goal_id,
                    )
                ),
                "description": str(
                    raw_goal.get(
                        "description",
                        "",
                    )
                ),
                "goal_type": str(
                    raw_goal.get(
                        "goal_type",
                        "UNKNOWN",
                    )
                ).upper(),
                "priority": str(
                    raw_goal.get(
                        "priority",
                        "MEDIUM",
                    )
                ).upper(),
                "timeframe": str(
                    raw_goal.get(
                        "timeframe",
                        "MEDIUM_TERM",
                    )
                ).upper(),
                "status": str(
                    raw_goal.get(
                        "status",
                        "CREATED",
                    )
                ).upper(),
                "progress": max(
                    0.0,
                    min(
                        1.0,
                        self._safe_float(
                            raw_goal.get(
                                "progress",
                                0.0,
                            ),
                            0.0,
                        ),
                    ),
                ),
                "parent_goal_id": self._optional_string(
                    raw_goal.get(
                        "parent_goal_id"
                    )
                ),
                "child_goal_ids": self._normalize_ids(
                    raw_goal.get(
                        "child_goal_ids",
                        [],
                    )
                ),
                "dependencies": self._normalize_ids(
                    raw_goal.get(
                        "dependencies",
                        [],
                    )
                ),
                "blockers": self._unique_strings(
                    raw_goal.get(
                        "blockers",
                        [],
                    )
                ),
                "deadline": self._optional_string(
                    raw_goal.get(
                        "deadline"
                    )
                ),
                "estimated_effort": (
                    self._optional_float(
                        raw_goal.get(
                            "estimated_effort"
                        )
                    )
                ),
                "metadata": (
                    dict(
                        raw_goal.get(
                            "metadata",
                            {},
                        )
                    )
                    if isinstance(
                        raw_goal.get(
                            "metadata"
                        ),
                        dict,
                    )
                    else {}
                ),
            }

        return normalized

    def _repair_relations(
        self,
    ) -> None:

        for goal in self._goals.values():
            parent_id = goal.get(
                "parent_goal_id"
            )

            if parent_id not in self._goals:
                goal["parent_goal_id"] = None

            goal["child_goal_ids"] = [
                child_id
                for child_id in goal.get(
                    "child_goal_ids",
                    [],
                )
                if (
                    child_id in self._goals
                    and child_id
                    != goal["goal_id"]
                )
            ]

            goal["dependencies"] = [
                dependency_id
                for dependency_id in goal.get(
                    "dependencies",
                    [],
                )
                if (
                    dependency_id in self._goals
                    and dependency_id
                    != goal["goal_id"]
                )
            ]

        for goal_id, goal in self._goals.items():
            parent_id = goal.get(
                "parent_goal_id"
            )

            if parent_id:
                parent = self._goals[
                    parent_id
                ]

                if goal_id not in parent[
                    "child_goal_ids"
                ]:
                    parent[
                        "child_goal_ids"
                    ].append(goal_id)

    def _sort_goal_ids(
        self,
        goal_ids: list[str],
    ) -> list[str]:

        priority_order = {
            "CRITICAL": 0,
            "HIGH": 1,
            "MEDIUM": 2,
            "LOW": 3,
        }

        status_order = {
            "ACTIVE": 0,
            "PLANNED": 1,
            "CREATED": 2,
            "PAUSED": 3,
            "BLOCKED": 4,
            "FAILED": 5,
            "CANCELLED": 6,
            "COMPLETED": 7,
            "ARCHIVED": 8,
        }

        return sorted(
            [
                goal_id
                for goal_id in goal_ids
                if goal_id in self._goals
            ],
            key=lambda goal_id: (
                priority_order.get(
                    self._goals[
                        goal_id
                    ].get(
                        "priority",
                        "MEDIUM",
                    ),
                    99,
                ),
                status_order.get(
                    self._goals[
                        goal_id
                    ].get(
                        "status",
                        "CREATED",
                    ),
                    99,
                ),
                goal_id,
            ),
        )

    def _goal_effort(
        self,
        goal_id: str,
    ) -> float:

        goal = self._goals[
            goal_id
        ]

        effort = self._optional_float(
            goal.get(
                "estimated_effort"
            )
        )

        if effort is None or effort <= 0:
            return 1.0

        return effort

    def _normalize_cycle(
        self,
        cycle: list[str],
    ) -> list[str]:

        if len(cycle) <= 1:
            return cycle

        body = cycle[:-1]

        if not body:
            return cycle

        rotations = [
            body[index:]
            + body[:index]
            for index in range(
                len(body)
            )
        ]

        normalized_body = min(
            rotations
        )

        return (
            normalized_body
            + [normalized_body[0]]
        )

    def _empty_graph_result(
        self,
    ) -> dict[str, Any]:

        return GoalGraphResult(
            graph_id=f"goal_graph_{uuid4().hex}",
            root_goal_ids=[],
            nodes=[],
            edges=[],
            execution_order=[],
            ready_goal_ids=[],
            blocked_goal_ids=[],
            cycle_paths=[],
            metadata={
                "graph_version": "1.0.0",
                "nodes_count": 0,
                "edges_count": 0,
                "roots_count": 0,
                "ready_count": 0,
                "blocked_count": 0,
                "has_cycles": False,
            },
        ).to_dict()

    def _normalize_ids(
        self,
        value: Any,
    ) -> list[str]:

        if not isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            return []

        return self._unique_strings(
            [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]
        )

    def _unique_strings(
        self,
        value: Any,
    ) -> list[str]:

        if not isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            return []

        result: list[str] = []
        seen: set[str] = set()

        for item in value:
            text = str(item).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(text)

        return result

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return normalized or None

    def _optional_float(
        self,
        value: Any,
    ) -> float | None:

        if value is None:
            return None

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

    def _safe_float(
        self,
        value: Any,
        default: float,
    ) -> float:

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return default

    def _reset(
        self,
    ) -> None:

        self._goals = {}
        self._nodes = {}
        self._edges = []
        self._graph_id = ""
