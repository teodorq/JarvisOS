from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.assistant.controller import PersonalAssistantController
from app.assistant.daily_work import DailyWorkService


class B100DailyWorkCenterTests(unittest.TestCase):

    def test_multistep_workflow_tracks_visible_progress(self) -> None:
        with TemporaryDirectory() as temporary:
            service = DailyWorkService(temporary)
            workflow = service.create_workflow(
                "Start dnia",
                ["Status systemu", "Pokaż zadania", "Raport"],
            )
            service.start("Start dnia")
            service.complete_current_step()
            status = service.status()
            active = status["active_workflow"]
            self.assertEqual(workflow["title"], "Start dnia")
            self.assertEqual(active["completed_steps"], 1)
            self.assertEqual(active["total_steps"], 3)
            self.assertEqual(active["next_step"], "Pokaż zadania")

    def test_reminder_and_report_are_local(self) -> None:
        with TemporaryDirectory() as temporary:
            service = DailyWorkService(temporary)
            service.add_reminder("Sprawdź raport", minutes=0)
            self.assertEqual(len(service.due_reminders()), 1)
            report = service.export_report()
            path = Path(report["path"])
            self.assertTrue(path.is_file())
            self.assertTrue(
                path.resolve().is_relative_to(
                    Path(temporary).resolve()
                )
            )

    def test_controller_parses_workflow_command(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            response = controller.handle(
                "Utwórz zadanie wieloetapowe Start dnia: Status; Zadania; Raport"
            )
            self.assertIn("utworzono zadanie", response)
            status = controller.daily.status()
            self.assertEqual(status["workflow_count"], 1)

    def test_export_report_command_is_mutating(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            thought = controller.plan("Eksportuj raport codziennej pracy")
            self.assertFalse(thought["read_only"])


if __name__ == "__main__":
    unittest.main()
