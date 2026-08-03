from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.ai.software_engineer.full_autonomy_planner import (
    FullAutonomyPlanner,
)


class B564ScopedSameSubsystemPlanningTests(unittest.TestCase):

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.targets = [
            "app/ai/software_engineer/target.py",
            "app/ai/software_engineer/__init__.py",
            "app/ai/software_engineer/workflow.py",
            "app/ai/software_engineer/helper.py",
        ]
        for index, relative in enumerate(self.targets):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"VALUE_{index} = {index}\n",
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_b55_scoped_plan_accepts_related_files_in_one_subsystem(
        self,
    ) -> None:
        plan = FullAutonomyPlanner(self.root).plan(
            (
                "Bezpiecznie zrealizuj zadanie rozwojowe dla istniejącego "
                "modułu app/ai/software_engineer/target.py: Podziel zbyt "
                "długą funkcję, zachowaj publiczne API i dodaj test regresyjny."
            ),
            targets=self.targets,
            metadata={
                "source": "B55ProjectIntelligence",
                "planning_mode": "project_intelligence_scoped",
                "issue_type": "LONG_FUNCTION",
            },
        )

        self.assertEqual(
            plan.metadata["planning_source"],
            "project_intelligence_scoped",
        )
        self.assertEqual(plan.subsystems, ["app.ai"])
        self.assertEqual(set(plan.target_files), set(self.targets))
        self.assertEqual(len(plan.campaigns), 2)

        stages = [
            stage
            for campaign in plan.campaigns
            for stage in campaign["stages"]
        ]
        self.assertEqual(len(stages), 4)
        self.assertTrue(
            all(stage["allow_same_subsystem"] for stage in stages)
        )

    def test_scoped_validation_stages_keep_validation_only_kind(
        self,
    ) -> None:
        plan = FullAutonomyPlanner(self.root).plan(
            "Przeprowadź bezpieczną zmianę zakresową i pełną walidację.",
            targets=self.targets,
            metadata={
                "source": "B55ProjectIntelligence",
                "planning_mode": "project_intelligence_scoped",
            },
        )

        validation_stages = [
            stage
            for campaign in plan.campaigns
            for stage in campaign["stages"]
            if stage.get("metadata", {}).get("execution_kind")
            == "validation_only"
        ]
        self.assertEqual(len(validation_stages), 3)
        self.assertTrue(
            all(
                stage["allow_same_subsystem"]
                for stage in validation_stages
            )
        )


if __name__ == "__main__":
    unittest.main()
