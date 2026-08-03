from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.ai.architecture import ArchitectureAnalyzer


class ArchitectureCoreTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "app").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(
        self,
        relative_path: str,
        content: str,
    ) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_builds_dependency_graph_and_counts_modules(self) -> None:
        self.write(
            "app/a.py",
            "from app.b import value\n",
        )
        self.write(
            "app/b.py",
            "value = 1\n",
        )

        report = ArchitectureAnalyzer(self.root).analyze()

        self.assertEqual(report.modules_scanned, 2)
        self.assertEqual(report.dependency_count, 1)

    def test_detects_circular_dependency(self) -> None:
        self.write(
            "app/a.py",
            "from app.b import value\n",
        )
        self.write(
            "app/b.py",
            "from app.a import value\n",
        )

        report = ArchitectureAnalyzer(self.root).analyze()

        self.assertEqual(
            report.circular_dependencies,
            [["app.a", "app.b"]],
        )
        self.assertTrue(
            any(
                issue.code == "CIRCULAR_DEPENDENCY"
                for issue in report.issues
            )
        )

    def test_detects_large_file(self) -> None:
        self.write(
            "app/large.py",
            "\n".join(f"value_{index} = {index}" for index in range(15)),
        )

        report = ArchitectureAnalyzer(
            self.root,
            large_file_lines=10,
        ).analyze()

        self.assertEqual(len(report.large_files), 1)

    def test_detects_large_class(self) -> None:
        methods = "\n".join(
            f"    def method_{index}(self):\n        return {index}"
            for index in range(4)
        )
        self.write(
            "app/service.py",
            f"class Service:\n{methods}\n",
        )

        report = ArchitectureAnalyzer(
            self.root,
            large_class_methods=3,
        ).analyze()

        self.assertEqual(len(report.large_classes), 1)
        self.assertTrue(
            any(
                issue.code == "LARGE_CLASS"
                for issue in report.issues
            )
        )

    def test_architecture_score_drops_when_issues_exist(self) -> None:
        self.write(
            "app/large.py",
            "\n".join(f"value_{index} = {index}" for index in range(15)),
        )

        report = ArchitectureAnalyzer(
            self.root,
            large_file_lines=10,
        ).analyze()

        self.assertLess(report.architecture_score, 100.0)
        self.assertGreaterEqual(report.architecture_score, 0.0)


if __name__ == "__main__":
    unittest.main()
