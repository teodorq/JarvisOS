from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.agent.loop import AgentLoop


class AgentLoopFinishRefactorTests(unittest.TestCase):
    def test_finished_task_keeps_the_same_final_report(self) -> None:
        loop = AgentLoop.__new__(AgentLoop)
        loop.goal_manager = MagicMock()
        loop.goal_manager.summary.return_value = "GOAL SUMMARY"
        loop.reflection = MagicMock()
        loop.reflection.reflect.return_value = {"summary": "REFLECTION"}
        loop.executor = MagicMock()
        loop.feedback = MagicMock()
        loop.replanner = MagicMock()
        task = SimpleNamespace(
            finished=True,
            failed=False,
            goal="goal",
            summary=lambda: "TASK SUMMARY",
        )

        result = loop.run(task)

        loop.goal_manager.start_goal.assert_called_once_with("goal")
        loop.goal_manager.finish_goal.assert_called_once_with()
        loop.goal_manager.fail_goal.assert_not_called()
        loop.reflection.reflect.assert_called_once_with(task, loop.goal_manager)
        self.assertIn("GOAL MANAGER", result)
        self.assertIn("SELF REFLECTION", result)
        self.assertIn("ZAKO\u0143CZONO", result)
        self.assertTrue(result.endswith("TASK SUMMARY"))


if __name__ == "__main__":
    unittest.main()
