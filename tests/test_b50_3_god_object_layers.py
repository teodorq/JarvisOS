from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.ai.architecture import (
    ArchitectureSmellAnalyzer,
    GodObjectDetector,
    LayerRule,
    LayerViolationDetector,
)


class GodObjectLayerTests(unittest.TestCase):

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

    def test_detects_god_object_with_many_responsibilities(self) -> None:
        methods = "\n".join(
            (
                f"    def task_{index}(self):\n"
                f"        self.value_{index} = {index}\n"
                f"        return self.value_{index}"
            )
            for index in range(6)
        )
        self.write(
            "app/service.py",
            f"class Service:\n{methods}\n",
        )

        detector = GodObjectDetector(
            method_threshold=3,
            attribute_threshold=3,
            dependency_threshold=99,
            responsibility_threshold=99,
            score_threshold=40.0,
        )
        report = ArchitectureSmellAnalyzer(
            self.root,
            god_object_detector=detector,
        ).analyze()

        self.assertEqual(len(report["god_objects"]), 1)
        self.assertEqual(
            report["god_objects"][0]["class_name"],
            "Service",
        )

    def test_small_class_is_not_god_object(self) -> None:
        self.write(
            "app/service.py",
            (
                "class Service:\n"
                "    def run(self):\n"
                "        return 1\n"
            ),
        )

        report = ArchitectureSmellAnalyzer(
            self.root,
        ).analyze()

        self.assertEqual(report["god_objects"], [])

    def test_detects_layer_violation(self) -> None:
        graph = {
            "app.core.engine": {
                "app.gui.window",
            },
            "app.gui.window": set(),
        }

        violations = LayerViolationDetector().detect(graph)

        self.assertEqual(len(violations), 1)
        self.assertEqual(
            violations[0].source_module,
            "app.core.engine",
        )
        self.assertEqual(
            violations[0].target_module,
            "app.gui.window",
        )

    def test_custom_layer_rule_is_supported(self) -> None:
        rules = (
            LayerRule(
                source_prefix="app.domain",
                forbidden_target_prefixes=(
                    "app.infrastructure",
                ),
            ),
        )
        graph = {
            "app.domain.orders": {
                "app.infrastructure.database",
            },
        }

        violations = LayerViolationDetector(
            rules=rules,
        ).detect(graph)

        self.assertEqual(len(violations), 1)

    def test_clean_graph_has_no_layer_violations(self) -> None:
        graph = {
            "app.gui.window": {
                "app.core.engine",
            },
            "app.core.engine": set(),
        }

        violations = LayerViolationDetector().detect(graph)

        self.assertEqual(violations, [])

    def test_smell_score_drops_and_recommendations_are_created(self) -> None:
        self.write(
            "app/core/engine.py",
            "from app.gui.window import Window\n",
        )
        self.write(
            "app/gui/window.py",
            "class Window:\n    pass\n",
        )

        report = ArchitectureSmellAnalyzer(
            self.root,
        ).analyze()

        self.assertLess(report["smell_score"], 100.0)
        self.assertTrue(report["recommendations"])


if __name__ == "__main__":
    unittest.main()
