import unittest
from unittest.mock import MagicMock

from app.ai.executive_ai.executive_controller import (
    ExecutiveController,
)
from app.ai.executive_ai.executive_engine import (
    ExecutiveEngine,
)
from app.ai.executive_ai.executive_memory import (
    ExecutiveMemory,
)
from app.ai.executive_ai.executive_planner import (
    ExecutivePlanner,
)
from app.ai.executive_ai.executive_state import (
    ExecutiveState,
)


class TestExecutiveAI(
    unittest.TestCase
):

    def test_executive_state_creation(
        self,
    ) -> None:

        state = ExecutiveState(
            objective="Rozwijaj JARVIS OS"
        )

        self.assertTrue(
            state.executive_id.startswith(
                "executive-"
            )
        )
        self.assertEqual(
            state.status,
            "CREATED",
        )
        self.assertEqual(
            state.mode,
            "SAFE_AUTONOMOUS",
        )

    def test_executive_state_roadmap(
        self,
    ) -> None:

        state = ExecutiveState(
            objective="Popraw projekt"
        )

        step = state.add_roadmap_step(
            name="ANALYZE",
            module="EXECUTIVE_AI",
        )

        state.update_roadmap_step(
            step_id=step["step_id"],
            status="COMPLETED",
        )

        summary = state.summary()

        self.assertEqual(
            summary["roadmap_steps"],
            1,
        )
        self.assertEqual(
            summary["completed_steps"],
            1,
        )

    def test_executive_memory_remember(
        self,
    ) -> None:

        memory = ExecutiveMemory()

        state = ExecutiveState(
            objective="Popraw stabilność"
        )

        record = memory.remember(
            state
        )

        self.assertEqual(
            record["executive_id"],
            state.executive_id,
        )
        self.assertEqual(
            memory.summary()["total_records"],
            1,
        )

    def test_executive_memory_find_similar(
        self,
    ) -> None:

        memory = ExecutiveMemory()

        memory.remember(
            ExecutiveState(
                objective="Rozwijaj cały projekt"
            )
        )

        matches = memory.find_similar_objectives(
            "cały projekt"
        )

        self.assertEqual(
            len(matches),
            1,
        )

    def test_executive_planner_selects_stabilize(
        self,
    ) -> None:

        planner = ExecutivePlanner()

        plan = planner.build_plan(
            objective="Napraw błędy i popraw stabilność"
        )

        self.assertEqual(
            plan["selected_strategy"],
            ExecutivePlanner.STRATEGY_STABILIZE,
        )

    def test_executive_planner_selects_project_director(
        self,
    ) -> None:

        planner = ExecutivePlanner()

        plan = planner.build_plan(
            objective="Rozwijaj cały projekt"
        )

        self.assertEqual(
            plan["delegated_module"],
            ExecutivePlanner.MODULE_PROJECT_DIRECTOR,
        )

    def test_executive_engine_create_session(
        self,
    ) -> None:

        engine = ExecutiveEngine()

        result = engine.create_session(
            objective="Zaplanuj rozwój projektu"
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "READY",
        )
        self.assertTrue(
            result["executive_id"]
        )

    def test_executive_engine_delegates_to_project_director(
        self,
    ) -> None:

        project_director = MagicMock()

        project_director.handle.return_value = {
            "success": True,
            "status": "COMPLETED",
        }

        engine = ExecutiveEngine(
            project_director=project_director
        )

        created = engine.create_session(
            objective="Rozwijaj cały projekt",
            mode="AUTONOMOUS",
        )

        result = engine.start(
            executive_id=created["executive_id"],
            approved=True,
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        project_director.handle.assert_called_once()

    def test_executive_controller_can_handle(
        self,
    ) -> None:

        controller = ExecutiveController()

        self.assertTrue(
            controller.can_handle(
                "executive ai summary"
            )
        )
        self.assertFalse(
            controller.can_handle(
                "otwórz youtube"
            )
        )

    def test_executive_controller_summary(
        self,
    ) -> None:

        controller = ExecutiveController()

        result = controller.handle(
            "executive ai summary"
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "COMPLETED",
        )
        self.assertIn(
            "summary",
            result,
        )


if __name__ == "__main__":
    unittest.main()
