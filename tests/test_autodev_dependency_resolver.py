import unittest

from app.autodev.autodev_dependency_resolver import (
    AutoDevDependencyResolver,
)


class TestAutoDevDependencyResolver(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = AutoDevDependencyResolver()

    def test_topological_order_is_stable(self) -> None:
        graph = {
            "nodes": [
                {"step_id": "prepare"},
                {"step_id": "tests"},
                {"step_id": "code"},
                {"step_id": "release"},
            ],
            "edges": [
                {"from": "prepare", "to": "code"},
                {"from": "prepare", "to": "tests"},
                {"from": "code", "to": "release"},
                {"from": "tests", "to": "release"},
            ],
        }

        result = self.resolver.resolve(graph)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "DEPENDENCIES_RESOLVED")
        self.assertEqual(
            result["ordered_step_ids"],
            ["prepare", "tests", "code", "release"],
        )

    def test_unknown_edge_endpoint_blocks_plan(self) -> None:
        result = self.resolver.resolve(
            {
                "nodes": [{"step_id": "one"}],
                "edges": [{"from": "one", "to": "missing"}],
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "INVALID_DEPENDENCIES")
        self.assertEqual(result["invalid_edges"][0]["reason"], "UNKNOWN_NODE")
        self.assertEqual(result["ordered_steps"], [])

    def test_cycle_is_detected(self) -> None:
        result = self.resolver.resolve(
            {
                "nodes": [
                    {"step_id": "one"},
                    {"step_id": "two"},
                ],
                "edges": [
                    {"from": "one", "to": "two"},
                    {"from": "two", "to": "one"},
                ],
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "DEPENDENCY_CYCLE_DETECTED",
        )
        self.assertEqual(result["cycle_nodes"], ["one", "two"])

    def test_duplicate_nodes_are_rejected(self) -> None:
        result = self.resolver.resolve(
            {
                "nodes": [
                    {"step_id": "one"},
                    {"step_id": "one"},
                ],
                "edges": [],
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["duplicate_node_ids"], ["one"])

    def test_duplicate_edges_do_not_change_indegree(self) -> None:
        result = self.resolver.resolve(
            {
                "nodes": [
                    {"step_id": "one"},
                    {"step_id": "two"},
                ],
                "edges": [
                    {"from": "one", "to": "two"},
                    {"from": "one", "to": "two"},
                ],
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["ordered_step_ids"], ["one", "two"])
        self.assertEqual(
            result["duplicate_edges"],
            [{"from": "one", "to": "two"}],
        )


if __name__ == "__main__":
    unittest.main()
