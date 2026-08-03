from __future__ import annotations

from typing import Any


PROFILE_PAUSES = {
    "calm": 0.16,
    "brief": 0.15,
    "result": 0.14,
    "confirmation": 0.17,
    "warning": 0.19,
}


def profile_parameters(
    profile: object,
    exaggeration: float,
    temperature: float,
) -> tuple[str, float, float, float]:
    name = str(profile or "calm").casefold()
    if name not in PROFILE_PAUSES:
        name = "calm"
    adjustments = {
        "calm": (-0.03, -0.03),
        "brief": (-0.01, -0.02),
        "result": (-0.04, -0.04),
        "confirmation": (0.03, -0.02),
        "warning": (0.05, -0.05),
    }
    energy, variation = adjustments[name]
    return (
        name,
        max(0.2, min(1.0, exaggeration + energy)),
        max(0.25, min(1.2, temperature + variation)),
        PROFILE_PAUSES[name],
    )


def master_waveform(
    waveform: Any,
    sample_rate: int,
    *,
    volume: float,
    enabled: bool = True,
    warmth_db: float = 0.8,
    presence_db: float = 0.6,
    room_mix: float = 0.018,
    target_rms: float = 0.13,
    fade_ms: float = 10.0,
) -> Any:
    """Apply subtle speech cleanup without changing speaker identity or pitch."""
    import torch

    audio = waveform.float()
    if not enabled or audio.numel() == 0:
        return torch.clamp(audio * volume, -1.0, 1.0)
    import torchaudio.functional as audio_fx

    audio = audio - audio.mean(dim=-1, keepdim=True)
    audio = audio_fx.highpass_biquad(audio, sample_rate, 62.0)
    audio = audio_fx.lowpass_biquad(audio, sample_rate, 10_800.0)
    audio = audio_fx.equalizer_biquad(audio, sample_rate, 165.0, warmth_db, 0.8)
    audio = audio_fx.equalizer_biquad(audio, sample_rate, 2_650.0, presence_db, 0.75)
    mix = max(0.0, min(0.05, float(room_mix)))
    for seconds, level in ((0.019, mix), (0.041, mix * 0.55)):
        delay = int(sample_rate * seconds)
        if delay < audio.shape[-1]:
            audio[..., delay:] += audio[..., :-delay].clone() * level
    rms = float(torch.sqrt(torch.mean(audio.square())).item())
    if rms > 1e-6:
        gain = max(0.72, min(1.65, float(target_rms) / rms))
        audio = audio * gain
    fade = min(audio.shape[-1] // 3, int(sample_rate * fade_ms / 1000.0))
    if fade > 1:
        ramp = torch.linspace(0.0, 1.0, fade, dtype=audio.dtype)
        audio[..., :fade] *= ramp
        audio[..., -fade:] *= ramp.flip(0)
    peak = float(audio.abs().max().item())
    if peak > 0.96:
        audio = audio * (0.96 / peak)
    return torch.clamp(audio * volume, -1.0, 1.0)
