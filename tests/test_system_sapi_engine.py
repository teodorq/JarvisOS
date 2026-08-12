from __future__ import annotations

import os
from pathlib import Path
import unittest

from app.voice.system_sapi_engine import WindowsSystemSapiEngine


class WindowsSystemSapiEngineTests(unittest.TestCase):
    def test_properties_are_bounded(self) -> None:
        engine = WindowsSystemSapiEngine.__new__(WindowsSystemSapiEngine)
        engine._rate = 170
        engine._volume = 1.0
        engine.setProperty("rate", 999)
        engine.setProperty("volume", -5)
        self.assertEqual(engine.getProperty("rate"), 240)
        self.assertEqual(engine.getProperty("volume"), 0.0)

    def test_helper_uses_data_protocol_without_dynamic_code(self) -> None:
        source = Path("app/voice/system_sapi_worker.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("FromBase64String", source)
        self.assertIn("SpeechSynthesizer", source)
        self.assertIn("ReadLine", source)
        self.assertNotIn("Invoke-Expression", source)

    @unittest.skipUnless(
        os.name == "nt"
        and os.environ.get("GITHUB_ACTIONS", "").casefold() != "true",
        "SAPI requires an interactive Windows audio session",
    )
    def test_worker_starts_and_stays_ready(self) -> None:
        engine = WindowsSystemSapiEngine()
        try:
            self.assertIsNotNone(engine._process)
            self.assertIsNone(engine._process.poll())
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
