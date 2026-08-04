from __future__ import annotations

import os
from pathlib import Path
import unittest

from app.voice.onecore_engine import OneCoreVoice, WindowsOneCoreEngine
from app.voice.tts_runtime import SerializedTTS


class _VoiceEngine:
    def getProperty(self, name: str):  # noqa: N802
        if name != "voices":
            return None
        return [
            OneCoreVoice("paulina", "Paulina", ["pl-PL"], "Female"),
            OneCoreVoice("adam", "Adam", ["pl-PL"], "Male"),
            OneCoreVoice("david", "David", ["en-US"], "Male"),
        ]


class TestB3101OneCoreVoice(unittest.TestCase):
    def test_exact_gender_match_prefers_polish_adam(self) -> None:
        runtime = SerializedTTS.__new__(SerializedTTS)
        runtime.language = "pl-PL"
        runtime.preferred_gender = "Male"
        self.assertEqual(runtime._preferred_voice_id(_VoiceEngine()), "adam")

    @unittest.skipUnless(os.name == "nt", "OneCore is a Windows service")
    def test_installed_onecore_has_polish_male_voice(self) -> None:
        voices = WindowsOneCoreEngine.available_voices()
        has_polish_male = any(
            voice.languages == ["pl-PL"] and voice.gender == "Male"
            for voice in voices
        )
        if not has_polish_male:
            self.skipTest(
                "Polish male OneCore voice is not installed."
            )
        self.assertTrue(WindowsOneCoreEngine.is_available())

    def test_pitch_is_clamped_to_a_safe_local_range(self) -> None:
        engine = WindowsOneCoreEngine()
        engine.setProperty("pitch", 0.2)
        self.assertEqual(engine.getProperty("pitch"), 0.7)
        engine.setProperty("pitch", 1.8)
        self.assertEqual(engine.getProperty("pitch"), 1.2)

    def test_helper_accepts_only_data_arguments(self) -> None:
        source = Path("app/voice/onecore_speak.ps1").read_text(encoding="utf-8")
        self.assertIn("TextBase64", source)
        self.assertIn("VoiceId", source)
        self.assertIn("Pitch", source)
        self.assertIn("AudioPitch", source)
        self.assertNotIn("Invoke-Expression", source)


if __name__ == "__main__":
    unittest.main()
