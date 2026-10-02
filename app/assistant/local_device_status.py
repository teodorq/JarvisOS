from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def _duration_text(total_seconds: float) -> str:
    minutes = max(0, int(total_seconds) // 60)
    days, remaining = divmod(minutes, 24 * 60)
    hours, minutes = divmod(remaining, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} d")
    if hours or days:
        parts.append(f"{hours} godz.")
    parts.append(f"{minutes} min")
    return " ".join(parts)


def format_local_device_status(
    *,
    provider: Any | None = None,
    now: datetime | None = None,
) -> str:
    """Return a concise local health snapshot without external services."""
    try:
        if provider is None:
            import psutil as provider  # type: ignore[no-redef]
        current = now or datetime.now()
        cpu = float(provider.cpu_percent(interval=None))
        memory = float(provider.virtual_memory().percent)
        root = Path.cwd().anchor or "/"
        disk = provider.disk_usage(root)
        free_gb = float(disk.free) / (1024 ** 3)
        uptime = (current - datetime.fromtimestamp(provider.boot_time())).total_seconds()
        battery = (
            provider.sensors_battery()
            if hasattr(provider, "sensors_battery")
            else None
        )
    except Exception:
        return "Nie udało się teraz odczytać stanu komputera."

    if battery is None:
        power = "bateria niewykryta"
    else:
        source = "zasilanie sieciowe" if battery.power_plugged else "bateria"
        power = f"{source}, poziom {float(battery.percent):.0f}%"
    return (
        f"Stan komputera: CPU {cpu:.0f}%, RAM {memory:.0f}%, "
        f"wolne miejsce {free_gb:.1f} GB. "
        f"Czas działania: {_duration_text(uptime)}. Zasilanie: {power}."
    )


__all__ = ["format_local_device_status"]
