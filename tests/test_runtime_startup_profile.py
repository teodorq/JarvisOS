from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from app.ai.brain import Brain
from app.voice.voice_listener import VoiceListener


class RuntimeStartupProfileTests(unittest.TestCase):
    def test_client_profile_defers_owner_autonomy(self) -> None:
        brain = Brain(runtime_profile="client")
        try:
            self.assertEqual(brain.runtime_profile, "client")
            self.assertEqual(
                brain.background_autodev_start_result["status"],
                "DEFERRED_CLIENT_MODE",
            )
            self.assertFalse(brain.background_status().get("running", False))
            self.assertIsNone(brain.strategic_policy_validation_service)
            self.assertIsNone(brain.long_running_autonomy_service)
        finally:
            brain.shutdown()

    def test_microphone_is_not_opened_on_gui_construction(self) -> None:
        recognizer = Mock()
        text_to_speech = Mock()
        with patch(
            "app.voice.voice_listener.sr.Microphone",
            side_effect=AssertionError("mikrofon otwarty w głównym wątku"),
        ) as microphone_factory:
            listener = VoiceListener(
                settings={"language": "pl-PL"},
                recognizer=recognizer,
                tts=text_to_speech,
                auto_start=False,
            )
        self.assertIsNone(listener.microphone)
        microphone_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
