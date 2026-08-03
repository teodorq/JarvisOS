from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.intelligence.brain_context import BrainContextV2, fold


class B102Brain2Tests(unittest.TestCase):

    def test_polish_text_is_folded_for_routing(self) -> None:
        self.assertEqual(fold("Pokaż pamięć i głos"), "pokaz pamiec i glos")

    def test_read_only_status_plan_has_no_confirmation(self) -> None:
        with TemporaryDirectory() as temporary:
            plan = BrainContextV2(temporary).plan("Pokaż status systemu")
            self.assertEqual(plan["intent"], "STATUS")
            self.assertEqual(plan["risk"], "READ_ONLY")
            self.assertFalse(plan["requires_confirmation"])

    def test_critical_command_is_explicitly_classified(self) -> None:
        with TemporaryDirectory() as temporary:
            plan = BrainContextV2(temporary).plan("Usuń wszystkie pliki projektu")
            self.assertEqual(plan["risk"], "CRITICAL")
            self.assertTrue(plan["requires_confirmation"])

    def test_vague_command_requests_clarification(self) -> None:
        with TemporaryDirectory() as temporary:
            plan = BrainContextV2(temporary).plan("zrób")
            self.assertTrue(plan["clarification"])

    def test_followup_reuses_last_command(self) -> None:
        with TemporaryDirectory() as temporary:
            service = BrainContextV2(temporary)
            service.plan("Otwórz notatnik")
            self.assertEqual(service.resolve_followup("kontynuuj"), "Otwórz notatnik")


if __name__ == "__main__":
    unittest.main()
