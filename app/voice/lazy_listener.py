"""Low-cost proxy that starts the audio stack only when voice is used."""

from __future__ import annotations

from importlib.util import find_spec
from threading import RLock
from typing import Any, Callable


class LazyVoiceListener:
    """Preserve the VoiceListener API without paying its idle startup cost."""

    def __init__(
        self,
        on_text: Callable[[str], None] | None = None,
        *,
        settings: dict[str, Any] | None = None,
        auto_start: bool = False,
        factory: Callable[..., Any] | None = None,
    ) -> None:
        self.on_text = on_text
        self.settings = dict(settings or {})
        self.continuous_mode = bool(self.settings.get("continuous_mode", False))
        self.dependencies_available = find_spec("speech_recognition") is not None
        self.last_error = ""
        self._auto_start = bool(auto_start)
        self._factory = factory
        self._listener: Any | None = None
        self._failed = False
        self._lock = RLock()
        if auto_start and self.continuous_mode:
            self.start()

    @property
    def loaded(self) -> bool:
        return self._listener is not None

    @property
    def manual_active(self) -> bool:
        return bool(getattr(self._listener, "manual_active", False))

    def start(self) -> bool:
        listener = self._load()
        if listener is None:
            return False
        listener.start()
        return True

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def listen_once(self) -> bool:
        listener = self._load()
        return bool(listener is not None and listener.listen_once())

    def cancel_listen_once(self) -> bool:
        if self._listener is None:
            return False
        return bool(self._listener.cancel_listen_once())

    def say(self, text: str) -> bool:
        listener = self._load()
        return bool(listener is not None and listener.say(text))

    def interrupt(self, *, force: bool = False) -> bool:
        if self._listener is None:
            return False
        return bool(self._listener.interrupt(force=force))

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        listener = self._load()
        if listener is None:
            raise AttributeError(name)
        return getattr(listener, name)

    def _load(self) -> Any | None:
        with self._lock:
            if self._listener is not None:
                return self._listener
            if self._failed or not self.dependencies_available:
                return None
            try:
                factory = self._factory
                if factory is None:
                    from app.voice.voice_listener import VoiceListener
                    factory = VoiceListener
                self._listener = factory(
                    on_text=self.on_text,
                    settings=self.settings,
                    auto_start=self._auto_start,
                )
            except Exception as error:
                self.last_error = str(error)
                self._failed = True
                return None
            return self._listener


__all__ = ["LazyVoiceListener"]
