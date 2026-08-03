from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.ai.evolution.autonomous_evolution_engine import (
    AutonomousEvolutionEngine,
)
from app.ai.evolution.evolution_backlog_selector import (
    EvolutionBacklogSelector,
)
from app.ai.evolution.evolution_learning_memory import (
    EvolutionLearningMemory,
)


class AutonomousEvolutionEngineTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        memory_path = Path(self.temp_directory.name) / "learning.json"
        self.memory = EvolutionLearningMemory(storage_path=memory_path)
        self.engine = AutonomousEvolutionEngine(memory=self.memory)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_selects_best_task_instead_of_first(self) -> None:
        tasks = [
            {
                "task_id": "first",
                "title": "Ryzykowna przebudowa",
                "priority_score": 80,
                "value_score": 70,
                "effort_score": 90,
                "risk_score": 95,
            },
            {
                "task_id": "best",
                "title": "Bezpieczna poprawa testów",
                "priority_score": 75,
                "value_score": 85,
                "effort_score": 20,
                "risk_score": 10,
            },
        ]

        selected = self.engine.select_best_task(tasks)

        self.assertIsNotNone(selected)
        self.assertEqual(selected["task_id"], "best")
        self.assertGreater(selected["evolution_score"], 70.0)

    def test_learning_reduces_score_after_rollbacks(self) -> None:
        task = {
            "task_id": "unstable",
            "title": "Zmiana modułu",
            "target": "app/example.py",
            "priority_score": 70,
            "value_score": 70,
            "effort_score": 40,
            "risk_score": 20,
        }
        before = self.engine.evaluate_task(task)

        for _ in range(3):
            self.engine.learn_from_result(
                task,
                {
                    "success": False,
                    "status": "ROLLED_BACK",
                    "rollback": True,
                },
            )

        after = self.engine.evaluate_task(task)

        self.assertLess(after["success_probability"], before["success_probability"])
        self.assertGreater(after["risk_score"], before["risk_score"])
        self.assertLess(after["evolution_score"], before["evolution_score"])

    def test_learning_rewards_successful_changes(self) -> None:
        task = {
            "task_id": "stable",
            "title": "Poprawa walidacji",
            "target": "app/stable.py",
            "priority_score": 60,
            "value_score": 65,
            "effort_score": 35,
            "risk_score": 25,
        }

        for _ in range(4):
            self.engine.learn_from_result(
                task,
                {"success": True, "status": "COMPLETED"},
            )

        score = self.engine.evaluate_task(task)
        stats = self.memory.statistics_for(task)

        self.assertEqual(stats["success_probability"], 100.0)
        self.assertEqual(stats["rollback_rate"], 0.0)
        self.assertGreater(score["learning_bonus"], 50.0)

    def test_selector_ignores_non_pending_items(self) -> None:
        selector = EvolutionBacklogSelector(engine=self.engine)
        result = selector.select(
            [
                {
                    "task_id": "done",
                    "title": "Zakończone",
                    "status": "COMPLETED",
                    "priority_score": 100,
                },
                {
                    "task_id": "pending",
                    "title": "Oczekujące",
                    "status": "PENDING",
                    "priority_score": 50,
                },
            ]
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["task_id"], "pending")

    def test_memory_persists_results(self) -> None:
        task = {"task_id": "x", "title": "Test", "target": "app/x.py"}
        self.memory.remember(task, {"success": True, "status": "COMPLETED"})

        restored = EvolutionLearningMemory(storage_path=self.memory.storage_path)

        self.assertEqual(restored.summary()["entries_count"], 1)
        self.assertEqual(restored.summary()["successes"], 1)


if __name__ == "__main__":
    unittest.main()
