from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any
import winsound

from PySide6.QtCore import QObject

from app.core.performance_profile import load_performance_profile


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
        performance = load_performance_profile(self.root)
        self.enabled = bool(self.config.get("enabled", True)) and (
            os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"
        ) and performance.sound_theme_enabled
        self.cooldown = max(0.1, float(self.config.get("cooldown_seconds", 0.32)))
        self._last_name = ""
        self._last_played = 0.0
        self.effects: dict[str, Path] = {}
        if self.enabled:
            self._prepare()

    def startup(self) -> None:
        self._play("startup", force=True)

    def play(self, state: object) -> None:
        name = self.STATE_SOUNDS.get(str(state or "").casefold(), "")
        if name:
            self._play(name)

    def apply_preferences(
        self,
        *,
        enabled: bool,
        performance_profile: object,
    ) -> None:
        performance_enabled = bool(
            getattr(performance_profile, "sound_theme_enabled", True)
        )
        self.enabled = (
            bool(enabled)
            and performance_enabled
            and os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"
        )
        if self.enabled and not self.effects:
            self._prepare()

    def _play(self, name: str, *, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and name == self._last_name and now - self._last_played < self.cooldown:
            return
        path = self.effects.get(name)
        if path is None:
            return
        winsound.PlaySound(
            str(path),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
        self._last_name = name
        self._last_played = now

    def _prepare(self) -> None:
        sound_root = self.root / "assets" / "sound_theme"
        for name in {"startup", *self.STATE_SOUNDS.values()}:
            path = sound_root / f"{name}.wav"
            if not path.is_file():
                continue
            self.effects[name] = path

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
        try:
            business = json.loads(
                (self.root / "config" / "business_edition.json").read_text(
                    encoding="utf-8"
                )
            )
            sound = dict(business.get("sound", {}) or {})
            defaults["enabled"] = bool(
                sound.get("effects_enabled", defaults["enabled"])
            )
        except (OSError, ValueError, TypeError):
            pass
        return defaults
