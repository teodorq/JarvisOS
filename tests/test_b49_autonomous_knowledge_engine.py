from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.ai.knowledge import AutonomousKnowledgeEngine, KnowledgeReportFormatter


class AutonomousKnowledgeEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_builds_code_map_and_dependency_graph(self) -> None:
        self.write("app/a.py", "from app.b import helper\n\ndef run():\n    return helper()\n")
        self.write("app/b.py", "def helper():\n    return 1\n")
        report = AutonomousKnowledgeEngine().analyze_project(self.root)
        self.assertIn("app/a.py", report.code_map)
        self.assertIn("app.b", report.dependency_graph["app.a"])

    def test_detects_missing_tests(self) -> None:
        self.write("app/service.py", "class Service:\n    def run(self):\n        return True\n")
        report = AutonomousKnowledgeEngine().analyze_project(self.root)
        categories = {issue.category for issue in report.issues}
        self.assertIn("missing_test", categories)

    def test_matching_test_suppresses_missing_test_issue(self) -> None:
        self.write("app/service.py", "def run():\n    return True\n")
        self.write("tests/test_service.py", "def test_run():\n    assert True\n")
        report = AutonomousKnowledgeEngine().analyze_project(self.root)
        missing = [i for i in report.issues if i.category == "missing_test" and i.path == "app/service.py"]
        self.assertEqual([], missing)

    def test_detects_duplicate_functions(self) -> None:
        body = "def calculate(value):\n    a = value + 1\n    b = a * 2\n    c = b - 3\n    return c\n"
        self.write("app/one.py", body)
        self.write("app/two.py", body)
        report = AutonomousKnowledgeEngine().analyze_project(self.root)
        self.assertTrue(any(issue.category == "duplicate_code" for issue in report.issues))

    def test_generates_ranked_autodev_tasks_with_roi_and_risk(self) -> None:
        self.write("app/service.py", "def run():\n    return True\n")
        report = AutonomousKnowledgeEngine().analyze_project(self.root)
        tasks = AutonomousKnowledgeEngine().to_autodev_tasks(report)
        self.assertTrue(tasks)
        self.assertIn("roi", tasks[0])
        self.assertIn("risk", tasks[0])
        self.assertGreaterEqual(tasks[0]["priority"], tasks[-1]["priority"])

    def test_saves_json_report(self) -> None:
        self.write("app/service.py", "def run():\n    return True\n")
        engine = AutonomousKnowledgeEngine()
        report = engine.analyze_project(self.root)
        output = engine.save_report(report, self.root / "data" / "knowledge.json")
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report.python_files, payload["python_files"])
        self.assertIn("tasks", payload)

    def test_formats_human_readable_report(self) -> None:
        self.write("app/service.py", "def run():\n    return True\n")
        report = AutonomousKnowledgeEngine().analyze_project(self.root)
        text = KnowledgeReportFormatter().format_text(report)
        self.assertIn("AUTONOMOUS KNOWLEDGE REPORT", text)
        self.assertIn("Recommended tasks", text)


if __name__ == "__main__":
    unittest.main()
