from __future__ import annotations

import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from app.ai.project_director.director_engine import DirectorEngine
from app.ai.project_director.director_execution_service import DirectorExecutionService
from app.ai.executive_ai.executive_engine import ExecutiveEngine
from app.ai.executive_ai.executive_execution_service import ExecutiveExecutionService
from app.ai.meta_executive.meta_engine import MetaEngine
from app.ai.meta_executive.meta_execution_service import MetaExecutionService


class AuditA321EngineExecutionSplitTests(unittest.TestCase):

    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_engine_execution_services_are_stateless(self) -> None:
        services = (
            DirectorExecutionService(),
            ExecutiveExecutionService(),
            MetaExecutionService(),
        )
        self.assertTrue(all(vars(service) == {} for service in services))

    def test_large_execution_methods_are_thin_wrappers(self) -> None:
        files = {
            "app/ai/project_director/director_engine.py": (
                "run_iteration", "_execute_selected_module",
            ),
            "app/ai/executive_ai/executive_engine.py": (
                "run_phase", "_execute_delegation",
            ),
            "app/ai/meta_executive/meta_engine.py": (
                "run_cycle", "_execute_selected_layer",
            ),
        }
        failures = []
        for relative, names in files.items():
            tree = ast.parse((self.root / relative).read_text(encoding="utf-8"))
            cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
            methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
            for name in names:
                length = methods[name].end_lineno - methods[name].lineno + 1
                if length > 14:
                    failures.append(f"{relative}:{name}={length}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_engine_files_are_reduced(self) -> None:
        limits = {
            "app/ai/project_director/director_engine.py": 510,
            "app/ai/executive_ai/executive_engine.py": 510,
            "app/ai/meta_executive/meta_engine.py": 520,
        }
        failures=[]
        for relative, limit in limits.items():
            lines=len((self.root/relative).read_text(encoding="utf-8").splitlines())
            if lines >= limit: failures.append(f"{relative}: {lines} >= {limit}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_director_iteration_behavior_is_preserved(self) -> None:
        engine = DirectorEngine.__new__(DirectorEngine)
        engine._get_state = MagicMock(return_value=None)
        result = engine.run_iteration("director-1")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertEqual(result["director_id"], "director-1")

    def test_executive_phase_behavior_is_preserved(self) -> None:
        engine = ExecutiveEngine.__new__(ExecutiveEngine)
        engine._get_state = MagicMock(return_value=None)
        result = engine.run_phase("executive-1")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertEqual(result["executive_id"], "executive-1")

    def test_meta_cycle_behavior_is_preserved(self) -> None:
        engine = MetaEngine.__new__(MetaEngine)
        engine._get_state = MagicMock(return_value=None)
        result = engine.run_cycle("meta-1")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertEqual(result["meta_id"], "meta-1")


if __name__ == "__main__":
    unittest.main()
