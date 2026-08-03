from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import time
import types
import unittest

if importlib.util.find_spec("speech_recognition") is None:
    sys.modules["speech_recognition"] = types.ModuleType("speech_recognition")

from app.assistant.voice_runtime import VoiceCommandInterpreter
from app.voice.voice_listener import VoiceListener


class _FakeTTS:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bool]] = []
        self.speaking = False

    def say(self, text: str, *, replace_pending: bool = True) -> bool:
        self.messages.append((text, replace_pending))
        return True

    def interrupt(self) -> bool:
        return True

    def close(self) -> None:
        return None


def _listener_without_microphone() -> VoiceListener:
    listener = VoiceListener.__new__(VoiceListener)
    listener.interpreter = VoiceCommandInterpreter()
    listener.tts = _FakeTTS()
    listener._tts_echo = ""
    listener._tts_echo_deadline = 0.0
    listener.mode = "command"
    listener.last_wake_time = 0.0
    return listener


class B1452VoiceTurnHandoffTests(unittest.TestCase):

    def test_spoken_prompt_arms_echo_guard(self) -> None:
        listener = _listener_without_microphone()
        listener.say("Słucham")
        self.assertEqual(listener.tts.messages, [("Słucham", True)])
        self.assertTrue(listener._is_tts_echo("słucham"))
        self.assertEqual(listener.mode, "command")

    def test_echo_guard_expires_and_real_command_is_not_blocked(self) -> None:
        listener = _listener_without_microphone()
        listener.say("Słucham")
        listener._tts_echo_deadline = time.monotonic() - 0.01
        self.assertFalse(listener._is_tts_echo("słucham"))
        self.assertFalse(
            listener._is_tts_echo(
                "dodaj jutro trening o osiemnastej"
            )
        )

    def test_listener_waits_while_tts_is_speaking(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/voice/voice_listener.py"
        ).read_text(encoding="utf-8")
        self.assertIn("if self.tts.speaking:", source)
        self.assertIn("if self._is_tts_echo(normalized):", source)

    def test_voice_listener_remains_below_audit_limit(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/voice/voice_listener.py"
        ).read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 220)


if __name__ == "__main__":
    unittest.main()
