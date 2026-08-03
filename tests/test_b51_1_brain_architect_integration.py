from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.ai.brain import Brain
from app.ai.planner_llm import PlannerLLM


class BrainArchitectIntegrationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.brain = Brain.__new__(Brain)
        self.brain.cognitive = MagicMock()
        self.brain.architect_controller = MagicMock()
        self.brain.architect_controller.can_handle.return_value = True
        self.brain.meta_controller = MagicMock()
        self.brain.executive_controller = MagicMock()
        self.brain.director_controller = MagicMock()
        self.brain.improvement_controller = MagicMock()
        self.brain.evolution_controller = MagicMock()
        self.brain.continuous_dev_controller = MagicMock()
        self.brain.reasoning_service = MagicMock()
        self.brain.research_service = MagicMock()
        self.brain.autodev_router = MagicMock()
        self.brain.autonomous_dev_controller = MagicMock()
        self.brain.autonomous_dev_controller.can_handle.return_value = False
        self.brain.planner = MagicMock()
        self.brain._remember_execution = MagicMock()

    def test_planner_detects_architect_before_research(self) -> None:
        planner = PlannerLLM()

        handler = planner.detect_handler(
            "Przeanalizuj architekturę projektu"
        )

        self.assertEqual(handler, "architect")

    def test_planner_creates_architect_plan(self) -> None:
        planner = PlannerLLM()

        plan = planner.create_plan(
            "Autonomous Architect"
        )

        self.assertTrue(plan["execute"])
        self.assertEqual(
            plan["handler_hint"],
            "architect",
        )

    def test_brain_routes_command_to_architect(self) -> None:
        thought = self.brain.think(
            "Przeanalizuj architekturę projektu"
        )

        self.assertEqual(
            thought["handler"],
            "autonomous_architect",
        )
        self.brain.cognitive.after_plan.assert_called_once()

    def test_brain_executes_architect_controller(self) -> None:
        self.brain.architect_controller.handle.return_value = {
            "success": True,
            "architecture_score": 91.0,
            "smell_score": 88.0,
            "recommended_count": 2,
            "blueprints": [],
            "autodev_queue": {
                "created": 2,
            },
        }

        result = self.brain.execute(
            {
                "command": "Autonomous Architect",
                "handler": "autonomous_architect",
            }
        )

        self.assertIn(
            "Autonomous Architect zakończył analizę",
            result,
        )
        self.assertIn(
            "Nowe zadania AutoDev: 2",
            result,
        )
        self.brain.architect_controller.handle.assert_called_once()

    def test_formatter_reports_failed_architect(self) -> None:
        result = self.brain._format_architect_response(
            {
                "success": False,
                "status": "FAILED",
                "error": "analysis error",
            }
        )

        self.assertIn("FAILED", result)
        self.assertIn("analysis error", result)


if __name__ == "__main__":
    unittest.main()
