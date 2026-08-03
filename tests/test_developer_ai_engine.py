import tempfile
import unittest
from pathlib import Path

from app.autodev.developer_ai_engine import (
    DeveloperAIEngine,
    DeveloperAIEnginePolicy,
)


class TestDeveloperAIEngine(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        self.root = Path(
            self.temp_dir.name
        )

        self.target = (
            self.root
            / "sample.py"
        )

    def tearDown(
        self,
    ) -> None:

        self.temp_dir.cleanup()

    def test_local_empty_block_proposal(
        self,
    ) -> None:

        self.target.write_text(
            "def run():\n"
            "    pass\n",
            encoding="utf-8",
        )

        engine = DeveloperAIEngine(
            policy=DeveloperAIEnginePolicy(
                project_root=str(self.root),
                prefer_local_refactoring=True,
                allow_llm_fallback=False,
            )
        )

        result = engine.generate(
            {
                "path": str(self.target),
                "goal": "Napraw pusty blok",
                "issue_type": "EMPTY_BLOCK",
                "line": 2,
                "issue": {
                    "type": "EMPTY_BLOCK",
                    "line": 2,
                },
            }
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "LOCAL_PROPOSAL_READY"
        )

        proposed = result[
            "proposal"
        ][
            "proposed_content"
        ]

        self.assertIn(
            "NotImplementedError",
            proposed,
        )

        self.assertEqual(
            self.target.read_text(
                encoding="utf-8"
            ),
            "def run():\n"
            "    pass\n",
        )

    def test_unsupported_issue(
        self,
    ) -> None:

        self.target.write_text(
            "def run():\n"
            "    return True\n",
            encoding="utf-8",
        )

        engine = DeveloperAIEngine(
            policy=DeveloperAIEnginePolicy(
                project_root=str(self.root),
                allow_llm_fallback=False,
            )
        )

        result = engine.generate(
            {
                "path": str(self.target),
                "goal": "Unknown",
                "issue_type": "UNKNOWN",
            }
        )

        self.assertFalse(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "UNSUPPORTED_ISSUE"
        )

    def test_long_function_needs_model(
        self,
    ) -> None:

        self.target.write_text(
            "def run():\n"
            "    return True\n",
            encoding="utf-8",
        )

        engine = DeveloperAIEngine(
            policy=DeveloperAIEnginePolicy(
                project_root=str(self.root),
                allow_llm_fallback=True,
            )
        )

        result = engine.generate(
            {
                "path": str(self.target),
                "goal": "Refactor",
                "issue_type": "LONG_FUNCTION",
            }
        )

        self.assertFalse(
            result["success"]
        )

        self.assertIn(
            result["status"],
            {"MODEL_UNAVAILABLE","MODEL_ERROR"}
        )


if __name__ == "__main__":
    unittest.main()
