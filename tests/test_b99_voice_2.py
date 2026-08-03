from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import ast
import unittest
from unittest.mock import patch

from app.assistant.voice_runtime import VoiceCommandInterpreter, VoiceRuntimeService
from app.voice.tts_runtime import SerializedTTS, _default_engine_factory


class B99Voice2Tests(unittest.TestCase):

    def test_command_can_follow_wake_word_in_same_utterance(self) -> None:
        interpreter = VoiceCommandInterpreter()
        wake, command = interpreter.wake_and_command(
            "Jarvis otwórz notatnik"
        )
        self.assertTrue(wake)
        self.assertEqual(command, "otwórz notatnik")

    def test_polish_confirmation_and_interrupt_are_recognized(self) -> None:
        interpreter = VoiceCommandInterpreter()
        self.assertIs(interpreter.confirmation("potwierdzam"), True)
        self.assertIs(interpreter.confirmation("nie wykonuj"), False)
        self.assertTrue(interpreter.is_interrupt("przerwij"))

    def test_voice_policy_is_persistent_and_bounded(self) -> None:
        with TemporaryDirectory() as temporary:
            service = VoiceRuntimeService(temporary)
            settings = service.update({
                "continuous_mode": True,
                "speech_rate": 999,
                "phrase_time_limit_seconds": 1,
            })
            self.assertTrue(settings["continuous_mode"])
            self.assertEqual(settings["speech_rate"], 240)
            self.assertEqual(settings["phrase_time_limit_seconds"], 3)
            self.assertTrue(VoiceRuntimeService(temporary).status()["continuous_mode"])

    def test_listener_keeps_interrupt_method_without_microphone_start(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/voice/voice_listener.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        listener = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "VoiceListener"
        )
        methods = {node.name for node in listener.body if isinstance(node, ast.FunctionDef)}
        self.assertIn("interrupt", methods)
        self.assertIn("_emit_command", methods)

    def test_wake_word_with_comma_keeps_direct_command(self) -> None:
        wake, command = VoiceCommandInterpreter().wake_and_command(
            "Jarvis, otwórz kalkulator"
        )
        self.assertTrue(wake)
        self.assertEqual(command, "otwórz kalkulator")

    def test_original_engine_forces_system_pyttsx3_voice(self) -> None:
        engine = object()
        with patch(
            "app.voice.tts_runtime.pyttsx3.init", return_value=engine
        ) as init, patch(
            "app.voice.system_sapi_engine.WindowsSystemSapiEngine.is_available",
            return_value=False,
        ):
            selected = _default_engine_factory(
                neural_enabled=True,
                engine_name="PYTTSX3_DEFAULT",
            )
        self.assertIs(selected, engine)
        init.assert_called_once_with()

    def test_original_profile_does_not_override_system_voice(self) -> None:
        class Engine:
            def __init__(self) -> None:
                self.properties = []

            def setProperty(self, name, value) -> None:  # noqa: N802
                self.properties.append((name, value))

            def stop(self) -> None:
                pass

        engine = Engine()
        runtime = SerializedTTS(
            engine_name="PYTTSX3_DEFAULT",
            rate=170,
            volume=1.0,
            engine_factory=lambda: engine,
        )
        try:
            self.assertTrue(runtime.wait_until_idle(timeout=1.0))
        finally:
            runtime.close()
        names = [name for name, _value in engine.properties]
        self.assertIn("rate", names)
        self.assertNotIn("voice", names)
        self.assertNotIn("pitch", names)


if __name__ == "__main__":
    unittest.main()
