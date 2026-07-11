import unittest

from tests.brain_test_base import create_test_brain


class TestBrainSelfImprovementIntegration(unittest.TestCase):

    def setUp(self):
        self.brain = create_test_brain()

    def test_self_improvement_routing(self):
        command = "self improvement analyze popraw stabilność projektu"
        self.brain.improvement_controller.can_handle.return_value = True

        thought = self.brain.think(command)

        self.assertEqual(thought["handler"], "self_improvement")
        self.assertTrue(thought["can_execute"])

    def test_evolution_routing(self):
        command = "evolution start popraw testy projektu"
        self.brain.evolution_controller.can_handle.return_value = True

        thought = self.brain.think(command)

        self.assertEqual(thought["handler"], "evolution")

    def test_execute_self_improvement(self):
        self.brain.improvement_controller.handle.return_value = {
            "success": True,
            "status": "COMPLETED",
        }
        result = self.brain.execute({
            "command":"x",
            "handler":"self_improvement",
            "actions":[]
        })
        self.assertIn("Self Improvement Brain", result)

    def test_execute_evolution(self):
        self.brain.evolution_controller.handle.return_value = {
            "success": True,
            "status": "COMPLETED",
        }
        result = self.brain.execute({
            "command":"x",
            "handler":"evolution",
            "actions":[]
        })
        self.assertIn("Auto Evolution Engine", result)


if __name__ == "__main__":
    unittest.main()
