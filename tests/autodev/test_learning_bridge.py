import unittest
from unittest.mock import MagicMock

from app.autodev.learning_bridge import LearningBridge


class TestLearningBridge(unittest.TestCase):

    def test_records_in_both_memories(self) -> None:
        engine = MagicMock()
        engine.learn_from_result.return_value = {
            "success": True,
            "status": "LEARNED",
        }
        engine.summary.return_value = {}

        memory = MagicMock()
        memory.summary_dict.return_value = {
            "total": 1,
        }

        bridge = LearningBridge(
            learning_engine=engine,
            reasoning_memory=memory,
        )

        result = bridge.record(
            {
                "success": True,
                "status": "COMPLETED",
            }
        )

        self.assertTrue(
            result["success"]
        )
        engine.learn_from_result.assert_called_once()
        memory.remember.assert_called_once()


if __name__ == "__main__":
    unittest.main()
