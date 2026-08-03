from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from app.gui.client_sound_theme import ClientSoundTheme


class TestB341B350CinematicSoundTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.app = QApplication.instance() or QApplication([])

    def test_manifest_closes_all_ten_stages(self) -> None:
        manifest = json.loads(
            (self.root / "config/b341_b350_cinematic_sound_theme.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            list(manifest["stages"]),
            [f"B{number}" for number in range(341, 351)],
        )
        self.assertTrue(
            all(value.endswith(("READY", "REVIEWED")) for value in manifest["stages"].values())
        )
        self.assertFalse(manifest["assets"]["downloaded_samples"])
        self.assertFalse(manifest["safety"]["celebrity_voice_clone"])

    def test_all_original_wave_assets_are_small_and_valid(self) -> None:
        sound_root = self.root / "assets/sound_theme"
        expected = {
            "startup.wav",
            "listening.wav",
            "thinking.wav",
            "success.wav",
            "warning.wav",
            "error.wav",
        }
        paths = {path.name: path for path in sound_root.glob("*.wav")}
        self.assertEqual(set(paths), expected)
        self.assertLess(sum(path.stat().st_size for path in paths.values()), 500_000)
        for name, path in paths.items():
            with self.subTest(sound=name), wave.open(str(path), "rb") as stream:
                self.assertEqual(stream.getnchannels(), 1)
                self.assertEqual(stream.getsampwidth(), 2)
                self.assertEqual(stream.getframerate(), 48_000)
                self.assertGreater(stream.getnframes(), 10_000)
                self.assertLess(stream.getnframes(), 60_000)

    def test_state_map_covers_every_meaningful_client_state(self) -> None:
        self.assertEqual(ClientSoundTheme.STATE_SOUNDS["listening"], "listening")
        self.assertEqual(ClientSoundTheme.STATE_SOUNDS["acting"], "thinking")
        self.assertEqual(ClientSoundTheme.STATE_SOUNDS["success"], "success")
        self.assertEqual(ClientSoundTheme.STATE_SOUNDS["warning"], "warning")
        self.assertEqual(ClientSoundTheme.STATE_SOUNDS["error"], "error")

    def test_offscreen_tests_never_play_real_audio(self) -> None:
        theme = ClientSoundTheme(QObject(), self.root)
        self.assertFalse(theme.enabled)
        self.assertEqual(theme.effects, {})
        theme.startup()
        theme.play("success")

    def test_theme_uses_qt_channel_instead_of_speech_channel(self) -> None:
        source = (self.root / "app/gui/client_sound_theme.py").read_text(
            encoding="utf-8"
        )
        presenter = (self.root / "app/gui/client_state_presenter.py").read_text(
            encoding="utf-8"
        )
        generator = (
            self.root / "tools/audio/generate_jarvis_sound_theme.py"
        ).read_text(encoding="utf-8")
        self.assertIn("QSoundEffect", source)
        self.assertNotIn("winsound", source)
        self.assertIn("self.sound_theme.play(value)", presenter)
        self.assertNotIn("http://", generator)
        self.assertNotIn("https://", generator)


if __name__ == "__main__":
    unittest.main()
