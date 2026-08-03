from __future__ import annotations

from pathlib import Path
import importlib.util
import importlib.machinery
import sys
import types
import unittest

if "speech_recognition" not in sys.modules and importlib.util.find_spec("speech_recognition") is None:
    module = types.ModuleType("speech_recognition")
    module.__spec__ = importlib.machinery.ModuleSpec("speech_recognition", loader=None)
    class WaitTimeoutError(Exception):
        pass
    class UnknownValueError(Exception):
        pass
    class Recognizer:
        pass
    class Microphone:
        pass
    module.WaitTimeoutError = WaitTimeoutError
    module.UnknownValueError = UnknownValueError
    module.Recognizer = Recognizer
    module.Microphone = Microphone
    sys.modules["speech_recognition"] = module

from app.gui.voice_command_dispatch import dispatch_voice_text
from app.voice.voice_listener import VoiceListener


class FakeMicrophone:
    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        return False


class FakeRecognizer:
    def __init__(self, transcript: str = "") -> None:
        self.transcript = transcript
        self.energy_threshold = 0
        self.dynamic_energy_threshold = False
        self.pause_threshold = 0.0
        self.non_speaking_duration = 0.0
        self.operation_timeout = None

    def adjust_for_ambient_noise(self, _source, duration=0.0):
        return None

    def listen(self, _source, timeout=None, phrase_time_limit=None):
        return object()

    def recognize_google(self, _audio, language=None):
        return self.transcript


class FakeTTS:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.speaking = False

    def say(self, text, *, replace_pending=True):
        self.messages.append(str(text))
        return True

    def wait_until_idle(self, timeout=8.0):
        return True

    def interrupt(self):
        return True

    def close(self):
        return None


def build_listener(transcript: str = ""):
    events: list[str] = []
    listener = VoiceListener(
        on_text=events.append,
        recognizer=FakeRecognizer(transcript),
        microphone=FakeMicrophone(),
        tts=FakeTTS(),
        auto_start=False,
    )
    listener.start = lambda: None
    listener.running = True
    return listener, events


class FakeConsole:
    def append(self, _text):
        return None

    def set_state(self, _text, _kind):
        return None


class FakeController:
    def status(self):
        return {"runtime": {"mode": "CLIENT"}}


class FakeClient:
    def __init__(self) -> None:
        self.controller = FakeController()
        self.states: list[str] = []

    def isVisible(self):
        return True

    def handle_voice_state(self, state):
        self.states.append(state)


class FakeWindow:
    def __init__(self) -> None:
        self.client_window = FakeClient()
        self.console_page = FakeConsole()
        self.commands: list[str] = []

    def process_client_command(self, text):
        self.commands.append(text)

    def process_command(self, text, source="Ty"):
        self.commands.append(text)


class B1454VoiceCaptureStateMachineTests(unittest.TestCase):

    def test_push_to_talk_captures_command_without_wake_word(self) -> None:
        listener, events = build_listener(
            "dodaj jutro trening o osiemnastej"
        )
        self.assertTrue(listener.listen_once())
        listener._runtime.manual_cycle()
        self.assertIn("[voice_state] prompt", events)
        self.assertIn("[voice_state] listening", events)
        self.assertIn("[voice_state] recognized", events)
        self.assertEqual(
            events[-1],
            "dodaj jutro trening o osiemnastej",
        )
        self.assertFalse(listener.manual_active)
        self.assertEqual(listener.tts.messages, ["Słucham"])

    def test_second_push_to_talk_cancels_active_capture(self) -> None:
        listener, events = build_listener()
        self.assertTrue(listener.listen_once())
        self.assertTrue(listener.cancel_listen_once())
        self.assertFalse(listener.manual_active)
        self.assertIn("[voice_state] cancelled", events)

    def test_background_wake_word_arms_one_shot_command_capture(self) -> None:
        listener, events = build_listener()
        listener._runtime.handle_background_text("Jarvis")
        self.assertTrue(listener.manual_active)
        self.assertIn("[voice_state] prompt", events)
        self.assertEqual(listener.tts.messages, ["Słucham"])

    def test_wake_word_with_command_executes_directly_once(self) -> None:
        listener, events = build_listener()
        listener._runtime.handle_background_text(
            "Jarvis otwórz kalendarz"
        )
        self.assertEqual(events, ["otwórz kalendarz"])

    def test_dispatch_ignores_duplicate_voice_command(self) -> None:
        window = FakeWindow()
        dispatch_voice_text(window, "Pokaż mój dzień")
        dispatch_voice_text(window, "Pokaż mój dzień")
        self.assertEqual(window.commands, ["Pokaż mój dzień"])

    def test_voice_state_updates_client_without_running_command(self) -> None:
        window = FakeWindow()
        dispatch_voice_text(window, "[voice_state] listening")
        self.assertEqual(window.client_window.states, ["listening"])
        self.assertEqual(window.commands, [])

    def test_source_limits_and_manual_flow_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        listener = (root / "app/voice/voice_listener.py").read_text(
            encoding="utf-8"
        )
        client = (root / "app/gui/client_experience_window.py").read_text(
            encoding="utf-8"
        )
        mixin = (root / "app/gui/client_voice_mixin.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(len(listener.splitlines()), 220)
        self.assertLess(len(client.splitlines()), 440)
        self.assertIn("ClientVoiceMixin", client)
        self.assertIn("ANULUJ", mixin)
        self.assertIn("Nie musisz mówić „Jarvis”", mixin)
        self.assertNotIn('say_safe("Słucham")', client)


if __name__ == "__main__":
    unittest.main()
