from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest
import wave

from app.voice.neural_engine import LocalNeuralVoiceEngine
from app.voice.speech_director import PolishSpeechDirector
from tools.voice_runtime.voice_mastering import PROFILE_PAUSES, profile_parameters


class TestB351B360VoiceDirection(unittest.TestCase):
    def test_release_manifest_closes_every_stage(self) -> None:
        manifest = json.loads(
            Path("config/b351_b360_voice_direction.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            list(manifest["stages"]),
            [f"B{number}" for number in range(351, 361)],
        )
        self.assertTrue(all(
            str(value).endswith(("READY", "VERIFIED"))
            for value in manifest["stages"].values()
        ))

    def test_director_preserves_simple_natural_sentence(self) -> None:
        directed = PolishSpeechDirector().direct("System gotowy")
        self.assertEqual(directed.text, "System gotowy")
        self.assertEqual(directed.profile, "result")

    def test_director_removes_internal_labels_and_bounds_speech(self) -> None:
        raw = (
            "B126 Status techniczny: COMPLETED. Plik C:\\JarvisAI\\app\\voice.py "
            "https://example.test/secret " + ("ważny opis " * 80)
        )
        directed = PolishSpeechDirector().direct(raw)
        self.assertNotIn("B126", directed.text)
        self.assertNotIn("C:\\", directed.text)
        self.assertNotIn("https://", directed.text)
        self.assertLessEqual(len(directed.text), 520)

    def test_profiles_have_bounded_distinct_delivery(self) -> None:
        values = {
            name: profile_parameters(name, 0.58, 0.72)
            for name in PROFILE_PAUSES
        }
        self.assertEqual(values["warning"][0], "warning")
        self.assertGreater(values["warning"][3], values["result"][3])
        for _, exaggeration, temperature, pause in values.values():
            self.assertGreaterEqual(exaggeration, 0.2)
            self.assertLessEqual(exaggeration, 1.0)
            self.assertGreaterEqual(temperature, 0.25)
            self.assertLessEqual(temperature, 1.2)
            self.assertGreater(pause, 0.0)

    def test_neural_config_loads_identity_safe_mastering(self) -> None:
        config = LocalNeuralVoiceEngine._load_config(Path.cwd())
        self.assertEqual(config["mastering"]["version"], "b360")
        safety = json.loads(
            Path("config/b351_b360_voice_direction.json").read_text(
                encoding="utf-8"
            )
        )["safety"]
        self.assertTrue(safety["no_pitch_shift"])
        self.assertFalse(safety["cloud_voice_api"])

    def test_b360_preview_is_real_bounded_pcm_audio(self) -> None:
        manifest = json.loads(
            Path("config/b351_b360_voice_direction.json").read_text(
                encoding="utf-8"
            )
        )
        preview = manifest["preview"]
        path = Path(preview["path"])
        self.assertTrue(path.is_file())
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            preview["sha256"],
        )
        with wave.open(str(path), "rb") as audio:
            self.assertEqual(audio.getframerate(), preview["sample_rate"])
            self.assertEqual(audio.getnchannels(), preview["channels"])
            self.assertEqual(audio.getsampwidth(), preview["sample_width_bytes"])
            self.assertGreater(audio.getnframes(), 24000)

    def test_worker_uses_profile_and_local_mastering_only(self) -> None:
        source = Path("tools/voice_runtime/chatterbox_worker.py").read_text(
            encoding="utf-8"
        )
        mastering = Path("tools/voice_runtime/voice_mastering.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("profile_parameters", source)
        self.assertIn("master_waveform", source)
        self.assertIn("speech_profile", source)
        self.assertNotIn("pitch_shift", mastering)
        self.assertNotIn("requests.", mastering)


if __name__ == "__main__":
    unittest.main()
