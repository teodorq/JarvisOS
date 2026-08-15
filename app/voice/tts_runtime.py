"""Serialized and self-healing local text-to-speech runtime for JARVIS OS."""

from __future__ import annotations

from collections.abc import Callable
import queue
import threading
import time
from typing import Any

import pyttsx3

from app.voice.speech_director import PolishSpeechDirector


def _default_engine_factory(
    *, neural_enabled: bool = True, engine_name: str = ""
) -> Any:
    selected = str(engine_name or "").strip().upper()
    if selected == "PYTTSX3_DEFAULT":
        try:
            from app.voice.system_sapi_engine import WindowsSystemSapiEngine

            if WindowsSystemSapiEngine.is_available():
                return WindowsSystemSapiEngine()
        except Exception:
            pass
        return pyttsx3.init()
    if selected == "PYTTSX3":
        return pyttsx3.init()
    try:
        from app.voice.cloud_voice_engine import (
            CloudVoiceEngine,
            requested_cloud_provider,
        )

        provider = requested_cloud_provider(selected)
        if provider and CloudVoiceEngine.is_available(provider):
            return CloudVoiceEngine.from_environment(provider)
    except Exception:
        pass
    if neural_enabled:
        try:
            from app.voice.neural_engine import LocalNeuralVoiceEngine

            if LocalNeuralVoiceEngine.is_available():
                return LocalNeuralVoiceEngine()
        except Exception:
            pass
    try:
        from app.voice.onecore_engine import WindowsOneCoreEngine

        if WindowsOneCoreEngine.is_available():
            return WindowsOneCoreEngine()
    except Exception:
        pass
    return pyttsx3.init()


class SerializedTTS:
    """Serialize speech, recover the engine and keep the worker alive."""

    _STOP = object()

    def __init__(
        self,
        *,
        rate: int = 158,
        volume: float = 0.92,
        pitch: float = 0.88,
        language: str = "pl-PL",
        preferred_gender: str = "Male",
        neural_enabled: bool = True,
        engine_name: str = "",
        engine_factory: Callable[[], Any] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.rate = int(rate)
        self.volume = max(0.25, min(float(volume), 1.0))
        self.pitch = max(0.7, min(float(pitch), 1.2))
        self.language = str(language or "pl-PL")
        self.preferred_gender = str(preferred_gender or "")
        self.neural_enabled = bool(neural_enabled)
        self.engine_name = str(engine_name or "").strip().upper()
        self._custom_engine_factory = engine_factory is not None
        self.engine_factory = engine_factory or (
            lambda: _default_engine_factory(
                neural_enabled=self.neural_enabled,
                engine_name=self.engine_name,
            )
        )
        self.on_error = on_error
        self.director = PolishSpeechDirector()
        self._queue: queue.Queue[object] = queue.Queue()
        self._lock = threading.RLock()
        self._thread_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._engine_ready = threading.Event()
        self._engine: Any | None = None
        self._generation = 0
        self._speaking = False
        self._spoken_count = 0
        self._failed_count = 0
        self._last_error = ""
        self._thread: threading.Thread | None = None
        self._start_worker()

    @property
    def speaking(self) -> bool:
        with self._lock:
            return self._speaking

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._speaking or self._queue.unfinished_tasks > 0

    @property
    def worker_alive(self) -> bool:
        with self._thread_lock:
            return bool(self._thread is not None and self._thread.is_alive())

    def status(self) -> dict[str, Any]:
        worker_alive = self.worker_alive
        with self._lock:
            return {
                "worker_alive": worker_alive,
                "speaking": self._speaking,
                "busy": self._speaking or self._queue.unfinished_tasks > 0,
                "queued": int(self._queue.qsize()),
                "spoken_count": self._spoken_count,
                "failed_count": self._failed_count,
                "last_error": self._last_error,
                "engine": type(self._engine).__name__ if self._engine else "",
            }

    def say(self, text: object, *, replace_pending: bool = True) -> bool:
        directed = self.director.direct(text)
        message = directed.text
        if not message or self._stop_event.is_set():
            return False

        self._ensure_worker()
        with self._lock:
            if replace_pending:
                self._generation += 1
            generation = self._generation
            active_engine = (
                self._engine if replace_pending and self._speaking else None
            )

        if replace_pending:
            self._clear_pending()
            if active_engine is not None and self._cross_thread_stop_safe(active_engine):
                self._stop_engine(active_engine)

        self._queue.put((generation, message, directed.profile))
        self._ensure_worker()
        return True

    def wait_until_idle(self, timeout: float = 8.0) -> bool:
        """Wait until queued speech and the current utterance have finished."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while time.monotonic() <= deadline:
            with self._lock:
                speaking = self._speaking
            unfinished = self._queue.unfinished_tasks
            if self._engine_ready.is_set() and not speaking and unfinished == 0:
                return True
            if unfinished and not self.worker_alive:
                self._ensure_worker()
            time.sleep(0.02)
        return False

    def interrupt(self) -> bool:
        if self._stop_event.is_set():
            return False

        with self._lock:
            self._generation += 1
            engine = self._engine

        self._clear_pending()
        if engine is None or not self._cross_thread_stop_safe(engine):
            return True
        return self._stop_engine(engine)

    def close(self, timeout: float = 2.0) -> None:
        if self._stop_event.is_set():
            return

        self.interrupt()
        self._stop_event.set()
        self._queue.put(self._STOP)
        with self._thread_lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout)))

    def _start_worker(self) -> bool:
        with self._thread_lock:
            if self._stop_event.is_set():
                return False
            if self._thread is not None and self._thread.is_alive():
                return True
            self._engine_ready.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="jarvis-tts-worker",
                daemon=True,
            )
            self._thread.start()
            return True

    def _ensure_worker(self) -> bool:
        return self.worker_alive or self._start_worker()

    def _run(self) -> None:
        engine: Any | None = self._create_engine()
        with self._lock:
            self._engine = engine
        self._engine_ready.set()
        try:
            while not self._stop_event.is_set():
                item = self._queue.get()
                try:
                    if item is self._STOP:
                        return

                    generation, message, profile = item
                    with self._lock:
                        if generation != self._generation:
                            continue

                    if engine is None:
                        engine = self._create_engine()
                        with self._lock:
                            self._engine = engine
                    if engine is None:
                        continue

                    with self._lock:
                        self._speaking = True
                    spoken = False
                    try:
                        self._speak(engine, message, profile)
                        spoken = True
                    except Exception as error:
                        self._report_error(error)
                        engine = self._recover_engine(engine)
                        with self._lock:
                            self._engine = engine
                            retry_current = (
                                engine is not None
                                and generation == self._generation
                                and not self._stop_event.is_set()
                            )
                        if retry_current:
                            try:
                                self._speak(engine, message, profile)
                                spoken = True
                            except Exception as fallback_error:
                                self._report_error(fallback_error)
                                self._stop_engine(engine)
                                engine = None
                                with self._lock:
                                    self._engine = None
                    finally:
                        with self._lock:
                            self._speaking = False
                            if spoken:
                                self._spoken_count += 1
                finally:
                    self._queue.task_done()
        finally:
            with self._lock:
                self._speaking = False
                self._engine = None
            if engine is not None:
                self._stop_engine(engine, report=False)

    @staticmethod
    def _speak(engine: Any, message: str, profile: str) -> None:
        try:
            engine.setProperty("speech_profile", profile)
        except Exception:
            pass
        engine.say(message)
        engine.runAndWait()

    def _create_engine(self) -> Any | None:
        try:
            return self._configure_engine(
                self.engine_factory(),
                preserve_system_default=self.engine_name in {
                    "PYTTSX3", "PYTTSX3_DEFAULT",
                },
            )
        except Exception as error:
            self._report_error(error)
            return self._create_native_fallback()

    def _create_native_fallback(self) -> Any | None:
        if self._custom_engine_factory:
            return None
        try:
            from app.voice.onecore_engine import WindowsOneCoreEngine

            if WindowsOneCoreEngine.is_available():
                return self._configure_engine(
                    WindowsOneCoreEngine(), preserve_system_default=False
                )
        except Exception as error:
            self._report_error(error)
        try:
            return self._configure_engine(
                pyttsx3.init(), preserve_system_default=False
            )
        except Exception as error:
            self._report_error(error)
            return None

    def _configure_engine(
        self, engine: Any, *, preserve_system_default: bool
    ) -> Any:
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)
        if not preserve_system_default:
            if bool(getattr(engine, "supports_pitch", False)):
                engine.setProperty("pitch", self.pitch)
            voice_id = self._preferred_voice_id(engine)
            if voice_id:
                engine.setProperty("voice", voice_id)
        return engine

    def _preferred_voice_id(self, engine: Any) -> str:
        getter = getattr(engine, "getProperty", None)
        if not callable(getter):
            return ""
        try:
            voices = list(getter("voices") or [])
        except Exception:
            return ""
        language = self.language.casefold().replace("_", "-")
        preferred_gender = self.preferred_gender.casefold()
        candidates: list[tuple[int, str]] = []
        for voice in voices:
            voice_id = str(getattr(voice, "id", "") or "")
            name = str(getattr(voice, "name", "") or "")
            languages = " ".join(
                item.decode(errors="ignore")
                if isinstance(item, bytes) else str(item)
                for item in list(getattr(voice, "languages", []) or [])
            )
            haystack = (
                f"{voice_id} {name} {languages}".casefold().replace("_", "-")
            )
            if (
                language not in haystack
                and language.split("-", 1)[0] not in haystack
            ):
                continue
            gender = str(getattr(voice, "gender", "") or "").casefold()
            score = 10 + (
                5 if preferred_gender and preferred_gender == gender else 0
            )
            candidates.append((score, voice_id))
        return max(candidates, default=(0, ""))[1]

    def _recover_engine(self, engine: Any) -> Any | None:
        self._stop_engine(engine, report=False)
        fallback = self._create_native_fallback()
        return fallback if fallback is not None else self._create_engine()


    @staticmethod
    def _cross_thread_stop_safe(engine: Any) -> bool:
        """SAPI/pyttsx3 objects must only be controlled by their owner thread."""
        declared = getattr(engine, "cross_thread_stop_safe", None)
        if declared is not None:
            return bool(declared)
        module = str(type(engine).__module__ or "").casefold()
        if module == "pyttsx3" or module.startswith("pyttsx3."):
            return False
        return True

    def _stop_engine(self, engine: Any, *, report: bool = True) -> bool:
        try:
            engine.stop()
            return True
        except Exception as error:
            if report:
                self._report_error(error)
            return False

    def _clear_pending(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            else:
                self._queue.task_done()
                if item is self._STOP:
                    self._queue.put(self._STOP)
                    return

    def _report_error(self, error: Exception) -> None:
        with self._lock:
            self._failed_count += 1
            self._last_error = f"{type(error).__name__}: {error}"[:500]
        if self.on_error is not None:
            try:
                self.on_error(error)
            except Exception:
                return
