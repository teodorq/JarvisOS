from __future__ import annotations

from collections import deque
from typing import Any


class AutoDevDependencyResolver:
    """Validate an execution graph and return a deterministic order.

    The resolver does not mutate the supplied graph.  It validates node IDs,
    rejects broken edges and cycles, and performs a stable topological sort.
    Nodes that are independent keep their original input order.
    """

    def resolve(
        self,
        graph: dict[str, Any],
    ) -> dict[str, Any]:
        raw_nodes = list(graph.get("nodes", []) or [])
        raw_edges = list(graph.get("edges", []) or [])

        nodes: list[dict[str, Any]] = []
        node_by_id: dict[str, dict[str, Any]] = {}
        node_order: dict[str, int] = {}
        duplicate_node_ids: list[str] = []
        invalid_nodes: list[dict[str, Any]] = []

        for index, raw_node in enumerate(raw_nodes):
            if not isinstance(raw_node, dict):
                invalid_nodes.append(
                    {
                        "index": index,
                        "reason": "NODE_NOT_A_DICTIONARY",
                    }
                )
                continue

            step_id = str(raw_node.get("step_id", "")).strip()
            if not step_id:
                invalid_nodes.append(
                    {
                        "index": index,
                        "reason": "MISSING_STEP_ID",
                    }
                )
                continue

            if step_id in node_by_id:
                if step_id not in duplicate_node_ids:
                    duplicate_node_ids.append(step_id)
                continue

            node = dict(raw_node)
            node["step_id"] = step_id
            nodes.append(node)
            node_by_id[step_id] = node
            node_order[step_id] = index

        adjacency: dict[str, set[str]] = {
            step_id: set()
            for step_id in node_by_id
        }
        indegree: dict[str, int] = {
            step_id: 0
            for step_id in node_by_id
        }
        invalid_edges: list[dict[str, str]] = []
        duplicate_edges: list[dict[str, str]] = []
        seen_edges: set[tuple[str, str]] = set()

        for raw_edge in raw_edges:
            if not isinstance(raw_edge, dict):
                invalid_edges.append(
                    {
                        "from": "",
                        "to": "",
                        "reason": "EDGE_NOT_A_DICTIONARY",
                    }
                )
                continue

            source = str(raw_edge.get("from", "")).strip()
            target = str(raw_edge.get("to", "")).strip()

            if not source or not target:
                invalid_edges.append(
                    {
                        "from": source,
                        "to": target,
                        "reason": "MISSING_ENDPOINT",
                    }
                )
                continue

            if source not in node_by_id or target not in node_by_id:
                invalid_edges.append(
                    {
                        "from": source,
                        "to": target,
                        "reason": "UNKNOWN_NODE",
                    }
                )
                continue

            edge_key = (source, target)
            if edge_key in seen_edges:
                duplicate_edges.append(
                    {
                        "from": source,
                        "to": target,
                    }
                )
                continue

            seen_edges.add(edge_key)
            adjacency[source].add(target)
            indegree[target] += 1

        structural_errors = bool(
            invalid_nodes
            or duplicate_node_ids
            or invalid_edges
        )

        ordered_ids: list[str] = []
        cycle_nodes: list[str] = []

        if not structural_errors:
            ready = deque(
                sorted(
                    (
                        step_id
                        for step_id, degree in indegree.items()
                        if degree == 0
                    ),
                    key=node_order.__getitem__,
                )
            )

            while ready:
                step_id = ready.popleft()
                ordered_ids.append(step_id)

                newly_ready: list[str] = []
                for target in sorted(
                    adjacency[step_id],
                    key=node_order.__getitem__,
                ):
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        newly_ready.append(target)

                if newly_ready:
                    merged = list(ready) + newly_ready
                    merged.sort(key=node_order.__getitem__)
                    ready = deque(merged)

            if len(ordered_ids) != len(nodes):
                cycle_nodes = sorted(
                    (
                        step_id
                        for step_id, degree in indegree.items()
                        if degree > 0
                    ),
                    key=node_order.__getitem__,
                )

        success = not structural_errors and not cycle_nodes

        if success:
            status = "DEPENDENCIES_RESOLVED"
        elif cycle_nodes:
            status = "DEPENDENCY_CYCLE_DETECTED"
        else:
            status = "INVALID_DEPENDENCIES"

        ordered_steps = [
            dict(node_by_id[step_id])
            for step_id in ordered_ids
        ]

        return {
            "success": success,
            "status": status,
            "invalid_nodes": invalid_nodes,
            "duplicate_node_ids": duplicate_node_ids,
            "invalid_edges": invalid_edges,
            "duplicate_edges": duplicate_edges,
            "cycle_nodes": cycle_nodes,
            "ordered_step_ids": ordered_ids,
            "ordered_steps": ordered_steps,
        }
