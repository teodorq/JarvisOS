"""Optional Cartesia and ElevenLabs TTS adapters with local-only secrets."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
from typing import Any, Mapping
import wave

import requests


try:
    import winsound
except ImportError:  # pragma: no cover - JARVIS OS targets Windows
    winsound = None  # type: ignore[assignment]


_PROVIDER_ALIASES = {
    "CARTESIA": "CARTESIA",
    "CARTESIA_SONIC": "CARTESIA",
    "CARTESIA_SONIC_3_5": "CARTESIA",
    "ELEVENLABS": "ELEVENLABS",
    "ELEVEN_LABS": "ELEVENLABS",
}
_EXPLICIT_LOCAL_ENGINES = {
    "LOCAL",
    "PYTTSX3",
    "PYTTSX3_DEFAULT",
    "WINDOWS_ONECORE",
}
_VOICE_ID = re.compile(r"^[A-Za-z0-9_-]{3,128}$")


def requested_cloud_provider(
    engine_name: str = "", *, environment: Mapping[str, str] | None = None
) -> str:
    """Resolve an explicit provider without changing the local default."""

    selected = str(engine_name or "").strip().upper().replace("-", "_")
    if selected in _PROVIDER_ALIASES:
        return _PROVIDER_ALIASES[selected]
    if selected in _EXPLICIT_LOCAL_ENGINES:
        return ""
    values = environment if environment is not None else os.environ
    configured = str(values.get("JARVIS_OS_VOICE_PROVIDER", ""))
    configured = configured.strip().upper().replace("-", "_")
    return _PROVIDER_ALIASES.get(configured, "")


def _bounded_timeout(value: object) -> float:
    try:
        return max(5.0, min(float(value), 60.0))
    except (TypeError, ValueError):
        return 25.0


@dataclass(frozen=True)
class CloudVoiceConfig:
    provider: str
    api_key: str = field(repr=False)
    voice_id: str
    model_id: str
    timeout_seconds: float = 25.0
    language: str = "pl"
    sample_rate: int = 24_000
    max_characters: int = 4_000

    @property
    def is_configured(self) -> bool:
        return bool(
            self.provider in {"CARTESIA", "ELEVENLABS"}
            and self.api_key.strip()
            and _VOICE_ID.fullmatch(self.voice_id.strip())
            and self.model_id.strip()
        )

    @classmethod
    def from_environment(
        cls,
        provider: str,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> "CloudVoiceConfig":
        values = environment if environment is not None else os.environ
        normalized = _PROVIDER_ALIASES.get(
            str(provider or "").strip().upper().replace("-", "_"), ""
        )
        if normalized == "CARTESIA":
            key_name = "CARTESIA_API_KEY"
            voice_name = "CARTESIA_VOICE_ID"
            model_name = "JARVIS_OS_CARTESIA_MODEL_ID"
            default_model = "sonic-3"
        elif normalized == "ELEVENLABS":
            key_name = "ELEVENLABS_API_KEY"
            voice_name = "ELEVENLABS_VOICE_ID"
            model_name = "JARVIS_OS_ELEVENLABS_MODEL_ID"
            default_model = "eleven_multilingual_v2"
        else:
            key_name = voice_name = model_name = ""
            default_model = ""
        return cls(
            provider=normalized,
            api_key=str(values.get(key_name, "")).strip()[:512],
            voice_id=str(values.get(voice_name, "")).strip()[:128],
            model_id=str(values.get(model_name, default_model)).strip()[:128],
            timeout_seconds=_bounded_timeout(
                values.get("JARVIS_OS_VOICE_TIMEOUT_SECONDS", "25")
            ),
        )


@dataclass(frozen=True)
class CloudVoice:
    id: str
    name: str
    languages: list[str]
    gender: str = ""


class CloudVoiceEngine:
    """pyttsx3-compatible TTS adapter for explicitly enabled cloud providers."""

    supports_pitch = False
    cross_thread_stop_safe = True
    MAX_AUDIO_BYTES = 16 * 1024 * 1024

    def __init__(
        self,
        config: CloudVoiceConfig,
        *,
        project_root: str | Path | None = None,
        session: Any | None = None,
    ) -> None:
        if not config.is_configured:
            raise RuntimeError("Dostawca głosu nie ma kompletnej konfiguracji.")
        self.config = config
        self.project_root = Path(
            project_root or Path(__file__).resolve().parents[2]
        ).resolve()
        self.output_root = self.project_root / "runtime" / "voice_output"
        self._session = session or requests.Session()
        self._voice = config.voice_id
        self._rate = 158
        self._volume = 0.92
        self._profile = "calm"
        self._message = ""

    @classmethod
    def from_environment(
        cls,
        provider: str,
        *,
        environment: Mapping[str, str] | None = None,
        project_root: str | Path | None = None,
        session: Any | None = None,
    ) -> "CloudVoiceEngine":
        return cls(
            CloudVoiceConfig.from_environment(
                provider, environment=environment
            ),
            project_root=project_root,
            session=session,
        )

    @classmethod
    def is_available(
        cls,
        provider: str,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> bool:
        return CloudVoiceConfig.from_environment(
            provider, environment=environment
        ).is_configured

    def available_voices(self) -> list[CloudVoice]:
        return [CloudVoice(
            id=self.config.voice_id,
            name=f"JARVIS {self.config.provider.title()}",
            languages=["pl-PL"],
        )]

    def setProperty(self, name: str, value: Any) -> None:  # noqa: N802
        if name == "rate":
            self._rate = max(100, min(int(value), 240))
        elif name == "volume":
            self._volume = max(0.25, min(float(value), 1.0))
        elif name == "voice" and _VOICE_ID.fullmatch(str(value or "")):
            self._voice = str(value)
        elif name == "speech_profile":
            self._profile = str(value or "calm")[:32]

    def getProperty(self, name: str) -> Any:  # noqa: N802
        return {
            "voices": self.available_voices(),
            "voice": self._voice,
            "rate": self._rate,
            "volume": self._volume,
            "speech_profile": self._profile,
        }.get(name)

    def say(self, message: object) -> None:
        self._message = " ".join(str(message or "").split()).strip()

    def runAndWait(self) -> None:  # noqa: N802
        message = self._message
        self._message = ""
        if not message:
            return
        if len(message) > self.config.max_characters:
            raise ValueError("Tekst przekracza bezpieczny limit usługi głosowej.")
        output = self._cache_path(message)
        if not output.is_file() or output.stat().st_size < 48:
            audio = self._synthesize(message)
            self._write_pcm_wave(output, audio)
        self._play(output)

    def _synthesize(self, message: str) -> bytes:
        if self.config.provider == "CARTESIA":
            url = "https://api.cartesia.ai/tts/bytes"
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Cartesia-Version": "2026-03-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model_id": self.config.model_id,
                "transcript": message,
                "voice": {"id": self._voice},
                "output_format": {
                    "container": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": self.config.sample_rate,
                },
                "language": self.config.language,
                "generation_config": {
                    "volume": self._volume,
                    "speed": self._speed(),
                },
            }
            params = None
        else:
            url = (
                "https://api.elevenlabs.io/v1/text-to-speech/"
                f"{self._voice}"
            )
            headers = {
                "xi-api-key": self.config.api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "text": message,
                "model_id": self.config.model_id,
                "language_code": self.config.language,
                "voice_settings": {"speed": self._speed()},
            }
            params = {"output_format": f"pcm_{self.config.sample_rate}"}
        response = self._session.post(
            url,
            headers=headers,
            params=params,
            json=payload,
            stream=True,
            timeout=(5.0, self.config.timeout_seconds),
        )
        try:
            status = int(getattr(response, "status_code", 0) or 0)
            if status < 200 or status >= 300:
                raise RuntimeError(
                    f"{self.config.provider} zwrócił status HTTP {status}."
                )
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > self.MAX_AUDIO_BYTES:
                    raise RuntimeError("Odpowiedź audio przekroczyła limit rozmiaru.")
                chunks.append(bytes(chunk))
            audio = b"".join(chunks)
            if len(audio) < 2 or len(audio) % 2:
                raise RuntimeError("Usługa głosowa zwróciła nieprawidłowe audio.")
            return audio
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def _cache_path(self, message: str) -> Path:
        identity = "\n".join((
            self.config.provider,
            self.config.model_id,
            self._voice,
            self.config.language,
            str(self.config.sample_rate),
            f"{self._speed():.3f}",
            f"{self._volume:.3f}",
            self._profile,
            message,
        ))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.output_root / "cloud_cache" / f"{digest}.wav"

    def _write_pcm_wave(self, output: Path, audio: bytes) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp")
        try:
            with wave.open(str(temporary), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(self.config.sample_rate)
                stream.writeframes(audio)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)

    def _play(self, output: Path) -> None:
        if winsound is None:
            raise RuntimeError("Odtwarzanie głosu wymaga systemu Windows.")
        winsound.PlaySound(str(output), winsound.SND_FILENAME)

    def _speed(self) -> float:
        return max(0.7, min(self._rate / 158.0, 1.2))

    def stop(self) -> None:
        if winsound is None:
            return
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except RuntimeError:
            return


__all__ = [
    "CloudVoice",
    "CloudVoiceConfig",
    "CloudVoiceEngine",
    "requested_cloud_provider",
]
