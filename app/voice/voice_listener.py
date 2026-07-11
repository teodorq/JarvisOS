import threading
import time
import speech_recognition as sr
import pyttsx3


class VoiceListener:
    def __init__(self, on_text=None):
        self.on_text = on_text
        self.running = False
        self.thread = None

        self.mode = "wake"
        self.last_wake_time = 0
        self.last_command_time = 0

        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 350
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        self.microphone = sr.Microphone()

        self.tts = pyttsx3.init()
        self.tts.setProperty("rate", 170)

    def say(self, text: str):
        try:
            self.tts.say(text)
            self.tts.runAndWait()
        except Exception:
            pass

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _emit(self, text: str):
        if self.on_text:
            self.on_text(text)

    def _is_wake_word(self, text: str) -> bool:
        return "jarvis" in text or "dżarwis" in text or "jervis" in text

    def _is_confirmation(self, text: str) -> bool:
        confirmations = [
            "tak", "ta", "wykonaj", "potwierdzam", "ok", "okej",
            "nie", "anuluj", "stop", "nie wykonuj"
        ]
        return text in confirmations

    def _loop(self):
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            self._emit(f"[voice_error] Mikrofon niedostępny: {e}")
            return

        while self.running:
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(
                        source,
                        timeout=5,
                        phrase_time_limit=6
                    )

                text = self.recognizer.recognize_google(audio, language="pl-PL")
                text = text.lower().strip()

                if not text:
                    continue

                # TAK/NIE przepuszczamy zawsze przez 15 sekund po komendzie
                if self._is_confirmation(text):
                    self._emit(text)
                    self.mode = "wake"
                    continue

                # TRYB WAKE
                if self.mode == "wake":
                    if self._is_wake_word(text):
                        self.mode = "command"
                        self.last_wake_time = time.time()
                        self.say("Słucham")
                        self._emit("jarvis")
                    continue

                # TRYB KOMENDY
                if self.mode == "command":
                    if time.time() - self.last_wake_time > 12:
                        self.mode = "wake"
                        continue

                    if self._is_wake_word(text):
                        self.say("Słucham")
                        self.last_wake_time = time.time()
                        continue

                    self.last_command_time = time.time()
                    self.mode = "wake"
                    self._emit(text)

            except sr.WaitTimeoutError:
                if self.mode == "command" and time.time() - self.last_wake_time > 12:
                    self.mode = "wake"
                continue
            except sr.UnknownValueError:
                continue
            except Exception as e:
                self._emit(f"[voice_error] {e}")
                continue