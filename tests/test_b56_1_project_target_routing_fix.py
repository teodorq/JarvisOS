from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.ai.software_engineer.autonomous_diagnostics_analyzer import (
    AutonomousDiagnosticsAnalyzer,
)
from app.ai.software_engineer.autonomous_diagnostics_collector import (
    AutonomousDiagnosticsCollector,
)
from app.ai.software_engineer.full_autonomy_feature_intent import (
    FullAutonomyFeatureIntent,
)
from app.ai.software_engineer.full_autonomy_planner import (
    FullAutonomyPlanner,
)


B55_OBJECTIVE = (
    "Bezpiecznie zrealizuj zadanie rozwojowe dla istniejącego modułu "
    "app/pkg/target.py: Podziel zbyt duży moduł. Wprowadź najmniejszą "
    "bezpieczną zmianę, zachowaj publiczne API i dodaj test regresyjny."
)


class B561ExistingTargetRoutingTests(unittest.TestCase):

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "app" / "pkg").mkdir(parents=True)
        (self.root / "tests").mkdir()
        (self.root / "app" / "pkg" / "target.py").write_text(
            "def value():\n    return 1\n",
            encoding="utf-8",
        )
        (self.root / "tests" / "test_target.py").write_text(
            "from app.pkg.target import value\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_existing_file_is_not_treated_as_new_feature(self) -> None:
        result = FullAutonomyFeatureIntent(self.root).detect(B55_OBJECTIVE)
        self.assertIsNone(result)

    def test_b55_scoped_plan_accepts_two_related_files(self) -> None:
        plan = FullAutonomyPlanner(self.root).plan(
            B55_OBJECTIVE,
            targets=[
                "app/pkg/target.py",
                "tests/test_target.py",
            ],
            metadata={
                "source": "B55ProjectIntelligence",
                "planning_mode": "project_intelligence_scoped",
            },
        )

        self.assertEqual(
            plan.metadata["planning_source"],
            "project_intelligence_scoped",
        )
        self.assertEqual(len(plan.target_files), 2)
        self.assertEqual(len(plan.campaigns), 2)
        execution_kinds = [
            stage.get("metadata", {}).get(
                "execution_kind",
                "cross_module_change",
            )
            for campaign in plan.campaigns
            for stage in campaign["stages"]
        ]
        self.assertEqual(
            execution_kinds.count("cross_module_change"),
            1,
        )
        self.assertGreaterEqual(
            execution_kinds.count("validation_only"),
            3,
        )

    def test_learning_history_does_not_override_current_root_cause(self) -> None:
        collector = AutonomousDiagnosticsCollector.__new__(
            AutonomousDiagnosticsCollector
        )
        snapshot = {
            "response": {
                "status": "FULL_AUTONOMY_PLANNING_FAILED",
                "errors": [
                    "ValueError: Podaj katalog modułu, nie pojedynczy plik."
                ],
            },
            "run": {
                "status": "FULL_AUTONOMY_PLANNING_FAILED",
                "learning_observation": {
                    "errors": [
                        "Target już istnieje: app/history_only.py"
                    ],
                },
            },
            "identifiers": {
                "job_id": "longrun-test",
                "autonomy_run_id": "autonomy-test",
            },
        }

        evidence = collector.evidence(snapshot)
        joined = "\n".join(evidence["errors"])
        self.assertIn("Podaj katalog modułu", joined)
        self.assertNotIn("history_only", joined)

        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            snapshot,
            evidence,
        )
        self.assertEqual(diagnostic.category, "PLANNING_FAILED")


if __name__ == "__main__":
    unittest.main()
