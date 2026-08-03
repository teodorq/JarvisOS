from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.ai.architecture import (
    ModuleSplitPlan,
    ModuleSplitPlanner,
    RefactorBlueprintBuilder,
    RefactorPlanEngine,
)


class RefactorBlueprintTests(unittest.TestCase):

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

    def test_builds_split_plan_from_god_object(self) -> None:
        planner = ModuleSplitPlanner()

        plans = planner.build_from_god_objects(
            [
                {
                    "module": "app.ai.brain",
                    "class_name": "BrainController",
                    "responsibility_count": 6,
                }
            ]
        )

        self.assertEqual(len(plans), 1)
        self.assertEqual(
            plans[0].target,
            "app.ai.brain.BrainController",
        )
        self.assertGreaterEqual(
            len(plans[0].proposed_modules),
            2,
        )

    def test_builds_split_plan_from_large_file(self) -> None:
        planner = ModuleSplitPlanner()

        plans = planner.build_from_large_files(
            {
                "C:/JarvisAI/app/ai/brain.py": 950,
            }
        )

        self.assertEqual(len(plans), 1)
        self.assertEqual(
            plans[0].priority,
            "medium",
        )
        self.assertIn(
            "brain_service",
            plans[0].proposed_modules,
        )

    def test_blueprint_contains_safeguards(self) -> None:
        plan = ModuleSplitPlan(
            target="app.ai.brain.Brain",
            reason="Za dużo odpowiedzialności.",
            proposed_modules=("brain_router", "brain_runtime"),
            migration_steps=("Podziel klasę.",),
            priority="high",
            estimated_risk=0.5,
            estimated_roi=0.8,
        )

        blueprint = RefactorBlueprintBuilder().from_split_plan(
            plan,
        )

        self.assertTrue(blueprint.safeguards)
        self.assertIn(
            "Wykonaj rollback przy regresji.",
            blueprint.safeguards,
        )

    def test_batch_sorts_high_priority_first(self) -> None:
        low = ModuleSplitPlan(
            target="low",
            reason="low",
            proposed_modules=("low_a",),
            migration_steps=("step",),
            priority="medium",
            estimated_risk=0.2,
            estimated_roi=0.9,
        )
        high = ModuleSplitPlan(
            target="high",
            reason="high",
            proposed_modules=("high_a",),
            migration_steps=("step",),
            priority="high",
            estimated_risk=0.8,
            estimated_roi=0.5,
        )

        result = RefactorBlueprintBuilder().build_batch(
            [low, high],
        )

        self.assertEqual(result[0].title, "Refactor: high")

    def test_refactor_plan_engine_returns_report(self) -> None:
        content = "\n".join(
            f"value_{index} = {index}"
            for index in range(710)
        )
        self.write(
            "app/large.py",
            content,
        )

        report = RefactorPlanEngine(
            self.root,
        ).build()

        self.assertIn("split_plans", report)
        self.assertIn("blueprints", report)
        self.assertGreater(
            report["recommended_count"],
            0,
        )

    def test_blueprint_serializes_to_dictionary(self) -> None:
        plan = ModuleSplitPlan(
            target="app.service.Service",
            reason="split",
            proposed_modules=("service_a",),
            migration_steps=("step",),
            priority="high",
            estimated_risk=0.3,
            estimated_roi=0.7,
        )

        data = (
            RefactorBlueprintBuilder()
            .from_split_plan(plan)
            .to_dict()
        )

        self.assertEqual(
            data["title"],
            "Refactor: app.service.Service",
        )
        self.assertEqual(
            data["estimated_roi"],
            0.7,
        )


if __name__ == "__main__":
    unittest.main()
