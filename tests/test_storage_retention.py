from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.core.storage_retention import (
    ScreenshotRetentionPolicy,
    enforce_screenshot_retention,
)


class ScreenshotRetentionTests(unittest.TestCase):
    @staticmethod
    def _file(root: Path, name: str, size: int, modified: datetime) -> Path:
        path = root / name
        path.write_bytes(b"x" * size)
        timestamp = modified.timestamp()
        os.utime(path, (timestamp, timestamp))
        return path

    def test_keeps_newest_and_applies_count_limit(self) -> None:
        now = datetime(2026, 10, 2, 12, 0)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5):
                self._file(
                    root,
                    f"screen_{index}.png",
                    10,
                    now - timedelta(minutes=index),
                )

            result = enforce_screenshot_retention(
                root,
                policy=ScreenshotRetentionPolicy(
                    max_files=3, max_total_bytes=1000, max_age_days=90
                ),
                now=now,
            )

            self.assertEqual(result["removed_files"], 2)
            self.assertEqual(result["kept_files"], 3)
            self.assertTrue((root / "screen_0.png").exists())

    def test_applies_age_and_total_size_limits(self) -> None:
        now = datetime(2026, 10, 2, 12, 0)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            newest = self._file(root, "newest.png", 80, now)
            self._file(root, "second.png", 50, now - timedelta(minutes=1))
            self._file(root, "old.png", 10, now - timedelta(days=100))

            result = enforce_screenshot_retention(
                root,
                policy=ScreenshotRetentionPolicy(
                    max_files=10, max_total_bytes=100, max_age_days=30
                ),
                now=now,
            )

            self.assertTrue(newest.exists())
            self.assertEqual(result["removed_files"], 2)
            self.assertEqual(result["removed_bytes"], 60)

    def test_ignores_unrelated_files_and_missing_directory(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            note = root / "note.txt"
            note.write_text("keep", encoding="utf-8")

            result = enforce_screenshot_retention(root)
            missing = enforce_screenshot_retention(root / "missing")

            self.assertTrue(note.exists())
            self.assertEqual(result["removed_files"], 0)
            self.assertEqual(missing["kept_files"], 0)


if __name__ == "__main__":
    unittest.main()
