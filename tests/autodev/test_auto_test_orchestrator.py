import unittest
from unittest.mock import MagicMock
from app.autodev.auto_test_orchestrator import AutoTestOrchestrator

class TestAutoTestOrchestrator(unittest.TestCase):
    def test_merge_when_tests_pass(self):
        selector = MagicMock()
        plan = MagicMock()
        plan.to_dict.return_value = {}
        selector.build_plan.return_value = plan

        runner = MagicMock()
        runner.run.return_value = {"success": True, "results": []}

        analyzer = MagicMock()
        analyzer.analyze.return_value = {"success": True}

        decision = MagicMock()
        decision.decide.return_value = {
            "status": "MERGE_ALLOWED",
            "decision": "MERGE",
        }

        result = AutoTestOrchestrator(
            selector=selector,
            runner=runner,
            analyzer=analyzer,
            decision_engine=decision,
        ).run(["app/example.py"])

        self.assertTrue(result["success"])

if __name__ == "__main__":
    unittest.main()
