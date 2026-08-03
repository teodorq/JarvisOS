from __future__ import annotations

import threading
import time
import unittest

from app.voice.tts_runtime import SerializedTTS


class _SapiLikeBlockingEngine:
    __module__ = "pyttsx3.engine"

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.started = threading.Event()
        self.release = threading.Event()
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


class SapiThreadAffinityTests(unittest.TestCase):
    def test_new_message_does_not_stop_sapi_from_the_gui_thread(self) -> None:
        engine = _SapiLikeBlockingEngine()
        runtime = SerializedTTS(engine_factory=lambda: engine)
        try:
            self.assertTrue(runtime.wait_until_idle(1.0))
            self.assertTrue(runtime.say("Pierwsza odpowiedź."))
            self.assertTrue(engine.started.wait(1.0))
            self.assertTrue(runtime.say("Druga odpowiedź."))
            time.sleep(0.05)
            self.assertEqual(engine.stop_calls, 0)

            engine.release.set()
            deadline = time.monotonic() + 1.0
            while len(engine.messages) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(engine.messages[-1], "Druga odpowiedź.")
            engine.release.set()
            self.assertTrue(runtime.wait_until_idle(2.0))
            self.assertEqual(engine.stop_calls, 0)
        finally:
            engine.release.set()
            runtime.close()


if __name__ == "__main__":
    unittest.main()
