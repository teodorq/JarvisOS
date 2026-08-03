from __future__ import annotations

import threading
import time
import unittest

from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.jarvis_experience.isolation import ClientIsolationPolicy
from app.voice.tts_runtime import SerializedTTS


class _BlockingEngine:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.release = threading.Event()
        self.started = threading.Event()
        self.stop_calls = 0

    def setProperty(self, _name, _value) -> None:  # noqa: N802
        return None

    def say(self, message: str) -> None:
        self.messages.append(str(message))

    def runAndWait(self) -> None:  # noqa: N802
        self.started.set()
        self.release.wait(2.0)
        self.release.clear()

    def stop(self) -> None:
        self.stop_calls += 1
        self.release.set()


class _FastEngine:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def setProperty(self, _name, _value) -> None:  # noqa: N802
        return None

    def say(self, message: str) -> None:
        self.messages.append(str(message))

    def runAndWait(self) -> None:  # noqa: N802
        return None

    def stop(self) -> None:
        return None


class VoiceRuntimeRecoveryTests(unittest.TestCase):
    def test_new_response_interrupts_a_blocked_previous_utterance(self) -> None:
        engine = _BlockingEngine()
        runtime = SerializedTTS(engine_factory=lambda: engine)
        try:
            self.assertTrue(runtime.say("Pierwsza odpowiedź."))
            self.assertTrue(engine.started.wait(1.0))
            self.assertTrue(runtime.say("Druga odpowiedź."))
            deadline = time.monotonic() + 1.5
            while len(engine.messages) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            engine.release.set()
            self.assertTrue(runtime.wait_until_idle(2.0))
            self.assertEqual(len(engine.messages), 2)
            self.assertIn("Druga", engine.messages[-1])
            self.assertGreaterEqual(engine.stop_calls, 1)
            self.assertTrue(runtime.worker_alive)
        finally:
            engine.release.set()
            runtime.close()

    def test_worker_survives_engine_creation_failure_and_retries_text(self) -> None:
        engine = _FastEngine()
        calls = 0
        errors: list[Exception] = []

        def factory():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("silnik chwilowo niedostępny")
            return engine

        runtime = SerializedTTS(engine_factory=factory, on_error=errors.append)
        try:
            self.assertTrue(runtime.say("Pierwsza próba."))
            self.assertTrue(runtime.wait_until_idle(1.0))
            self.assertTrue(runtime.worker_alive)
            self.assertTrue(runtime.say("Druga próba."))
            self.assertTrue(runtime.wait_until_idle(1.0))
            self.assertEqual(len(errors), 1)
            self.assertEqual(engine.messages, ["Pierwsza próba.", "Druga próba."])
            status = runtime.status()
            self.assertEqual(status["spoken_count"], 2)
            self.assertEqual(status["failed_count"], 1)
        finally:
            runtime.close()

    def test_owner_only_denial_remains_readable_in_client(self) -> None:
        denial = ClientCapabilityPolicy.denial_message(
            "Ile wydaliśmy na reklamy?"
        )
        event = ClientIsolationPolicy.sanitize_event({
            "state": "error", "message": denial, "progress": 100,
        })
        self.assertIn("tylko dla właściciela", event["message"])
        self.assertNotEqual(event["message"], "Zadanie zostało obsłużone.")


if __name__ == "__main__":
    unittest.main()
