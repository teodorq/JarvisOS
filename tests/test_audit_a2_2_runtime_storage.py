from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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

    def test_json_store_update_does_not_lose_concurrent_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = JsonStore(
                Path(temp) / "state.json",
                lambda: {"count": 0},
            )

            def increment() -> None:
                store.update(
                    lambda value: {"count": int(value["count"]) + 1}
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda _index: increment(), range(80)))

            self.assertEqual(store.load(), {"count": 80})

    def test_json_store_update_keeps_file_when_transform_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = JsonStore(Path(temp) / "state.json", dict)
            store.save({"value": "safe"})

            def fail(_value: object) -> object:
                raise ValueError("stop")

            with self.assertRaises(ValueError):
                store.update(fail)

            self.assertEqual(store.load(), {"value": "safe"})

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

    def test_memory_keeps_all_concurrent_history_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            memory_file = Path(temp) / "data" / "memory.json"
            memories = [Memory(memory_file=memory_file) for _index in range(8)]

            def add(index: int) -> None:
                memories[index % len(memories)].add_history(
                    f"user-{index}",
                    f"jarvis-{index}",
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(add, range(80)))

            restored = Memory(memory_file=memory_file)._load()
            self.assertEqual(len(restored["history"]), 80)
            self.assertEqual(
                {item["user"] for item in restored["history"]},
                {f"user-{index}" for index in range(80)},
            )


if __name__ == "__main__":
    unittest.main()
