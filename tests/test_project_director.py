import unittest
from unittest.mock import MagicMock

from app.ai.project_director.director_controller import DirectorController
from app.ai.project_director.director_engine import DirectorEngine
from app.ai.project_director.director_memory import DirectorMemory
from app.ai.project_director.director_planner import DirectorPlanner
from app.ai.project_director.director_state import DirectorState


class TestProjectDirector(unittest.TestCase):

    def test_director_state_creation(self) -> None:
        state = DirectorState(objective="Popraw jakość projektu")

        self.assertTrue(state.director_id.startswith("director-"))
        self.assertEqual(state.status, "CREATED")
        self.assertEqual(state.mode, "SAFE_AUTONOMOUS")

    def test_director_state_plan_and_summary(self) -> None:
        state = DirectorState(objective="Rozwijaj projekt")

        step = state.add_plan_step(
            name="ANALYZE",
            module="RESEARCH",
        )

        state.update_plan_step(
            step_id=step["step_id"],
            status="COMPLETED",
        )

        summary = state.summary()

        self.assertEqual(summary["plan_steps"], 1)
        self.assertEqual(summary["completed_steps"], 1)

    def test_director_memory_remember(self) -> None:
        memory = DirectorMemory()
        state = DirectorState(objective="Popraw stabilność")

        record = memory.remember(state)

        self.assertEqual(record["director_id"], state.director_id)
        self.assertEqual(memory.summary()["total_records"], 1)

    def test_director_memory_find_similar(self) -> None:
        memory = DirectorMemory()

        memory.remember(
            DirectorState(
                objective="Popraw stabilność projektu"
            )
        )

        matches = memory.find_similar_objectives(
            "stabilność projektu"
        )

        self.assertEqual(len(matches), 1)

    def test_director_planner_selects_self_improvement(self) -> None:
        planner = DirectorPlanner()

        plan = planner.build_plan(
            objective="self improvement popraw jakość projektu"
        )

        self.assertEqual(
            plan["selected_module"],
            DirectorPlanner.MODULE_SELF_IMPROVEMENT,
        )

    def test_director_planner_selects_evolution(self) -> None:
        planner = DirectorPlanner()

        plan = planner.build_plan(
            objective="evolution autonomicznie rozwijaj projekt"
        )

        self.assertEqual(
            plan["selected_module"],
            DirectorPlanner.MODULE_EVOLUTION,
        )

    def test_director_engine_create_session(self) -> None:
        engine = DirectorEngine()

        result = engine.create_session(
            objective="Zdecyduj co rozwijać dalej"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["director_id"])

    def test_director_engine_executes_reasoner(self) -> None:
        reasoner = MagicMock()
        reasoner.handle.return_value = {
            "success": True,
            "status": "COMPLETED",
        }

        engine = DirectorEngine(
            reasoning_service=reasoner
        )

        created = engine.create_session(
            objective="Zdecyduj najlepszą strategię",
            mode="AUTONOMOUS",
        )

        result = engine.start(
            director_id=created["director_id"],
            approved=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "COMPLETED")
        reasoner.handle.assert_called_once()

    def test_director_controller_can_handle(self) -> None:
        controller = DirectorController()

        self.assertTrue(
            controller.can_handle(
                "project director summary"
            )
        )
        self.assertFalse(
            controller.can_handle(
                "otwórz youtube"
            )
        )

    def test_director_controller_summary(self) -> None:
        controller = DirectorController()

        result = controller.handle(
            "project director summary"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIn("summary", result)


if __name__ == "__main__":
    unittest.main()
