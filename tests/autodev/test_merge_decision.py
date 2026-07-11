import unittest
from app.autodev.merge_decision import MergeDecisionEngine

class TestMergeDecisionEngine(unittest.TestCase):
    def test_merge(self):
        result = MergeDecisionEngine().decide(
            test_result={"success": True},
            regression_result={"success": True},
        )
        self.assertEqual(result["decision"], "MERGE")

    def test_rollback(self):
        result = MergeDecisionEngine().decide(
            test_result={"success": False},
            regression_result={"success": False},
        )
        self.assertEqual(result["decision"], "ROLLBACK")

if __name__ == "__main__":
    unittest.main()
