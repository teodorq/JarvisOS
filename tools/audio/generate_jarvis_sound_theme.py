from __future__ import annotations

from array import array
import math
from pathlib import Path
import wave


SAMPLE_RATE = 48_000
OUTPUT = Path(__file__).resolve().parents[2] / "assets" / "sound_theme"


def _envelope(time: float, duration: float, attack: float = 0.025) -> float:
    release = min(0.2, duration * 0.38)
    rise = min(1.0, time / max(attack, 0.001))
    fall = min(1.0, max(0.0, duration - time) / max(release, 0.001))
    return rise * fall


def _tone(time: float, frequency: float, duration: float, level: float) -> float:
    return math.sin(math.tau * frequency * time) * _envelope(time, duration) * level


def _event(
    time: float,
    start: float,
    duration: float,
    frequency: float,
    level: float,
    *,
    glide: float = 0.0,
) -> float:
    local = time - start
    if local < 0.0 or local >= duration:
        return 0.0
    phase = math.tau * (frequency * local + 0.5 * glide * local * local)
    return math.sin(phase) * _envelope(local, duration) * level


def _sample(name: str, time: float, duration: float) -> float:
    if name == "startup":
        value = _tone(time, 92.0, duration, 0.07)
        value += _event(time, 0.04, 0.38, 330.0, 0.23, glide=650.0)
        value += _event(time, 0.30, 0.42, 520.0, 0.20, glide=720.0)
        value += _event(time, 0.62, 0.46, 720.0, 0.18, glide=510.0)
        return value
    if name == "listening":
        return (
            _event(time, 0.02, 0.22, 660.0, 0.28, glide=690.0)
            + _event(time, 0.10, 0.20, 990.0, 0.15, glide=310.0)
        )
    if name == "thinking":
        return sum(
            _event(time, start, 0.13, frequency, 0.17, glide=180.0)
            for start, frequency in ((0.02, 430.0), (0.16, 560.0), (0.30, 710.0))
        )
    if name == "success":
        return sum(
            _event(time, start, 0.48, frequency, level, glide=45.0)
            for start, frequency, level in (
                (0.02, 523.25, 0.19),
                (0.14, 659.25, 0.17),
                (0.27, 783.99, 0.15),
            )
        )
    if name == "warning":
        return (
            _event(time, 0.02, 0.26, 392.0, 0.24, glide=-65.0)
            + _event(time, 0.29, 0.26, 311.13, 0.22, glide=-45.0)
        )
    if name == "error":
        return (
            _event(time, 0.02, 0.51, 280.0, 0.25, glide=-230.0)
            + _event(time, 0.08, 0.43, 140.0, 0.13, glide=-75.0)
        )
    raise ValueError(name)


def _write(name: str, duration: float) -> None:
    total = int(SAMPLE_RATE * duration)
    samples = array("h")
    for index in range(total):
        time = index / SAMPLE_RATE
        value = math.tanh(_sample(name, time, duration) * 1.35) * 0.82
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))
    path = OUTPUT / f"{name}.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(SAMPLE_RATE)
        stream.writeframes(samples.tobytes())


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    durations = {
        "startup": 1.12,
        "listening": 0.34,
        "thinking": 0.48,
        "success": 0.78,
        "warning": 0.60,
        "error": 0.60,
    }
    for name, duration in durations.items():
        _write(name, duration)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
