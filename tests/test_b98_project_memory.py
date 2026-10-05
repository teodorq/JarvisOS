from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.assistant.project_memory import ProjectMemoryService


class B98ProjectMemoryTests(unittest.TestCase):

    def test_projects_preferences_and_interrupted_work_are_persistent(self) -> None:
        with TemporaryDirectory() as temporary:
            service = ProjectMemoryService(temporary)
            project = service.remember_project(
                "JARVIS OS",
                path="C:\\JarvisAI",
            )
            service.set_preference("odpowiedzi", "krótkie")
            task = service.interrupt_task(
                "Dopracuj Vision",
                state={"step": 3},
            )

            reloaded = ProjectMemoryService(temporary)
            status = reloaded.status()
            self.assertEqual(status["project_count"], 1)
            self.assertEqual(status["active_project"]["name"], "JARVIS OS")
            self.assertEqual(reloaded.get_preference("odpowiedzi"), "krótkie")
            self.assertEqual(status["interrupted_count"], 1)
            self.assertEqual(status["last_interrupted"]["task_id"], task["task_id"])
            self.assertEqual(project["path"], "C:\\JarvisAI")

    def test_resume_consumes_latest_interrupted_task(self) -> None:
        with TemporaryDirectory() as temporary:
            service = ProjectMemoryService(temporary)
            service.interrupt_task("Pierwsze")
            service.interrupt_task("Drugie")
            resumed = service.resume_last_task()
            self.assertEqual(resumed["title"], "Drugie")
            self.assertEqual(service.status()["interrupted_count"], 1)

    def test_personal_facts_are_bounded_persistent_and_removable(self) -> None:
        with TemporaryDirectory() as temporary:
            service = ProjectMemoryService(temporary)
            first = service.remember_personal_fact("Lubię kawę")
            service.remember_personal_fact("Wolę krótkie odpowiedzi")

            reloaded = ProjectMemoryService(temporary)
            facts = reloaded.list_preferences(category="personal_fact")
            self.assertEqual(len(facts), 2)
            self.assertEqual(reloaded.find_personal_facts("kawie")[0]["value"], "Lubię kawę")
            self.assertTrue(reloaded.remove_preference(first["key"]))
            self.assertEqual(len(reloaded.list_preferences(category="personal_fact")), 1)

    def test_regular_preferences_are_not_personal_facts(self) -> None:
        with TemporaryDirectory() as temporary:
            service = ProjectMemoryService(temporary)
            service.set_preference("odpowiedzi", "krótkie")
            self.assertEqual(service.list_preferences(category="personal_fact"), [])

    def test_exact_fact_match_wins_over_similar_facts(self) -> None:
        with TemporaryDirectory() as temporary:
            service = ProjectMemoryService(temporary)
            service.remember_personal_fact("Lubię kawę")
            service.remember_personal_fact("Lubię herbatę")

            matches = service.find_personal_facts("lubię kawę")
            self.assertEqual([item["value"] for item in matches], ["Lubię kawę"])


if __name__ == "__main__":
    unittest.main()
