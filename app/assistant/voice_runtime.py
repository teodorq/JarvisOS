from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from app.assistant.natural_language import fold_text, normalize_user_command
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VoiceRuntimeService:
    """B99 local Voice 2.0 policy and Polish transcript interpretation."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "assistant" / "voice_runtime.json",
            self._default,
        )
        if not self.store.exists():
            self.store.save(self._default())

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "2.3",
            "language": "pl-PL",
            "voice_profile": "CALM_CINEMATIC",
            "preferred_gender": "Male",
            "volume": 0.92,
            "pitch": 0.88,
            "voice_engine": "CHATTERBOX_MULTILINGUAL_V3",
            "neural_enabled": True,
            "reference_audio": "assets/voice/references/jarvis_style_reference_vtubereels_147563_20260801.mp3",
            "neural_device": "auto",
            "fallback_engine": "WINDOWS_ONECORE",
            "wake_words": ["jarvis", "jarwis", "dżarwis", "jervis"],
            "command_timeout_seconds": 15,
            "phrase_time_limit_seconds": 12,
            "confirmation_window_seconds": 20,
            "speech_rate": 158,
            "continuous_mode": False,
            "interrupt_enabled": True,
            "last_transcript": "",
            "last_event": "",
            "updated_at": "",
        }

    def settings(self) -> dict[str, Any]:
        value = self.store.load()
        data = value if isinstance(value, dict) else self._default()
        default = self._default()
        migrated = str(data.get("version", "")) != default["version"]
        if migrated and int(data.get("speech_rate", 175) or 175) == 175:
            data["speech_rate"] = default["speech_rate"]
        for key, item in default.items():
            data.setdefault(key, item)
        if migrated:
            data["version"] = default["version"]
            self.store.save(data)
        return data

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        data = self.settings()
        allowed = {
            "language",
            "voice_profile",
            "preferred_gender",
            "volume",
            "pitch",
            "voice_engine",
            "neural_enabled",
            "reference_audio",
            "neural_device",
            "fallback_engine",
            "wake_words",
            "command_timeout_seconds",
            "phrase_time_limit_seconds",
            "confirmation_window_seconds",
            "speech_rate",
            "continuous_mode",
            "interrupt_enabled",
        }
        for key, value in dict(updates or {}).items():
            if key not in allowed:
                continue
            if key.endswith("_seconds"):
                value = max(3, min(int(value), 60))
            if key == "speech_rate":
                value = max(100, min(int(value), 240))
            if key == "volume":
                value = max(0.25, min(float(value), 1.0))
            if key == "pitch":
                value = max(0.7, min(float(value), 1.2))
            if key == "preferred_gender":
                value = str(value or "").strip().title()[:20]
            if key == "voice_profile":
                value = str(value or "").strip().upper()[:40]
            if key in {"continuous_mode", "interrupt_enabled", "neural_enabled"}:
                value = bool(value)
            if key == "wake_words":
                value = [str(item).casefold().strip() for item in value if str(item).strip()][:10]
            data[key] = value
        data["updated_at"] = utc_now()
        self.store.save(data)
        return data

    def record(self, transcript: str, event: str) -> None:
        data = self.settings()
        data["last_transcript"] = str(transcript)[:500]
        data["last_event"] = str(event)[:100]
        data["updated_at"] = utc_now()
        self.store.save(data)

    def status(self) -> dict[str, Any]:
        data = self.settings()
        return {
            "status": "VOICE_2_READY",
            "language": data["language"],
            "voice_profile": data["voice_profile"],
            "preferred_gender": data["preferred_gender"],
            "speech_rate": data["speech_rate"],
            "volume": data["volume"],
            "pitch": data["pitch"],
            "voice_engine": data["voice_engine"],
            "neural_enabled": data["neural_enabled"],
            "fallback_engine": data["fallback_engine"],
            "wake_words": data["wake_words"],
            "command_timeout_seconds": data["command_timeout_seconds"],
            "phrase_time_limit_seconds": data["phrase_time_limit_seconds"],
            "continuous_mode": data["continuous_mode"],
            "interrupt_enabled": data["interrupt_enabled"],
            "last_event": data.get("last_event", ""),
        }


class VoiceCommandInterpreter:
    """Pure interpreter used by VoiceListener and tests without microphone access."""

    CONFIRMATIONS = {
        "tak": True,
        "ta": True,
        "wykonaj": True,
        "potwierdzam": True,
        "ok": True,
        "okej": True,
        "zgoda": True,
        "nie": False,
        "anuluj": False,
        "stop": False,
        "nie wykonuj": False,
    }

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self.settings = dict(settings or VoiceRuntimeService._default())
        self.wake_words = {
            fold_text(item)
            for item in self.settings.get("wake_words", [])
            if str(item).strip()
        }

    def normalize(self, transcript: object) -> str:
        text = " ".join(str(transcript).strip().split())
        return re.sub(r"\s+", " ", text).strip(" .,:;!?")

    def confirmation(self, transcript: object) -> bool | None:
        normalized = fold_text(self.normalize(transcript))
        mapping = {fold_text(key): value for key, value in self.CONFIRMATIONS.items()}
        return mapping.get(normalized)

    def wake_and_command(self, transcript: object) -> tuple[bool, str]:
        normalized = self.normalize(transcript)
        folded = fold_text(normalized)
        for wake_word in self.wake_words:
            match = re.match(
                rf"^{re.escape(wake_word)}(?:[\s,;:!?.-]+|$)",
                folded,
            )
            if match:
                command = normalized[match.end():].strip(" ,;:!?.-")
                return True, command
        return False, normalized

    def is_interrupt(self, transcript: object) -> bool:
        return fold_text(self.normalize(transcript)) in {
            "przerwij",
            "jarvis przerwij",
            "stop mowienie",
            "przestan mowic",
            "cisza",
        }
