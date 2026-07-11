import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.autodev.autodev_autonomy_v6 import (
    AutoDevAutonomyV6,
)
from app.autodev.project_intelligence_inspector import (
    ProjectIntelligenceInspector,
)


class TestAutoDevProjectIntelligence(
    unittest.TestCase
):

    def test_inspector_uses_real_project_scanner(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "module_a.py").write_text(
                (
                    "def duplicated():\n"
                    "    value = 1\n"
                    "    return value\n"
                ),
                encoding="utf-8",
            )

            (root / "module_b.py").write_text(
                (
                    "def duplicated_copy():\n"
                    "    value = 1\n"
                    "    return value\n"
                ),
                encoding="utf-8",
            )

            inspector = ProjectIntelligenceInspector(
                project_root=temp_dir
            )

            result = inspector.inspect()

            self.assertTrue(result["success"])
            self.assertEqual(
                result["status"],
                "PROJECT_INTELLIGENCE_READY",
            )
            self.assertEqual(
                result["report"]["index"]["files_count"],
                2,
            )
            self.assertGreaterEqual(
                result["report"]["duplicates"][
                    "duplicate_groups_count"
                ],
                1,
            )
            self.assertFalse(result["writes_code"])

    def test_autonomy_v6_delegates_tasks(
        self,
    ) -> None:
        autonomy_v5 = MagicMock()
        inspector = MagicMock()

        inspector.inspect.return_value = {
            "success": True,
            "status": "PROJECT_INTELLIGENCE_READY",
            "next_tasks": [
                {
                    "goal": "Podziel duży moduł",
                    "priority_score": 25.0,
                    "risk_score": 10.0,
                    "value_score": 20.0,
                }
            ],
            "writes_code": False,
        }

        autonomy_v5.run.return_value = {
            "success": True,
            "status": "AUTONOMY_V5_COMPLETED",
            "writes_code": False,
        }

        autonomy = AutoDevAutonomyV6(
            autonomy_v5=autonomy_v5,
            inspector=inspector,
        )

        result = autonomy.run()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "AUTONOMY_V6_COMPLETED",
        )
        self.assertFalse(result["writes_code"])
        self.assertFalse(result["approved"])
        autonomy_v5.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
