import unittest

from tests.brain_test_base import create_test_brain


class TestBrainExecutiveAIIntegration(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.brain = create_test_brain()

    def test_executive_ai_start_routing(
        self,
    ) -> None:

        command = (
            "executive ai start "
            "zaplanuj rozwój JARVIS OS"
        )

        self.brain.executive_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "executive_ai",
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

        self.brain.executive_controller.can_handle.assert_called_once_with(
            command
        )

        self.brain.director_controller.can_handle.assert_not_called()

    def test_executive_ai_autonomous_routing(
        self,
    ) -> None:

        command = (
            "executive ai autonomous "
            "rozwijaj cały system"
        )

        self.brain.executive_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "executive_ai",
        )

        self.assertTrue(
            thought["can_execute"]
        )

    def test_executive_ai_has_highest_priority(
        self,
    ) -> None:

        command = (
            "executive ai start "
            "ulepsz cały projekt"
        )

        self.brain.executive_controller.can_handle.return_value = True
        self.brain.director_controller.can_handle.return_value = True
        self.brain.improvement_controller.can_handle.return_value = True
        self.brain.evolution_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "executive_ai",
        )

        self.brain.meta_controller.can_handle.assert_called_once_with(
            command
        )

        self.brain.director_controller.can_handle.assert_not_called()
        self.brain.improvement_controller.can_handle.assert_not_called()
        self.brain.evolution_controller.can_handle.assert_not_called()

    def test_execute_executive_ai_completed(
        self,
    ) -> None:

        command = (
            "executive ai autonomous "
            "rozwijaj JARVIS OS"
        )

        self.brain.executive_controller.handle.return_value = {
            "success": True,
            "status": "COMPLETED",
            "executive_id": "executive-001",
            "selected_strategy": "EVOLVE",
            "delegated_module": "PROJECT_DIRECTOR",
            "phase": 1,
            "requires_approval": False,
            "summary": {
                "current_phase": "FINISHED",
                "priority": "HIGH",
                "risk_level": "MEDIUM",
            },
        }

        result = self.brain.execute(
            {
                "command": command,
                "handler": "executive_ai",
                "actions": [],
            }
        )

        self.assertIn(
            "Executive AI",
            result,
        )

        self.assertIn(
            "Status: COMPLETED",
            result,
        )

        self.assertIn(
            "Executive ID: executive-001",
            result,
        )

        self.assertIn(
            "Strategia: EVOLVE",
            result,
        )

        self.assertIn(
            "Delegowany moduł: PROJECT_DIRECTOR",
            result,
        )

        self.assertIn(
            "Faza: 1",
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

        self.brain.executive_controller.handle.assert_called_once_with(
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

    def test_execute_executive_ai_waiting_for_approval(
        self,
    ) -> None:

        command = (
            "executive ai start "
            "przebuduj architekturę systemu"
        )

        self.brain.executive_controller.handle.return_value = {
            "success": True,
            "status": "WAITING_FOR_APPROVAL",
            "executive_id": "executive-002",
            "selected_strategy": "STABILIZE",
            "delegated_module": "PROJECT_DIRECTOR",
            "phase": 0,
            "requires_approval": True,
        }

        result = self.brain.execute(
            {
                "command": command,
                "handler": "executive_ai",
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
            "Executive AI czeka",
            result,
        )

    def test_format_executive_summary(
        self,
    ) -> None:

        result = self.brain._format_executive_response(
            {
                "success": True,
                "status": "COMPLETED",
                "sessions": [
                    {
                        "executive_id": "one",
                    },
                    {
                        "executive_id": "two",
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

    def test_format_executive_memory(
        self,
    ) -> None:

        result = self.brain._format_executive_response(
            {
                "success": True,
                "status": "COMPLETED",
                "memory_summary": {
                    "total_records": 5,
                },
            }
        )

        self.assertIn(
            "Rekordy pamięci: 5",
            result,
        )

    def test_format_executive_error(
        self,
    ) -> None:

        result = self.brain._format_executive_response(
            {
                "success": False,
                "status": "FAILED",
                "executive_id": "executive-error",
                "error": "Błąd testowy Executive AI",
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
            "Błąd testowy Executive AI",
            result,
        )

        self.assertIn(
            "executive-error",
            result,
        )

    def test_executive_summary_command_routing(
        self,
    ) -> None:

        command = "executive ai summary"

        self.brain.executive_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "executive_ai",
        )

    def test_executive_memory_command_routing(
        self,
    ) -> None:

        command = "executive ai memory"

        self.brain.executive_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "executive_ai",
        )


if __name__ == "__main__":
    unittest.main()