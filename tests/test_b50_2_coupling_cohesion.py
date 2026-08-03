from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.ai.architecture import (
    ArchitectureQualityAnalyzer,
    CohesionAnalyzer,
    CouplingAnalyzer,
)


class CouplingCohesionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "app").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(
        self,
        relative_path: str,
        content: str,
    ) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_coupling_analyzer_counts_incoming_and_outgoing(self) -> None:
        graph = {
            "app.a": {"app.b", "app.c"},
            "app.b": {"app.c"},
            "app.c": set(),
        }

        metrics = CouplingAnalyzer().analyze(graph)

        self.assertEqual(metrics["app.a"]["efferent"], 2)
        self.assertEqual(metrics["app.c"]["afferent"], 2)
        self.assertEqual(metrics["app.b"]["total"], 2)

    def test_high_coupling_filter_returns_only_large_values(self) -> None:
        metrics = {
            "app.a": {"total": 9},
            "app.b": {"total": 3},
        }

        result = CouplingAnalyzer().high_coupling_modules(
            metrics,
            threshold=8,
        )

        self.assertEqual(result, {"app.a": 9})

    def test_cohesion_analyzer_scores_connected_methods(self) -> None:
        self.write(
            "app/service.py",
            (
                "class Service:\n"
                "    def first(self):\n"
                "        return self.value\n"
                "    def second(self):\n"
                "        return self.value + 1\n"
            ),
        )

        report = ArchitectureQualityAnalyzer(self.root).analyze()
        metric = report["cohesion"]["app.service.Service"]

        self.assertEqual(metric["cohesion"], 1.0)
        self.assertEqual(metric["score"], 100.0)

    def test_low_cohesion_class_is_detected(self) -> None:
        self.write(
            "app/service.py",
            (
                "class Service:\n"
                "    def first(self):\n"
                "        return self.alpha\n"
                "    def second(self):\n"
                "        return self.beta\n"
            ),
        )

        report = ArchitectureQualityAnalyzer(
            self.root,
            low_cohesion_threshold=0.5,
        ).analyze()

        targets = [
            item["target"]
            for item in report["recommendations"]
        ]

        self.assertIn("app.service.Service", targets)

    def test_quality_analyzer_returns_scores_and_recommendations(self) -> None:
        self.write(
            "app/a.py",
            "from app.b import value\n",
        )
        self.write(
            "app/b.py",
            "value = 1\n",
        )

        report = ArchitectureQualityAnalyzer(
            self.root,
            high_coupling_threshold=0,
        ).analyze()

        self.assertIn("coupling_score", report)
        self.assertIn("cohesion_score", report)
        self.assertIn("overall_score", report)
        self.assertTrue(report["recommendations"])

    def test_scores_stay_within_valid_range(self) -> None:
        self.write(
            "app/simple.py",
            "value = 1\n",
        )

        report = ArchitectureQualityAnalyzer(self.root).analyze()

        self.assertGreaterEqual(report["overall_score"], 0.0)
        self.assertLessEqual(report["overall_score"], 100.0)


if __name__ == "__main__":
    unittest.main()
