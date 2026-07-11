import unittest
from unittest.mock import MagicMock

from app.ai.brain import Brain


class TestBrainMetaExecutiveIntegration(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.brain = Brain.__new__(
            Brain
        )

        self.brain.cognitive = MagicMock()
        self.brain.memory = MagicMock()

        self.brain.meta_controller = MagicMock()
        self.brain.executive_controller = MagicMock()
        self.brain.director_controller = MagicMock()
        self.brain.improvement_controller = MagicMock()
        self.brain.evolution_controller = MagicMock()
        self.brain.continuous_dev_controller = MagicMock()
        self.brain.reasoning_service = MagicMock()
        self.brain.research_service = MagicMock()
        self.brain.autodev_router = MagicMock()
        self.brain.planner = MagicMock()
        self.brain.executor = MagicMock()
        self.brain.task_planner = MagicMock()
        self.brain.agent_loop = MagicMock()

        self.brain.meta_controller.can_handle.return_value = False
        self.brain.executive_controller.can_handle.return_value = False
        self.brain.director_controller.can_handle.return_value = False
        self.brain.improvement_controller.can_handle.return_value = False
        self.brain.evolution_controller.can_handle.return_value = False
        self.brain.continuous_dev_controller.can_handle.return_value = False
        self.brain.reasoning_service.can_handle.return_value = False
        self.brain.research_service.can_handle.return_value = False
        self.brain.autodev_router.can_handle.return_value = False

    def test_meta_executive_start_routing(
        self,
    ) -> None:

        command = (
            "meta executive start "
            "zarządzaj całym JARVIS OS"
        )

        self.brain.meta_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "meta_executive",
        )
        self.assertTrue(
            thought["can_execute"]
        )
        self.assertEqual(
            thought["command"],
            command,
        )

        self.brain.meta_controller.can_handle.assert_called_once_with(
            command
        )
        self.brain.executive_controller.can_handle.assert_not_called()

    def test_meta_executive_autonomous_routing(
        self,
    ) -> None:

        command = (
            "meta executive autonomous "
            "rozwijaj cały system"
        )

        self.brain.meta_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "meta_executive",
        )
        self.assertTrue(
            thought["can_execute"]
        )

    def test_meta_executive_has_highest_priority(
        self,
    ) -> None:

        command = (
            "meta executive start "
            "ulepsz cały system"
        )

        self.brain.meta_controller.can_handle.return_value = True
        self.brain.executive_controller.can_handle.return_value = True
        self.brain.director_controller.can_handle.return_value = True
        self.brain.improvement_controller.can_handle.return_value = True
        self.brain.evolution_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "meta_executive",
        )

        self.brain.executive_controller.can_handle.assert_not_called()
        self.brain.director_controller.can_handle.assert_not_called()
        self.brain.improvement_controller.can_handle.assert_not_called()
        self.brain.evolution_controller.can_handle.assert_not_called()

    def test_execute_meta_executive_completed(
        self,
    ) -> None:

        command = (
            "meta executive autonomous "
            "zarządzaj całym systemem"
        )

        self.brain.meta_controller.handle.return_value = {
            "success": True,
            "status": "COMPLETED",
            "meta_id": "meta-001",
            "selected_strategy": "GOVERN",
            "selected_layer": "EXECUTIVE_AI",
            "cycle": 1,
            "requires_approval": False,
            "summary": {
                "current_stage": "FINISHED",
                "priority": "HIGH",
                "risk_level": "MEDIUM",
            },
        }

        result = self.brain.execute(
            {
                "command": command,
                "handler": "meta_executive",
                "actions": [],
            }
        )

        self.assertIn(
            "Meta Executive",
            result,
        )
        self.assertIn(
            "Status: COMPLETED",
            result,
        )
        self.assertIn(
            "Meta ID: meta-001",
            result,
        )
        self.assertIn(
            "Strategia: GOVERN",
            result,
        )
        self.assertIn(
            "Wybrana warstwa: EXECUTIVE_AI",
            result,
        )
        self.assertIn(
            "Cykl: 1",
            result,
        )
        self.assertIn(
            "Priorytet: HIGH",
            result,
        )
        self.assertIn(
            "Ryzyko: MEDIUM",
            result,
        )

        self.brain.meta_controller.handle.assert_called_once_with(
            command=command,
            context={
                "project_root": "C:/JarvisAI",
                "metadata": {
                    "source": "Brain",
                },
            },
        )

        self.brain.memory.add_history.assert_called_once_with(
            command,
            result,
        )
        self.brain.cognitive.after_execute.assert_called_once_with(
            command,
            result,
        )

    def test_execute_meta_executive_waiting_for_approval(
        self,
    ) -> None:

        command = (
            "meta executive start "
            "przebuduj cały system"
        )

        self.brain.meta_controller.handle.return_value = {
            "success": True,
            "status": "WAITING_FOR_APPROVAL",
            "meta_id": "meta-002",
            "selected_strategy": "EVOLVE",
            "selected_layer": "EXECUTIVE_AI",
            "cycle": 0,
            "requires_approval": True,
        }

        result = self.brain.execute(
            {
                "command": command,
                "handler": "meta_executive",
                "actions": [],
            }
        )

        self.assertIn(
            "WAITING_FOR_APPROVAL",
            result,
        )
        self.assertIn(
            "wymaga akceptacji",
            result,
        )
        self.assertIn(
            "Meta Executive czeka",
            result,
        )

    def test_format_meta_summary(
        self,
    ) -> None:

        result = self.brain._format_meta_response(
            {
                "success": True,
                "status": "COMPLETED",
                "sessions": [
                    {
                        "meta_id": "one",
                    },
                    {
                        "meta_id": "two",
                    },
                ],
            }
        )

        self.assertIn(
            "Status: COMPLETED",
            result,
        )
        self.assertIn(
            "Liczba sesji: 2",
            result,
        )

    def test_format_meta_memory(
        self,
    ) -> None:

        result = self.brain._format_meta_response(
            {
                "success": True,
                "status": "COMPLETED",
                "memory_summary": {
                    "total_records": 6,
                },
            }
        )

        self.assertIn(
            "Rekordy pamięci: 6",
            result,
        )

    def test_format_meta_error(
        self,
    ) -> None:

        result = self.brain._format_meta_response(
            {
                "success": False,
                "status": "FAILED",
                "meta_id": "meta-error",
                "error": "Błąd testowy Meta Executive",
            }
        )

        self.assertIn(
            "nie zakończył operacji poprawnie",
            result,
        )
        self.assertIn(
            "Status: FAILED",
            result,
        )
        self.assertIn(
            "Błąd testowy Meta Executive",
            result,
        )
        self.assertIn(
            "meta-error",
            result,
        )

    def test_meta_summary_command_routing(
        self,
    ) -> None:

        command = "meta executive summary"

        self.brain.meta_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "meta_executive",
        )

    def test_meta_memory_command_routing(
        self,
    ) -> None:

        command = "meta executive memory"

        self.brain.meta_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "meta_executive",
        )


if __name__ == "__main__":
    unittest.main()
