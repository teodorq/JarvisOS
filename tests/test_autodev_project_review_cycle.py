import tempfile
import unittest
from pathlib import Path

from app.autodev.autodev_change_simulator import (
    AutoDevChangeSimulator,
)
from app.autodev.autodev_project_analyzer import (
    AutoDevProjectAnalyzer,
)
from app.autodev.autodev_project_review_cycle import (
    AutoDevProjectReviewCycle,
)


class TestAutoDevProjectReviewCycle(
    unittest.TestCase
):

    def test_project_analyzer(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "example.py").write_text(
                "print('ok')\n",
                encoding="utf-8",
            )

            analyzer = AutoDevProjectAnalyzer(
                project_root=temp_dir
            )

            result = analyzer.analyze()

            self.assertTrue(
                result["success"]
            )

            self.assertEqual(
                result["snapshot"]["python_files_count"],
                1,
            )

    def test_change_simulator_blocks_high_risk(
        self,
    ) -> None:
        simulator = AutoDevChangeSimulator()

        result = simulator.simulate(
            target="app/test.py",
            changed_lines=500,
            dependent_modules=10,
            public_api=True,
        )

        self.assertEqual(
            result["risk_level"],
            "CRITICAL"
        )

        self.assertFalse(
            result["writes_code"]
        )

    def test_full_review_cycle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "example.py").write_text(
                "import os\n\nvalue = 1\n",
                encoding="utf-8",
            )

            cycle = AutoDevProjectReviewCycle(
                project_root=temp_dir
            )

            result = cycle.run(
                target=str(
                    root / "example.py"
                ),
                changed_lines=5,
                dependent_modules=0,
            )

            self.assertTrue(
                result["success"]
            )

            self.assertEqual(
                result["status"],
                "PROJECT_REVIEW_PASSED"
            )

            self.assertFalse(
                result["writes_code"]
            )


if __name__ == "__main__":
    unittest.main()
