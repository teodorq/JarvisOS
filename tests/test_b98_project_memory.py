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


if __name__ == "__main__":
    unittest.main()
