"""Local neural Polish voice adapter with a native Windows fallback."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Any
import winsound

from app.core.safe_process import SafeProcessRunner


@dataclass(frozen=True)
class NeuralVoice:
    id: str
    name: str
    languages: list[str]
    gender: str


class LocalNeuralVoiceEngine:
    """Small pyttsx3-compatible client for the isolated neural worker."""

    supports_pitch = False
    VOICE = NeuralVoice(
        id="jarvis-neural-pl",
        name="JARVIS Neural Polish",
        languages=["pl-PL"],
        gender="Male",
    )
    FAILURE_COOLDOWN_SECONDS = 300

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(
            project_root or Path(__file__).resolve().parents[2]
        ).resolve()
        self.config = self._load_config(self.project_root)
        self.python = (
            self.project_root / "runtime" / "voice_env" / "Scripts" / "python.exe"
        )
        self.worker = (
            self.project_root / "tools" / "voice_runtime" / "chatterbox_worker.py"
        )
        self.reference = self.project_root / str(self.config["reference_audio"])
        self.cache_root = self.project_root / "runtime" / "voice_cache"
        self.output_root = self.project_root / "runtime" / "voice_output"
        self._process_runner = SafeProcessRunner(
            project_root=self.project_root,
            allowed_executables=(self.python,),
        )
        self._voice = self.VOICE.id
        self._rate = 158
        self._volume = 0.92
        self._profile = "calm"
        self._message = ""
        self._process: subprocess.Popen[str] | None = None
        self._stderr_handle: Any | None = None
        self._responses: queue.Queue[str] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._lock = threading.RLock()
        self._request_lock = threading.RLock()
        self._prewarm_thread: threading.Thread | None = None
        if bool(self.config.get("prewarm", True)):
            self._prewarm_thread = threading.Thread(
                target=self._background_prewarm,
                name="jarvis-neural-voice-prewarm",
                daemon=True,
            )
            self._prewarm_thread.start()

    @staticmethod
    def _load_config(project_root: Path) -> dict[str, Any]:
        path = project_root / "config" / "b311_b320_neural_voice.json"
        defaults: dict[str, Any] = {
            "enabled": True,
            "reference_audio": (
                "assets/voice/references/"
                "jarvis_style_reference_vtubereels_147563_20260801.mp3"
            ),
            "language": "pl",
            "device": "auto",
            "model_version": "v3",
            "exaggeration": 0.58,
            "cfg_weight": 0.0,
            "temperature": 0.72,
            "repetition_penalty": 1.35,
            "timeout_seconds": 420,
            "prewarm": True,
        }
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            voice = loaded.get("voice", loaded)
            if isinstance(voice, dict):
                defaults.update(voice)
        except (OSError, ValueError, TypeError):
            pass
        direction_path = project_root / "config" / "b351_b360_voice_direction.json"
        try:
            direction = json.loads(direction_path.read_text(encoding="utf-8"))
            mastering = direction.get("mastering", {})
            if isinstance(mastering, dict):
                defaults["mastering"] = mastering
        except (OSError, ValueError, TypeError):
            defaults["mastering"] = {
                "enabled": True,
                "version": "b360",
                "warmth_db": 0.8,
                "presence_db": 0.6,
                "room_mix": 0.018,
                "target_rms": 0.13,
                "fade_ms": 10,
            }
        return defaults

    @classmethod
    def is_available(cls, project_root: str | Path | None = None) -> bool:
        if os.name != "nt":
            return False
        root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
        config = cls._load_config(root)
        if not bool(config.get("enabled", True)):
            return False
        python = root / "runtime" / "voice_env" / "Scripts" / "python.exe"
        package = (
            root / "runtime" / "voice_env" / "Lib" / "site-packages" / "chatterbox"
        )
        worker = root / "tools" / "voice_runtime" / "chatterbox_worker.py"
        reference = root / str(config["reference_audio"])
        failure = root / "runtime" / "voice_output" / "neural_failed.flag"
        if failure.is_file():
            age = time.time() - failure.stat().st_mtime
            if age < cls.FAILURE_COOLDOWN_SECONDS:
                return False
        return all(item.exists() for item in (python, package, worker, reference))

    @classmethod
    def available_voices(cls) -> list[NeuralVoice]:
        return [cls.VOICE]

    def setProperty(self, name: str, value: Any) -> None:  # noqa: N802
        if name == "rate":
            self._rate = max(100, min(int(value), 240))
        elif name == "volume":
            self._volume = max(0.25, min(float(value), 1.0))
        elif name == "voice":
            self._voice = str(value or self.VOICE.id)
        elif name == "speech_profile":
            profile = str(value or "calm").casefold()
            allowed = {"calm", "brief", "result", "confirmation", "warning"}
            self._profile = profile if profile in allowed else "calm"

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
        if not self._message:
            return
        self.output_root.mkdir(parents=True, exist_ok=True)
        cache_dir = self.output_root / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        identity = json.dumps(
            {
                "text": self._message,
                "reference": str(self.reference),
                "reference_mtime": self.reference.stat().st_mtime_ns,
                "model": self.config.get("model_version", "v3"),
                "language": self.config.get("language", "pl"),
                "exaggeration": self.config.get("exaggeration", 0.58),
                "cfg_weight": self.config.get("cfg_weight", 0.0),
                "temperature": self.config.get("temperature", 0.72),
                "speech_profile": self._profile,
                "mastering": self.config.get("mastering", {}),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        output = cache_dir / f"{digest}.wav"
        try:
            if not output.is_file() or output.stat().st_size < 256:
                response = self._request({
                    "action": "synthesize",
                    "text": self._message,
                    "output": str(output),
                    "language": str(self.config.get("language", "pl")),
                    "model_version": str(self.config.get("model_version", "v3")),
                    "exaggeration": float(
                        self.config.get("exaggeration", 0.58)
                    ),
                    "cfg_weight": float(self.config.get("cfg_weight", 0.0)),
                    "temperature": float(self.config.get("temperature", 0.72)),
                    "repetition_penalty": float(
                        self.config.get("repetition_penalty", 1.35)
                    ),
                    "volume": self._volume,
                    "speech_profile": self._profile,
                    "mastering": dict(self.config.get("mastering", {})),
                })
                if not bool(response.get("ok")):
                    message = str(
                        response.get("error") or "Silnik neuralny nie odpowiedzial."
                    )
                    raise RuntimeError(message)
            winsound.PlaySound(str(output), winsound.SND_FILENAME)
            self._clear_failure()
        except Exception:
            self._trip_circuit()
            raise
        finally:
            self._message = ""

    def _background_prewarm(self) -> None:
        try:
            self._request({
                "action": "preload",
                "model_version": str(self.config.get("model_version", "v3")),
                "exaggeration": float(self.config.get("exaggeration", 0.58)),
            })
        except Exception:
            return

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._request_lock:
            return self._request_unlocked(payload)

    def _request_unlocked(self, payload: dict[str, Any]) -> dict[str, Any]:
        process = self._ensure_process()
        if process.stdin is None:
            raise RuntimeError("Brak polaczenia z lokalnym silnikiem glosu.")
        request_id = hashlib.sha256(
            f"{time.time_ns()}:{payload.get('text', '')}".encode("utf-8")
        ).hexdigest()[:16]
        payload["request_id"] = request_id
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()
        timeout = max(30.0, float(self.config.get("timeout_seconds", 420)))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None and self._responses.empty():
                raise RuntimeError("Lokalny silnik glosu zostal zatrzymany.")
            try:
                wait = max(0.01, min(0.25, deadline - time.monotonic()))
                line = self._responses.get(timeout=wait)
            except queue.Empty:
                continue
            try:
                response = json.loads(line)
            except ValueError:
                continue
            if str(response.get("request_id", "")) == request_id:
                return response
        raise TimeoutError("Lokalny silnik glosu przekroczyl limit czasu.")

    def _ensure_process(self) -> subprocess.Popen[str]:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self._process
            self.cache_root.mkdir(parents=True, exist_ok=True)
            self.output_root.mkdir(parents=True, exist_ok=True)
            log_path = self.output_root / "chatterbox.log"
            self._stderr_handle = log_path.open("a", encoding="utf-8")
            env = os.environ.copy()
            env["HF_HOME"] = str(self.cache_root / "huggingface")
            env["HF_HUB_DISABLE_TELEMETRY"] = "1"
            command = [
                str(self.python), "-u", str(self.worker),
                "--reference", str(self.reference),
                "--output-root", str(self.output_root),
                "--device", str(self.config.get("device", "auto")),
            ]
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._process = self._process_runner.open(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._stderr_handle,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
                env=env,
            )
            process = self._process
            self._reader = threading.Thread(
                target=self._read_responses,
                args=(process,),
                name="jarvis-neural-voice-protocol",
                daemon=True,
            )
            self._reader.start()
            return process

    def _read_responses(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            value = line.strip()
            if value:
                self._responses.put(value)

    def stop(self) -> None:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except RuntimeError:
            pass
        with self._lock:
            process = self._process
            self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                process.kill()
        handle = self._stderr_handle
        self._stderr_handle = None
        if handle is not None:
            handle.close()

    def _trip_circuit(self) -> None:
        try:
            self.output_root.mkdir(parents=True, exist_ok=True)
            (self.output_root / "neural_failed.flag").touch()
        except OSError:
            pass
        self.stop()

    def _clear_failure(self) -> None:
        failure = self.output_root / "neural_failed.flag"
        try:
            failure.unlink(missing_ok=True)
        except OSError:
            pass
