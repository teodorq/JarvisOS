"""Blocking microphone loop used by VoiceListener."""

from __future__ import annotations

import time

import speech_recognition as sr


class VoiceLoopRuntime:
    def __init__(self, owner) -> None:
        self.owner = owner

    def microphone(self):
        """Create the input device only inside the background voice thread."""
        owner = self.owner
        if owner.microphone is None:
            owner.microphone = sr.Microphone()
        return owner.microphone

    def capture(self, *, timeout: float, phrase_limit: float) -> str:
        owner = self.owner
        with self.microphone() as source:
            audio = owner.recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_limit,
            )
        return owner.recognizer.recognize_google(
            audio,
            language=owner.language,
        )

    def wait_for_tts(self) -> None:
        owner = self.owner
        waiter = getattr(owner.tts, "wait_until_idle", None)
        if callable(waiter):
            waiter(timeout=8.0)
        else:
            time.sleep(0.1)
            while owner.running and getattr(owner.tts, "speaking", False):
                time.sleep(0.05)
        time.sleep(0.25)

    def finish_manual(self, state: str) -> None:
        owner = self.owner
        with owner._state_lock:
            was_active = owner._manual_active
            owner._manual_active = False
        owner._manual_request.clear()
        owner.mode = "wake"
        if was_active and state:
            owner._emit_state(state)

    def manual_cycle(self) -> None:
        owner = self.owner
        try:
            self.wait_for_tts()
            if owner._manual_cancel.is_set():
                return
            owner._emit_state("listening")
            text = self.capture(
                timeout=6,
                phrase_limit=owner.phrase_time_limit,
            )
            if owner._manual_cancel.is_set():
                return
            normalized = owner.interpreter.normalize(text)
            if not normalized or owner._is_tts_echo(normalized):
                self.finish_manual("not_understood")
                return
            owner._emit_state("recognized")
            self.finish_manual("")
            owner._emit_command(normalized)
        except sr.WaitTimeoutError:
            self.finish_manual("timeout")
        except sr.UnknownValueError:
            self.finish_manual("not_understood")
        except Exception as error:
            self.finish_manual("error")
            owner._emit(f"[voice_error] {error}")
        finally:
            owner._manual_cancel.clear()

    def handle_background_text(self, text: str) -> None:
        owner = self.owner
        normalized = owner.interpreter.normalize(text)
        if not normalized or owner._is_tts_echo(normalized):
            return
        if owner.interpreter.is_interrupt(normalized):
            owner.interrupt()
            return
        confirmation = owner.interpreter.confirmation(normalized)
        if confirmation is not None and time.time() <= owner.confirmation_deadline:
            owner._emit(normalized)
            return
        wake, command = owner.interpreter.wake_and_command(normalized)
        if wake and command:
            owner._emit_command(command)
        elif wake:
            owner.listen_once()
        elif owner.continuous_mode:
            owner._emit_command(normalized)

    def calibrate(self) -> bool:
        owner = self.owner
        try:
            with self.microphone() as source:
                owner.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=0.6,
                )
            return True
        except Exception as error:
            owner._emit(f"[voice_error] Mikrofon niedostępny: {error}")
            owner.running = False
            return False

    def run(self) -> None:
        owner = self.owner
        if not self.calibrate():
            return
        while owner.running:
            if owner._manual_request.is_set():
                self.manual_cycle()
                continue
            if getattr(owner.tts, "speaking", False):
                time.sleep(0.05)
                continue
            try:
                text = self.capture(timeout=1, phrase_limit=5)
                self.handle_background_text(text)
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                continue
            except Exception as error:
                owner._emit(f"[voice_error] {error}")
                time.sleep(0.25)
