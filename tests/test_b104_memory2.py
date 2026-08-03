from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.intelligence.memory_index import MemoryIndexV2


class B104Memory2Tests(unittest.TestCase):

    def test_duplicate_memory_updates_one_entry(self) -> None:
        with TemporaryDirectory() as temporary:
            service = MemoryIndexV2(temporary)
            first = service.remember("Używaj pełnych plików", category="project")
            second = service.remember("Używaj pełnych plików", category="project")
            self.assertEqual(first["memory_id"], second["memory_id"])
            self.assertEqual(service.status()["entry_count"], 1)

    def test_ranked_search_finds_relevant_memory(self) -> None:
        with TemporaryDirectory() as temporary:
            service = MemoryIndexV2(temporary)
            service.remember("JARVIS używa pełnych plików i paczek ZIP", tags=["jarvis"])
            service.remember("Kawa jest w kuchni")
            results = service.search("pełne pliki jarvis")
            self.assertIn("pełnych plików", results[0]["text"])
            self.assertGreater(results[0]["score"], 0)

    def test_memory_is_persistent_and_forgettable(self) -> None:
        with TemporaryDirectory() as temporary:
            entry = MemoryIndexV2(temporary).remember("Test pamięci")
            reloaded = MemoryIndexV2(temporary)
            self.assertEqual(reloaded.status()["entry_count"], 1)
            self.assertTrue(reloaded.forget(entry["memory_id"]))
            self.assertEqual(reloaded.status()["entry_count"], 0)


if __name__ == "__main__":
    unittest.main()
