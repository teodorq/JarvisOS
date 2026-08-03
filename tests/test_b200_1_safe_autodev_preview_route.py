from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.software_engineer.safe_autodev_preview_command import (
    execute_safe_autodev_preview,
    plan_safe_autodev_preview,
)
from app.gui.command_safety import is_safe_read_only_thought


COMMAND = (
    "Przeanalizuj projekt i zaproponuj jedną bezpieczną poprawę, "
    "ale niczego jeszcze nie zmieniaj."
)


class _Brain:
    def __init__(self, root: str) -> None:
        self.project_root = root
        self.cognitive = MagicMock()
        self.research_service = MagicMock()
        self.research_service.can_handle.return_value = True
        self.remembered = []

    def _remember_execution(self, command, result):
        self.remembered.append((command, result))


class B2001SafeAutoDevPreviewRouteTests(unittest.TestCase):
    def test_exact_owner_command_routes_before_legacy_research(self) -> None:
        with TemporaryDirectory() as directory:
            brain = _Brain(directory)
            thought = BrainCommandRouter().think(brain, COMMAND)
        self.assertEqual(thought["handler"], "safe_autodev_preview")
        self.assertTrue(thought["read_only"])
        self.assertFalse(thought["requires_confirmation"])
        brain.research_service.can_handle.assert_not_called()
        brain.cognitive.after_plan.assert_called_once_with(thought)

    def test_read_only_preview_is_safe_without_confirmation(self) -> None:
        thought = plan_safe_autodev_preview(SimpleNamespace(), COMMAND)
        self.assertIsNotNone(thought)
        self.assertTrue(is_safe_read_only_thought(thought))
        runtime_source = (
            Path(__file__).resolve().parents[1] / "app/gui/business_command_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn("is_safe_read_only_thought(thought)", runtime_source)

    def test_plain_project_analysis_keeps_legacy_route_available(self) -> None:
        self.assertIsNone(
            plan_safe_autodev_preview(
                SimpleNamespace(),
                "Przeanalizuj projekt i wygeneruj raport.",
            )
        )

    def test_execution_returns_one_concrete_proposal_and_changes_no_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "app"
            app.mkdir()
            target = app / "large_module.py"
            target.write_text(
                "\n".join(["value = 1"] * 700) + "\n",
                encoding="utf-8",
            )
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            brain = _Brain(directory)
            thought = plan_safe_autodev_preview(brain, COMMAND)
            result = execute_safe_autodev_preview(brain, thought)
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        self.assertIn("jedną bezpieczną poprawę", result)
        self.assertIn("Plik: app/large_module.py", result)
        self.assertIn("Nic nie zmieniłem", result)
        self.assertEqual(before, after)
        self.assertEqual(len(brain.remembered), 1)

    def test_router_execute_uses_read_only_scanner(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "app/sample.py").write_text(
                "\n".join(["value = 1"] * 450) + "\n",
                encoding="utf-8",
            )
            brain = _Brain(directory)
            thought = plan_safe_autodev_preview(brain, COMMAND)
            result = BrainCommandRouter().execute(brain, thought)
        self.assertIn("Propozycja:", result)
        self.assertIn("Nic nie zmieniłem", result)

    def test_no_candidate_is_honest_and_read_only(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "app/small.py").write_text("value = 1\n", encoding="utf-8")
            brain = _Brain(directory)
            result = execute_safe_autodev_preview(
                brain,
                plan_safe_autodev_preview(brain, COMMAND),
            )
        self.assertIn("nie znalazłem", result)
        self.assertIn("Nic nie zmieniłem", result)

    def test_source_bounds_and_markers(self) -> None:
        root = Path(__file__).resolve().parents[1]
        router = (root / "app/ai/brain_command_router.py").read_text(encoding="utf-8")
        preview = (
            root / "app/ai/software_engineer/safe_autodev_preview_command.py"
        ).read_text(encoding="utf-8")
        self.assertLess(len(router.splitlines()), 200)
        self.assertLess(len(preview.splitlines()), 150)
        self.assertIn("safe_autodev_preview", router)
        self.assertIn("Nic nie zmieniłem", preview)
        self.assertNotIn("write_text", preview)
        self.assertNotIn("dispatch_best", preview)


if __name__ == "__main__":
    unittest.main()
