from __future__ import annotations

from pathlib import Path
import unittest

from app.gui.client_input_policy import should_block_client_input


class B1501ConfirmationRevisionInputTests(unittest.TestCase):
    def test_busy_window_allows_natural_revision_when_confirmation_is_pending(self) -> None:
        self.assertFalse(
            should_block_client_input(
                presenter_busy=True,
                has_pending_confirmation=True,
            )
        )

    def test_busy_window_still_blocks_unrelated_second_task(self) -> None:
        self.assertTrue(
            should_block_client_input(
                presenter_busy=True,
                has_pending_confirmation=False,
            )
        )

    def test_idle_window_accepts_normal_commands(self) -> None:
        self.assertFalse(
            should_block_client_input(
                presenter_busy=False,
                has_pending_confirmation=False,
            )
        )

    def test_client_window_uses_pending_confirmation_policy(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "gui"
            / "client_experience_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn("should_block_client_input", source)
        self.assertIn("has_pending_confirmation", source)
        self.assertNotIn(
            'confirmations = {"tak", "nie", "wykonaj", "anuluj", "potwierdzam"}',
            source,
        )


if __name__ == "__main__":
    unittest.main()
