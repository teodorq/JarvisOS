from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.assistant.voice_runtime import VoiceRuntimeService
from app.voice.neural_engine import LocalNeuralVoiceEngine
from app.voice.tts_runtime import SerializedTTS


class _TestEngine:
    supports_pitch = False

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[str] = []
        self.stopped = False

    def setProperty(self, _name, _value):  # noqa: N802
        return None

    def getProperty(self, name):  # noqa: N802
        return [] if name == "voices" else None

    def say(self, message) -> None:
        self.messages.append(str(message))

    def runAndWait(self) -> None:  # noqa: N802
        if self.fail:
            raise RuntimeError("primary failed")

    def stop(self) -> None:
        self.stopped = True


class TestB311B320NeuralVoice(unittest.TestCase):
    def test_release_manifest_closes_every_stage(self) -> None:
        manifest = json.loads(
            Path("config/b311_b320_neural_voice.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            list(manifest["stages"]),
            [f"B{number}" for number in range(311, 321)],
        )
        self.assertTrue(all(
            str(value).endswith(("READY", "VERIFIED"))
            for value in manifest["stages"].values()
        ))

    def test_reference_hash_and_local_privacy_are_explicit(self) -> None:
        manifest = json.loads(
            Path("config/b311_b320_neural_voice.json").read_text(encoding="utf-8")
        )
        reference = Path(manifest["voice"]["reference_audio"])
        digest = hashlib.sha256(reference.read_bytes()).hexdigest().upper()
        self.assertEqual(digest, manifest["voice"]["reference_sha256"])
        self.assertTrue(manifest["privacy"]["reference_stays_local"])
        self.assertFalse(manifest["privacy"]["cloud_voice_api"])
        self.assertTrue(manifest["privacy"]["generated_audio_watermarked"])

    def test_voice_policy_migrates_to_neural_with_native_fallback(self) -> None:
        with TemporaryDirectory() as temporary:
            settings = VoiceRuntimeService(temporary).settings()
            status = VoiceRuntimeService(temporary).status()
        self.assertEqual(settings["version"], "2.3")
        self.assertEqual(settings["voice_engine"], "CHATTERBOX_MULTILINGUAL_V3")
        self.assertTrue(settings["neural_enabled"])
        self.assertEqual(status["fallback_engine"], "WINDOWS_ONECORE")

    @unittest.skipUnless(os.name == "nt", "Neural runtime targets Windows")
    def test_availability_requires_complete_isolated_runtime(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            package = root / "runtime/voice_env/Lib/site-packages/chatterbox"
            python = root / "runtime/voice_env/Scripts/python.exe"
            worker = root / "tools/voice_runtime/chatterbox_worker.py"
            reference = root / "assets/voice/references/reference.mp3"
            for directory in (config, package, python.parent, worker.parent, reference.parent):
                directory.mkdir(parents=True, exist_ok=True)
            (config / "b311_b320_neural_voice.json").write_text(
                json.dumps({"voice": {
                    "enabled": True,
                    "reference_audio": "assets/voice/references/reference.mp3",
                }}),
                encoding="utf-8",
            )
            python.touch()
            worker.touch()
            reference.write_bytes(b"reference")
            self.assertTrue(LocalNeuralVoiceEngine.is_available(root))
            failure = root / "runtime/voice_output/neural_failed.flag"
            failure.parent.mkdir(parents=True)
            failure.touch()
            self.assertFalse(LocalNeuralVoiceEngine.is_available(root))

    def test_failed_primary_replays_same_text_on_fallback(self) -> None:
        primary = _TestEngine(fail=True)
        fallback = _TestEngine()
        engines = iter((primary, fallback))
        errors: list[Exception] = []
        runtime = SerializedTTS(
            engine_factory=lambda: next(engines),
            on_error=errors.append,
        )
        try:
            self.assertTrue(runtime.say("System gotowy"))
            self.assertTrue(runtime.wait_until_idle(timeout=2.0))
        finally:
            runtime.close()
        self.assertEqual(primary.messages, ["System gotowy"])
        self.assertEqual(fallback.messages, ["System gotowy"])
        self.assertEqual(len(errors), 1)

    def test_worker_is_bounded_and_never_uploads_reference(self) -> None:
        source = Path("tools/voice_runtime/chatterbox_worker.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('language_id=language', source)
        self.assertIn('audio_prompt_path=None', source)
        self.assertIn('watermarked', source)
        self.assertIn('output_root not in output.parents', source)
        self.assertNotIn('requests.post', source)
        self.assertNotIn('Invoke-Expression', source)


if __name__ == "__main__":
    unittest.main()
