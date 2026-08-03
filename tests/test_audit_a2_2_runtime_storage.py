from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.agent.goal_manager import GoalManager
from app.agent.self_reflection import SelfReflection
from app.code.symbol_index import SymbolIndex
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths
from app.memory.memory import Memory


class FakeScanner:

    def list_python_files(
        self,
    ):
        return [
            "app/sample.py",
        ]


class FakeParser:

    def parse_file(
        self,
        path,
    ):
        return {
            "classes": [
                {
                    "name": "Sample",
                    "line": 1,
                    "methods": [],
                }
            ],
            "functions": [],
            "imports": [],
        }


class AuditA22RuntimeStorageTests(unittest.TestCase):

    def test_project_paths_expose_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = ProjectPaths.from_value(
                temp
            )

            self.assertEqual(
                paths.main_memory_file,
                Path(temp).resolve()
                / "data/memory.json",
            )
            self.assertEqual(
                paths.symbol_index_cache,
                Path(temp).resolve()
                / "data/cache/symbol_index.json",
            )

    def test_json_store_saves_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data/state.json"
            store = JsonStore(
                path,
                dict,
            )
            store.save(
                {
                    "value": 7,
                }
            )

            self.assertEqual(
                store.load(),
                {
                    "value": 7,
                },
            )
            self.assertEqual(
                list(
                    path.parent.glob(
                        "*.tmp"
                    )
                ),
                [],
            )

    def test_json_store_returns_default_for_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            path.write_text(
                "{broken",
                encoding="utf-8",
            )
            store = JsonStore(
                path,
                lambda: {
                    "safe": True,
                },
            )

            self.assertEqual(
                store.load(),
                {
                    "safe": True,
                },
            )

    def test_memory_uses_resolved_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            memory = Memory(
                project_root=temp
            )
            memory.remember_note(
                "test"
            )

            restored = Memory(
                project_root=temp
            )

            self.assertEqual(
                restored.search_notes(
                    "test"
                )[0]["text"],
                "test",
            )

    def test_goal_manager_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manager = GoalManager(
                project_root=temp
            )
            manager.start_goal(
                "Audit"
            )
            manager.add_note(
                "note"
            )

            restored = GoalManager(
                project_root=temp
            )

            self.assertEqual(
                restored.current_goal,
                "Audit",
            )
            self.assertEqual(
                restored.notes,
                [
                    "note",
                ],
            )

    def test_reflection_recovers_from_corrupt_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = (
                Path(temp)
                / "data/memory/reflections.json"
            )
            path.parent.mkdir(
                parents=True
            )
            path.write_text(
                "not-json",
                encoding="utf-8",
            )

            reflection = SelfReflection(
                project_root=temp
            )

            self.assertEqual(
                reflection.history,
                [],
            )

    def test_symbol_index_uses_runtime_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            index = SymbolIndex(
                project_root=temp,
                scanner=FakeScanner(),
                parser=FakeParser(),
            )
            built = index.build()

            self.assertEqual(
                built["classes"][0]["name"],
                "Sample",
            )
            self.assertTrue(
                index.cache_file.is_file()
            )

            restored = SymbolIndex(
                project_root=temp,
                scanner=FakeScanner(),
                parser=FakeParser(),
            )

            self.assertEqual(
                restored.get_index(),
                built,
            )

    def test_runtime_json_is_valid_after_repeated_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            memory = Memory(
                project_root=temp
            )

            for index in range(20):
                memory.add_history(
                    f"user-{index}",
                    f"jarvis-{index}",
                )

            with memory.memory_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(
                    file
                )

            self.assertEqual(
                len(
                    data["history"]
                ),
                20,
            )


if __name__ == "__main__":
    unittest.main()
