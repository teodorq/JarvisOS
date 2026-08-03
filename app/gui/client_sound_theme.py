from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect


class ClientSoundTheme(QObject):
    """Small original HUD sound theme, independent from spoken responses."""

    STATE_SOUNDS = {
        "listening": "listening",
        "thinking": "thinking",
        "acting": "thinking",
        "success": "success",
        "brief": "success",
        "warning": "warning",
        "important": "warning",
        "error": "error",
    }

    def __init__(self, parent: QObject, project_root: object = None) -> None:
        super().__init__(parent)
        self.root = Path(
            project_root or Path(__file__).resolve().parents[2]
        ).resolve()
        self.config = self._load_config()
        self.enabled = bool(self.config.get("enabled", True)) and (
            os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"
        )
        self.cooldown = max(0.1, float(self.config.get("cooldown_seconds", 0.32)))
        self._last_name = ""
        self._last_played = 0.0
        self.effects: dict[str, QSoundEffect] = {}
        if self.enabled:
            self._prepare()

    def startup(self) -> None:
        self._play("startup", force=True)

    def play(self, state: object) -> None:
        name = self.STATE_SOUNDS.get(str(state or "").casefold(), "")
        if name:
            self._play(name)

    def _play(self, name: str, *, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and name == self._last_name and now - self._last_played < self.cooldown:
            return
        effect = self.effects.get(name)
        if effect is None:
            return
        effect.stop()
        effect.play()
        self._last_name = name
        self._last_played = now

    def _prepare(self) -> None:
        sound_root = self.root / "assets" / "sound_theme"
        volume = max(0.0, min(1.0, float(self.config.get("volume", 0.24))))
        levels = dict(self.config.get("levels", {}) or {})
        for name in {"startup", *self.STATE_SOUNDS.values()}:
            path = sound_root / f"{name}.wav"
            if not path.is_file():
                continue
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setLoopCount(1)
            effect.setVolume(max(0.0, min(1.0, volume * float(levels.get(name, 1.0)))))
            self.effects[name] = effect

    def _load_config(self) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "enabled": True,
            "volume": 0.24,
            "cooldown_seconds": 0.32,
            "levels": {},
        }
        path = self.root / "config" / "b341_b350_cinematic_sound_theme.json"
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            settings = loaded.get("sound_theme", loaded)
            if isinstance(settings, dict):
                defaults.update(settings)
        except (OSError, ValueError, TypeError):
            pass
        return defaults
