"""Reliable wake-word and push-to-talk listener for JARVIS OS."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

import speech_recognition as sr

from app.assistant.natural_language import fold_text
from app.assistant.voice_runtime import VoiceCommandInterpreter, VoiceRuntimeService
from app.voice.tts_runtime import SerializedTTS
from app.voice.voice_loop_runtime import VoiceLoopRuntime


class VoiceListener:
    """Separate background wake-word listening from one-shot manual capture."""

    def __init__(
        self,
        on_text: Callable[[str], None] | None = None,
        *,
        settings: dict[str, Any] | None = None,
        recognizer: Any | None = None,
        microphone: Any | None = None,
        tts: Any | None = None,
        auto_start: bool = True,
    ) -> None:
        runtime = dict(settings or VoiceRuntimeService().settings())
        self.on_text = on_text
        self.settings = runtime
        self.interpreter = VoiceCommandInterpreter(runtime)
        self.command_timeout = float(runtime.get("command_timeout_seconds", 15))
        self.phrase_time_limit = float(runtime.get("phrase_time_limit_seconds", 12))
        self.confirmation_window = float(
            runtime.get("confirmation_window_seconds", 20)
        )
        self.continuous_mode = bool(runtime.get("continuous_mode", False))
        self.interrupt_enabled = bool(runtime.get("interrupt_enabled", True))
        self.language = str(runtime.get("language", "pl-PL"))
        self.recognizer = recognizer or sr.Recognizer()
        self.recognizer.energy_threshold = 350
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.75
        self.recognizer.non_speaking_duration = 0.45
        self.recognizer.operation_timeout = 8
        # Urządzenie audio jest otwierane w wątku nasłuchiwania, nie podczas startu GUI.
        self.microphone = microphone
        self.tts = tts or SerializedTTS(
            rate=int(runtime.get("speech_rate", 158)),
            volume=float(runtime.get("volume", 0.92)),
            pitch=float(runtime.get("pitch", 0.88)),
            language=self.language,
            preferred_gender=str(runtime.get("preferred_gender", "Male")),
            neural_enabled=bool(runtime.get("neural_enabled", True)),
            engine_name=str(runtime.get("voice_engine", "")),
            on_error=self._handle_tts_error,
        )
        self.running = False
        self.thread: threading.Thread | None = None
        self.mode = "wake"
        self.last_wake_time = 0.0
        self.last_command_time = 0.0
        self.confirmation_deadline = 0.0
        self._tts_echo = ""
        self._tts_echo_deadline = 0.0
        self._manual_request = threading.Event()
        self._manual_cancel = threading.Event()
        self._manual_active = False
        self._state_lock = threading.RLock()
        self._runtime = VoiceLoopRuntime(self)
        if auto_start:
            self.start()

    @property
    def manual_active(self) -> bool:
        with self._state_lock:
            return self._manual_active

    def say(self, text: str) -> bool:
        message = self.interpreter.normalize(text)
        accepted = bool(self.tts.say(message, replace_pending=True))
        if not accepted:
            return False
        self._tts_echo = fold_text(message)
        self._tts_echo_deadline = time.monotonic() + max(
            2.0, min(8.0, len(message) / 10.0 + 1.0)
        )
        return True

    def interrupt(self, *, force: bool = False) -> bool:
        if not force and not self.interrupt_enabled:
            return False
        return bool(self.tts.interrupt())

    def listen_once(self) -> bool:
        with self._state_lock:
            if self._manual_active:
                return False
            self._manual_active = True
        self.start()
        self._manual_cancel.clear()
        self._manual_request.set()
        self._emit_state("prompt")
        self.say("Słucham")
        return True

    def cancel_listen_once(self) -> bool:
        if not self.manual_active:
            return False
        self._manual_cancel.set()
        self._runtime.finish_manual("cancelled")
        return True

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(
            target=self._loop,
            name="jarvis-voice-listener",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        self._manual_cancel.set()
        self.interrupt(force=True)
        self.tts.close()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.5)

    def _emit(self, text: str) -> None:
        if self.on_text:
            self.on_text(text)

    def _emit_state(self, state: str) -> None:
        self._emit(f"[voice_state] {state}")

    def _handle_tts_error(self, error: Exception) -> None:
        self._emit(f"[voice_error] Synteza mowy: {error}")

    def _is_tts_echo(self, text: str) -> bool:
        if time.monotonic() > self._tts_echo_deadline:
            return False
        folded = fold_text(self.interpreter.normalize(text))
        return bool(folded) and folded in {
            self._tts_echo,
            "slucham",
            "jarvis slucham",
        }

    def _emit_command(self, text: str) -> None:
        command = self.interpreter.normalize(text)
        if not command:
            return
        self.last_command_time = time.time()
        self.confirmation_deadline = (
            self.last_command_time + self.confirmation_window
        )
        self.mode = "wake"
        self._emit(command)

    def _loop(self) -> None:
        # Runtime checks retained in VoiceLoopRuntime:
        # if self.tts.speaking:
        # if self._is_tts_echo(normalized):
        self._runtime.run()
