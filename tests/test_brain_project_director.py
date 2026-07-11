import unittest

from tests.brain_test_base import create_test_brain


class TestBrainProjectDirectorIntegration(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.brain = create_test_brain()

    def test_project_director_start_routing(
        self,
    ) -> None:

        command = (
            "project director start "
            "popraw stabilność projektu"
        )

        self.brain.director_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "project_director",
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
        self.brain.director_controller.can_handle.assert_called_once_with(
            command
        )
        self.brain.improvement_controller.can_handle.assert_not_called()

    def test_project_director_autonomous_routing(
        self,
    ) -> None:

        command = (
            "project director autonomous "
            "rozwijaj cały projekt"
        )

        self.brain.director_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "project_director",
        )
        self.assertTrue(
            thought["can_execute"]
        )

    def test_project_director_has_priority_over_lower_layers(
        self,
    ) -> None:

        command = (
            "project director start "
            "ulepsz projekt"
        )

        self.brain.director_controller.can_handle.return_value = True
        self.brain.improvement_controller.can_handle.return_value = True
        self.brain.evolution_controller.can_handle.return_value = True
        self.brain.continuous_dev_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "project_director",
        )

        self.brain.improvement_controller.can_handle.assert_not_called()
        self.brain.evolution_controller.can_handle.assert_not_called()
        self.brain.continuous_dev_controller.can_handle.assert_not_called()

    def test_execute_project_director_completed(
        self,
    ) -> None:

        command = (
            "project director autonomous "
            "rozwijaj projekt"
        )

        self.brain.director_controller.handle.return_value = {
            "success": True,
            "status": "COMPLETED",
            "director_id": "director-001",
            "selected_module": "EVOLUTION",
            "iteration": 1,
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
                "handler": "project_director",
                "actions": [],
            }
        )

        self.assertIn(
            "Autonomous Project Director",
            result,
        )
        self.assertIn(
            "Status: COMPLETED",
            result,
        )
        self.assertIn(
            "Director ID: director-001",
            result,
        )
        self.assertIn(
            "Wybrany moduł: EVOLUTION",
            result,
        )

    def test_execute_project_director_waiting_for_approval(
        self,
    ) -> None:

        command = (
            "project director start "
            "zmień architekturę projektu"
        )

        self.brain.director_controller.handle.return_value = {
            "success": True,
            "status": "WAITING_FOR_APPROVAL",
            "director_id": "director-002",
            "selected_module": "CONTINUOUS_DEV",
            "iteration": 0,
            "requires_approval": True,
        }

        result = self.brain.execute(
            {
                "command": command,
                "handler": "project_director",
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

    def test_format_project_director_summary(
        self,
    ) -> None:

        result = self.brain._format_project_director_response(
            {
                "success": True,
                "status": "COMPLETED",
                "sessions": [
                    {
                        "director_id": "one",
                    },
                    {
                        "director_id": "two",
                    },
                ],
            }
        )

        self.assertIn(
            "Liczba sesji: 2",
            result,
        )

    def test_format_project_director_memory(
        self,
    ) -> None:

        result = self.brain._format_project_director_response(
            {
                "success": True,
                "status": "COMPLETED",
                "memory_summary": {
                    "total_records": 4,
                },
            }
        )

        self.assertIn(
            "Rekordy pamięci: 4",
            result,
        )

    def test_format_project_director_error(
        self,
    ) -> None:

        result = self.brain._format_project_director_response(
            {
                "success": False,
                "status": "FAILED",
                "director_id": "director-error",
                "error": "Błąd testowy Directora",
            }
        )

        self.assertIn(
            "Status: FAILED",
            result,
        )
        self.assertIn(
            "Błąd testowy Directora",
            result,
        )

    def test_project_director_summary_command_routing(
        self,
    ) -> None:

        command = "project director summary"

        self.brain.director_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "project_director",
        )

    def test_project_director_memory_command_routing(
        self,
    ) -> None:

        command = "project director memory"

        self.brain.director_controller.can_handle.return_value = True

        thought = self.brain.think(
            command
        )

        self.assertEqual(
            thought["handler"],
            "project_director",
        )


if __name__ == "__main__":
    unittest.main()
