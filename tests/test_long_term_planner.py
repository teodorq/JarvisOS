from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.ai.planner.execution_tracker import (
    ExecutionTracker,
)
from app.ai.planner.goal_decomposer import (
    GoalDecomposer,
)
from app.ai.planner.goal_graph import GoalGraph
from app.ai.planner.goal_manager import GoalManager
from app.ai.planner.goal_scheduler import (
    GoalScheduler,
)
from app.ai.planner.long_term_planner import (
    LongTermPlanner,
)
from app.ai.planner.planning_controller import (
    PlanningController,
)
from app.ai.planner.planning_memory import (
    PlanningMemory,
)
from app.ai.planner.planning_session import (
    PlanningSession,
)
from app.ai.planner.priority_manager import (
    PriorityManager,
)


class LongTermPlannerTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        root = Path(
            self.temp_directory.name
        )

        self.goal_manager = GoalManager(
            storage_path=root / "goals.json"
        )

        self.execution_tracker = ExecutionTracker(
            storage_path=root / "executions.json"
        )

        self.planning_memory = PlanningMemory(
            storage_path=root / "planning_memory.json"
        )

        self.planner = LongTermPlanner(
            goal_manager=self.goal_manager,
            goal_graph=GoalGraph(),
            goal_decomposer=GoalDecomposer(),
            priority_manager=PriorityManager(),
            goal_scheduler=GoalScheduler(),
            execution_tracker=(
                self.execution_tracker
            ),
            planning_memory=self.planning_memory,
        )

        self.controller = PlanningController(
            planner=self.planner
        )

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_goal_manager_creates_goal(
        self,
    ) -> None:
        goal = self.goal_manager.create_goal(
            title="Zbudować Jarvis Core 3.0",
            description=(
                "Rozwinąć nowy rdzeń systemu."
            ),
            goal_type="PROJECT",
            priority="HIGH",
            timeframe="LONG_TERM",
        )

        self.assertTrue(
            goal["goal_id"].startswith(
                "goal_"
            )
        )

        self.assertEqual(
            goal["status"],
            "CREATED",
        )

        self.assertEqual(
            goal["priority"],
            "HIGH",
        )

    def test_goal_decomposer_creates_subgoals(
        self,
    ) -> None:
        decomposer = GoalDecomposer()

        goal = {
            "goal_id": "goal_test",
            "title": "Zbudować Jarvis Core 3.0",
            "description": (
                "Zbudować nową architekturę systemu."
            ),
            "goal_type": "PROJECT",
            "priority": "HIGH",
            "timeframe": "LONG_TERM",
            "success_criteria": [
                "System działa poprawnie."
            ],
            "tags": [
                "jarvis"
            ],
        }

        result = decomposer.decompose(
            goal=goal,
            context={
                "dependency_count": 4,
                "affected_modules": 6,
            },
        )

        self.assertTrue(
            result["decomposition_id"].startswith(
                "goal_decomposition_"
            )
        )

        self.assertGreater(
            len(result["subgoals"]),
            3,
        )

        self.assertGreater(
            result["estimated_total_effort"],
            0,
        )

    def test_goal_graph_orders_dependencies(
        self,
    ) -> None:
        first = self.goal_manager.create_goal(
            title="Analiza",
            priority="HIGH",
        )

        second = self.goal_manager.create_goal(
            title="Implementacja",
            priority="HIGH",
            dependencies=[
                first["goal_id"]
            ],
        )

        graph = GoalGraph().build(
            [
                first,
                second,
            ]
        )

        self.assertFalse(
            graph["metadata"]["has_cycles"]
        )

        self.assertEqual(
            graph["execution_order"][0],
            first["goal_id"],
        )

        self.assertEqual(
            graph["execution_order"][1],
            second["goal_id"],
        )

    def test_priority_manager_selects_ready_goal(
        self,
    ) -> None:
        low_goal = self.goal_manager.create_goal(
            title="Cel niski",
            priority="LOW",
        )

        high_goal = self.goal_manager.create_goal(
            title="Cel wysoki",
            priority="HIGH",
        )

        result = PriorityManager().evaluate(
            goals=[
                low_goal,
                high_goal,
            ]
        )

        self.assertEqual(
            result["next_goal_id"],
            high_goal["goal_id"],
        )

        self.assertEqual(
            result["ordered_goal_ids"][0],
            high_goal["goal_id"],
        )

    def test_goal_scheduler_selects_next_goal(
        self,
    ) -> None:
        first = self.goal_manager.create_goal(
            title="Pierwszy cel",
            priority="HIGH",
            estimated_effort=2,
        )

        second = self.goal_manager.create_goal(
            title="Drugi cel",
            priority="MEDIUM",
            estimated_effort=2,
            dependencies=[
                first["goal_id"]
            ],
        )

        goals = [
            first,
            second,
        ]

        graph = GoalGraph().build(
            goals
        )

        priority = PriorityManager().evaluate(
            goals=goals
        )

        schedule = GoalScheduler().schedule(
            goals=goals,
            priority_result=priority,
            graph_result=graph,
        )

        self.assertEqual(
            schedule["next_goal_id"],
            first["goal_id"],
        )

        self.assertIn(
            second["goal_id"],
            schedule["blocked_goal_ids"],
        )

    def test_execution_tracker_tracks_progress(
        self,
    ) -> None:
        execution = self.execution_tracker.create(
            goal_id="goal_test",
            title="Test wykonania",
            estimated_effort=4,
        )

        execution = self.execution_tracker.start(
            execution["execution_id"]
        )

        self.assertEqual(
            execution["status"],
            "RUNNING",
        )

        execution = (
            self.execution_tracker.update_progress(
                execution_id=execution[
                    "execution_id"
                ],
                progress=0.5,
                current_step="Implementacja",
                actual_effort_delta=2,
            )
        )

        self.assertEqual(
            execution["progress"],
            0.5,
        )

        execution = self.execution_tracker.complete(
            execution["execution_id"],
            result={
                "success": True
            },
        )

        self.assertEqual(
            execution["status"],
            "COMPLETED",
        )

        self.assertEqual(
            execution["progress"],
            1.0,
        )

    def test_planning_session_tracks_steps(
        self,
    ) -> None:
        session = PlanningSession(
            root_goal_id="goal_root",
            title="Test planowania",
        )

        first = session.add_step(
            goal_id="goal_first",
            name="Analiza",
            order=1,
        )

        second = session.add_step(
            goal_id="goal_second",
            name="Implementacja",
            order=2,
            dependencies=[
                "goal_first"
            ],
        )

        session.start()

        session.complete_step(
            first["step_id"],
            output={
                "success": True
            },
        )

        next_step = session.next_ready_step()

        self.assertIsNotNone(
            next_step
        )

        self.assertEqual(
            next_step["goal_id"],
            second["goal_id"],
        )

    def test_long_term_planner_creates_plan(
        self,
    ) -> None:
        result = self.planner.create_plan(
            title="Zbudować Jarvis Core 3.0",
            description=(
                "Stworzyć nowy rdzeń systemu Jarvis."
            ),
            goal_type="PROJECT",
            priority="HIGH",
            timeframe="LONG_TERM",
            success_criteria=[
                "Wszystkie testy przechodzą."
            ],
            context={
                "dependency_count": 3,
                "affected_modules": 5,
            },
        )

        self.assertTrue(
            result["success"]
        )

        self.assertTrue(
            result["session_id"].startswith(
                "planning_session_"
            )
        )

        self.assertGreater(
            len(result["subgoals"]),
            3,
        )

        self.assertIsNotNone(
            result["next_goal_id"]
        )

    def test_planning_controller_creates_plan(
        self,
    ) -> None:
        result = self.controller.create_plan(
            title="Rozwinąć JARVIS OS",
            description=(
                "Zaplanować dalszy rozwój systemu."
            ),
            priority="HIGH",
            timeframe="LONG_TERM",
        )

        self.assertTrue(
            result["success"]
        )

        self.assertIn(
            "schedule",
            result,
        )

        self.assertIn(
            "graph",
            result,
        )

        self.assertIn(
            "priority_result",
            result,
        )

    def test_planning_memory_records_session(
        self,
    ) -> None:
        session = {
            "session_id": "planning_session_test",
            "status": "COMPLETED",
            "progress": 1.0,
            "goal": {
                "goal_id": "goal_test",
                "title": "Test pamięci",
            },
            "plan": {
                "plan_id": "plan_test",
            },
            "schedule": {
                "next_goal_id": None,
            },
            "completed_goal_ids": [
                "goal_test"
            ],
            "lessons": [
                "Plan działa poprawnie."
            ],
        }

        self.planning_memory.remember(
            session=session,
            result={
                "success": True,
                "status": "COMPLETED",
            },
        )

        summary = self.planning_memory.summary()

        self.assertEqual(
            summary["entries_count"],
            1,
        )

        self.assertEqual(
            summary["completed_plans"],
            1,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )