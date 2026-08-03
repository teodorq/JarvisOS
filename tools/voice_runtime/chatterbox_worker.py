"""Isolated JSON-lines worker for local Chatterbox speech synthesis."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
import inspect
import os
from pathlib import Path
import re
import sys
import traceback
from typing import Any

from voice_mastering import master_waveform, profile_parameters


PROTOCOL = sys.stdout
sys.stdout = sys.stderr


def _reply(request_id: str, **payload: Any) -> None:
    value = {"request_id": request_id, **payload}
    print(json.dumps(value, ensure_ascii=False), file=PROTOCOL, flush=True)


def _bounded(value: object, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(number, high))


def _split_text(text: str, maximum: int = 230) -> list[str]:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > maximum:
            parts = re.split(r"(?<=[,;:])\s+", sentence)
        else:
            parts = [sentence]
        for part in parts:
            candidate = f"{current} {part}".strip()
            if current and len(candidate) > maximum:
                chunks.append(current)
                current = part
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks[:12]


class ChatterboxWorker:
    def __init__(self, reference: Path, output_root: Path, device: str) -> None:
        self.reference = reference.resolve()
        self.output_root = output_root.resolve()
        self.requested_device = device
        self.model: Any | None = None
        self.model_version = ""
        self.device = ""
        self.sample_rate = 24000

    def _select_device(self) -> str:
        import torch

        if self.requested_device in {"cpu", "cuda"}:
            if self.requested_device == "cuda" and not torch.cuda.is_available():
                return "cpu"
            return self.requested_device
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _load(self, model_version: str, exaggeration: float) -> None:
        if self.model is not None and self.model_version == model_version:
            return
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        torch.set_num_threads(max(1, min(8, os.cpu_count() or 4)))
        self.device = self._select_device()
        if self.device == "cuda":
            torch.backends.cudnn.benchmark = True
        with redirect_stdout(sys.stderr):
            loader = ChatterboxMultilingualTTS.from_pretrained
            parameters = inspect.signature(loader).parameters
            if "t3_model" in parameters:
                self.model = loader(
                    device=self.device,
                    t3_model=model_version,
                )
            else:
                self.model = loader(device=self.device)
                model_version = "v2"
            self.model.prepare_conditionals(
                str(self.reference),
                exaggeration=exaggeration,
            )
        self.model_version = model_version
        self.sample_rate = int(self.model.sr)

    def _safe_output(self, value: object) -> Path:
        output = Path(str(value or "")).resolve()
        if self.output_root not in output.parents:
            raise ValueError("Output path is outside the local voice directory.")
        if output.suffix.casefold() != ".wav":
            raise ValueError("Only WAV output is allowed.")
        output.parent.mkdir(parents=True, exist_ok=True)
        return output

    def preload(self, request: dict[str, Any]) -> dict[str, Any]:
        model_version = str(request.get("model_version", "v3"))
        if model_version not in {"v2", "v3"}:
            model_version = "v3"
        exaggeration = _bounded(request.get("exaggeration"), 0.2, 1.0, 0.58)
        self._load(model_version, exaggeration)
        return {
            "ok": True,
            "device": self.device,
            "sample_rate": self.sample_rate,
            "preloaded": True,
        }

    def synthesize(self, request: dict[str, Any]) -> dict[str, Any]:
        import torch
        import torchaudio

        text = str(request.get("text", ""))[:2400]
        chunks = _split_text(text)
        if not chunks:
            raise ValueError("Speech text is empty.")
        output = self._safe_output(request.get("output"))
        language = str(request.get("language", "pl")).casefold()
        model_version = str(request.get("model_version", "v3"))
        if model_version not in {"v2", "v3"}:
            model_version = "v3"
        exaggeration = _bounded(request.get("exaggeration"), 0.2, 1.0, 0.58)
        cfg_weight = _bounded(request.get("cfg_weight"), 0.0, 1.0, 0.0)
        temperature = _bounded(request.get("temperature"), 0.25, 1.2, 0.72)
        repetition_penalty = _bounded(
            request.get("repetition_penalty"), 1.0, 2.0, 1.35
        )
        volume = _bounded(request.get("volume"), 0.25, 1.0, 0.92)
        profile, exaggeration, temperature, pause_seconds = profile_parameters(
            request.get("speech_profile"), exaggeration, temperature
        )
        mastering = request.get("mastering", {})
        if not isinstance(mastering, dict):
            mastering = {}
        self._load(model_version, exaggeration)
        pieces = []
        for index, chunk in enumerate(chunks):
            with torch.inference_mode(), redirect_stdout(sys.stderr):
                audio = self.model.generate(
                    chunk,
                    language_id=language,
                    audio_prompt_path=None,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                    temperature=temperature,
                    repetition_penalty=repetition_penalty,
                )
            pieces.append(audio.detach().cpu())
            if index < len(chunks) - 1:
                pieces.append(torch.zeros(1, int(self.sample_rate * pause_seconds)))
        waveform = torch.cat(pieces, dim=-1)
        waveform = master_waveform(
            waveform,
            self.sample_rate,
            volume=volume,
            enabled=bool(mastering.get("enabled", True)),
            warmth_db=_bounded(mastering.get("warmth_db"), 0.0, 2.0, 0.8),
            presence_db=_bounded(
                mastering.get("presence_db"), 0.0, 2.0, 0.6
            ),
            room_mix=_bounded(mastering.get("room_mix"), 0.0, 0.05, 0.018),
            target_rms=_bounded(
                mastering.get("target_rms"), 0.07, 0.2, 0.13
            ),
            fade_ms=_bounded(mastering.get("fade_ms"), 2.0, 30.0, 10.0),
        )
        temporary = output.with_suffix(".writing.wav")
        torchaudio.save(
            str(temporary), waveform, self.sample_rate,
            encoding="PCM_S", bits_per_sample=16,
        )
        temporary.replace(output)
        return {
            "ok": True,
            "output": str(output),
            "device": self.device,
            "sample_rate": self.sample_rate,
            "chunks": len(chunks),
            "profile": profile,
            "mastered": bool(mastering.get("enabled", True)),
            "watermarked": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    reference = Path(args.reference)
    if not reference.is_file():
        raise FileNotFoundError(reference)
    worker = ChatterboxWorker(reference, Path(args.output_root), args.device)
    for raw_line in sys.stdin:
        request_id = ""
        try:
            request = json.loads(raw_line)
            request_id = str(request.get("request_id", ""))[:64]
            action = request.get("action")
            if action == "preload":
                _reply(request_id, **worker.preload(request))
            elif action == "synthesize":
                _reply(request_id, **worker.synthesize(request))
            else:
                raise ValueError("Unsupported voice action.")
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            _reply(request_id, ok=False, error=f"{type(error).__name__}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
