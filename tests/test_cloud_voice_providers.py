from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import wave

from app.voice.cloud_voice_engine import (
    CloudVoiceConfig,
    CloudVoiceEngine,
    requested_cloud_provider,
)
from app.voice.environment import load_voice_environment
from app.voice.tts_runtime import _default_engine_factory


class _Response:
    def __init__(self, audio: bytes, status: int = 200) -> None:
        self.audio = audio
        self.status_code = status
        self.closed = False

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.audio[:2]
        yield self.audio[2:]

    def close(self) -> None:
        self.closed = True


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class CloudVoiceProviderTests(unittest.TestCase):
    def test_local_voice_remains_default_without_opt_in(self) -> None:
        self.assertEqual(requested_cloud_provider(environment={}), "")
        self.assertEqual(
            requested_cloud_provider(
                "CHATTERBOX_MULTILINGUAL_V3",
                environment={"JARVIS_OS_VOICE_PROVIDER": "cartesia"},
            ),
            "CARTESIA",
        )
        self.assertEqual(
            requested_cloud_provider(
                "PYTTSX3_DEFAULT",
                environment={"JARVIS_OS_VOICE_PROVIDER": "elevenlabs"},
            ),
            "",
        )

    def test_provider_requires_key_and_valid_voice_id(self) -> None:
        incomplete = CloudVoiceConfig.from_environment(
            "CARTESIA",
            environment={"CARTESIA_API_KEY": "secret"},
        )
        self.assertFalse(incomplete.is_configured)
        complete = CloudVoiceConfig.from_environment(
            "ELEVENLABS",
            environment={
                "ELEVENLABS_API_KEY": "secret-value",
                "ELEVENLABS_VOICE_ID": "voice_123",
            },
        )
        self.assertTrue(complete.is_configured)
        self.assertNotIn("secret-value", repr(complete))

    def test_cartesia_uses_current_bearer_api_and_writes_bounded_wave(self) -> None:
        response = _Response(b"\x00\x00" * 256)
        session = _Session(response)
        config = CloudVoiceConfig.from_environment(
            "CARTESIA",
            environment={
                "CARTESIA_API_KEY": "cartesia-secret",
                "CARTESIA_VOICE_ID": "voice_123",
            },
        )
        with TemporaryDirectory() as temporary:
            engine = CloudVoiceEngine(
                config, project_root=temporary, session=session
            )
            with patch.object(engine, "_play") as play:
                engine.say("System gotowy")
                engine.runAndWait()
            output = play.call_args.args[0]
            with wave.open(str(output), "rb") as audio:
                self.assertEqual(audio.getframerate(), 24_000)
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertEqual(audio.getnchannels(), 1)
        url, request = session.calls[0]
        self.assertEqual(url, "https://api.cartesia.ai/tts/bytes")
        self.assertEqual(
            request["headers"]["Authorization"], "Bearer cartesia-secret"
        )
        self.assertEqual(request["headers"]["Cartesia-Version"], "2026-03-01")
        self.assertEqual(request["json"]["language"], "pl")
        self.assertNotIn("cartesia-secret", str(request["json"]))
        self.assertTrue(response.closed)

    def test_elevenlabs_uses_pcm_and_never_places_key_in_url_or_payload(self) -> None:
        session = _Session(_Response(b"\x00\x00" * 64))
        config = CloudVoiceConfig.from_environment(
            "ELEVENLABS",
            environment={
                "ELEVENLABS_API_KEY": "eleven-secret",
                "ELEVENLABS_VOICE_ID": "voice_abc",
            },
        )
        with TemporaryDirectory() as temporary:
            engine = CloudVoiceEngine(
                config, project_root=temporary, session=session
            )
            with patch.object(engine, "_play"):
                engine.say("Dzień dobry")
                engine.runAndWait()
        url, request = session.calls[0]
        self.assertTrue(url.endswith("/voice_abc"))
        self.assertNotIn("eleven-secret", url)
        self.assertEqual(request["params"]["output_format"], "pcm_24000")
        self.assertEqual(request["headers"]["xi-api-key"], "eleven-secret")
        self.assertNotIn("eleven-secret", str(request["json"]))

    def test_factory_uses_cloud_only_when_complete_and_falls_back_locally(self) -> None:
        complete = {
            "JARVIS_OS_VOICE_PROVIDER": "CARTESIA",
            "CARTESIA_API_KEY": "secret",
            "CARTESIA_VOICE_ID": "voice_123",
        }
        fake_cloud = object()
        with patch.dict(os.environ, complete, clear=True), patch(
            "app.voice.cloud_voice_engine.CloudVoiceEngine.from_environment",
            return_value=fake_cloud,
        ), patch(
            "app.voice.cloud_voice_engine.CloudVoiceEngine.is_available",
            return_value=True,
        ):
            self.assertIs(
                _default_engine_factory(
                    neural_enabled=False,
                    engine_name="CHATTERBOX_MULTILINGUAL_V3",
                ),
                fake_cloud,
            )

        local = object()
        incomplete = {"JARVIS_OS_VOICE_PROVIDER": "ELEVENLABS"}
        with patch.dict(os.environ, incomplete, clear=True), patch(
            "app.voice.cloud_voice_engine.CloudVoiceEngine.is_available",
            return_value=False,
        ), patch(
            "app.voice.onecore_engine.WindowsOneCoreEngine.is_available",
            return_value=False,
        ), patch("app.voice.tts_runtime.pyttsx3.init", return_value=local):
            self.assertIs(
                _default_engine_factory(
                    neural_enabled=False,
                    engine_name="CHATTERBOX_MULTILINGUAL_V3",
                ),
                local,
            )

    def test_local_voice_file_is_allow_listed_and_does_not_override_process(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir()
            (config / "voice.env").write_text(
                "\n".join((
                    "JARVIS_OS_VOICE_PROVIDER=CARTESIA",
                    "CARTESIA_API_KEY=file-secret",
                    "UNSAFE_VALUE=blocked",
                )),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ, {"CARTESIA_API_KEY": "process-secret"}, clear=True
            ):
                loaded = load_voice_environment(root)
                self.assertEqual(os.environ["CARTESIA_API_KEY"], "process-secret")
                self.assertEqual(os.environ["JARVIS_OS_VOICE_PROVIDER"], "CARTESIA")
                self.assertNotIn("UNSAFE_VALUE", os.environ)
        self.assertEqual(loaded, ("JARVIS_OS_VOICE_PROVIDER",))

    def test_invalid_audio_trips_runtime_fallback(self) -> None:
        session = _Session(_Response(b"bad"))
        config = CloudVoiceConfig.from_environment(
            "ELEVENLABS",
            environment={
                "ELEVENLABS_API_KEY": "secret",
                "ELEVENLABS_VOICE_ID": "voice_abc",
            },
        )
        with TemporaryDirectory() as temporary:
            engine = CloudVoiceEngine(
                config, project_root=temporary, session=session
            )
            engine.say("Test")
            with self.assertRaisesRegex(RuntimeError, "nieprawidłowe audio"):
                engine.runAndWait()


if __name__ == "__main__":
    unittest.main()
