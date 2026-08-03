from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.stability.performance_center import RuntimePerformanceCenter


class B112PerformanceCenterTests(unittest.TestCase):
    def test_probe_records_bounded_metrics(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "app/ai/brain.py"
            source.parent.mkdir(parents=True)
            source.write_text("class Brain: pass\n", encoding="utf-8")
            result = RuntimePerformanceCenter(root).probe()
            self.assertIn(result["status"], {"HEALTHY", "WARNING"})
            self.assertGreaterEqual(result["score"], 0)
            self.assertGreaterEqual(result["json_roundtrip_ms"], 0)

    def test_compaction_only_prunes_stability_history(self) -> None:
        with TemporaryDirectory() as temporary:
            center = RuntimePerformanceCenter(temporary)
            for _ in range(24):
                center.probe()
            result = center.compact()
            self.assertEqual(result["removed"], 4)
            self.assertEqual(center.status()["snapshot_count"], 20)

    def test_status_before_probe_is_ready(self) -> None:
        with TemporaryDirectory() as temporary:
            status = RuntimePerformanceCenter(temporary).status()
            self.assertEqual(status["status"], "RUNTIME_PERFORMANCE_READY")
            self.assertEqual(status["latest_status"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
