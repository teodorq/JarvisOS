from __future__ import annotations

from pathlib import Path
import ast
import threading
import time
import unittest

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService, fold_text
from app.voice.tts_runtime import SerializedTTS


class _FakeEngine:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.active = 0
        self.max_active = 0
        self.rate = 0
        self.stopped = False
        self.lock = threading.Lock()

    def setProperty(self, name: str, value: int) -> None:
        if name == "rate":
            self.rate = value

    def say(self, message: str) -> None:
        self.messages.append(message)

    def runAndWait(self) -> None:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.03)
        with self.lock:
            self.active -= 1

    def stop(self) -> None:
        self.stopped = True


class B1001VoiceRuntimePolishRoutingTests(unittest.TestCase):

    def test_polish_l_stroke_is_folded_for_command_routing(self) -> None:
        folded = fold_text("Pokaż status głosu 2.0")
        self.assertIn("status glosu", folded)
        self.assertEqual(
            NaturalLanguageService.classify("Pokaż status głosu 2.0"),
            "voice_status",
        )
        self.assertTrue(
            PersonalAssistantController.matches(
                "Pokaż status głosu 2.0"
            )
        )

    def test_tts_uses_only_one_run_loop(self) -> None:
        engine = _FakeEngine()
        runtime = SerializedTTS(
            engine_factory=lambda: engine,
        )
        try:
            runtime.say("pierwsza", replace_pending=False)
            runtime.say("druga", replace_pending=False)
            runtime.say("trzecia", replace_pending=False)
            deadline = time.time() + 2.0
            while len(engine.messages) < 3 and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(engine.max_active, 1)
            self.assertEqual(
                engine.messages,
                ["pierwsza", "druga", "trzecia"],
            )
        finally:
            runtime.close()

    def test_wake_branch_does_not_speak_twice(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "app/voice/voice_listener.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        listener = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "VoiceListener"
        )
        loop_method = next(
            node for node in listener.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_loop"
        )
        calls = [
            node for node in ast.walk(loop_method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "say"
        ]
        self.assertEqual(calls, [])

    def test_voice_errors_are_not_sent_to_brain(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "app/gui/business_command_runtime.py"
        )
        source = source_path.read_text(encoding="utf-8")
        self.assertIn('[voice_error]', source)
        self.assertIn('Voice runtime diagnostic:', source)


if __name__ == "__main__":
    unittest.main()
