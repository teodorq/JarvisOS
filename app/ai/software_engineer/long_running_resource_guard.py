from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class LongRunningResourceGuard:
    """Blocks autonomous work when host resources are unsafe."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        sample_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.sample_provider = sample_provider or self._system_sample

    def evaluate(
        self,
        policy: dict[str, Any],
        *,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = {
            **dict(policy),
            **dict(overrides or {}),
        }
        sample = dict(self.sample_provider() or {})
        reasons: list[str] = []

        cpu = self._float(sample.get("cpu_percent"), 0.0)
        memory = self._float(sample.get("memory_percent"), 0.0)
        disk = self._float(sample.get("disk_free_gb"), 9999.0)
        on_ac_power = sample.get("on_ac_power")

        max_cpu = self._bounded(
            values.get("max_cpu_percent", 85.0),
            20.0,
            98.0,
        )
        max_memory = self._bounded(
            values.get("max_memory_percent", 90.0),
            20.0,
            98.0,
        )
        min_disk = self._bounded(
            values.get("min_disk_free_gb", 2.0),
            0.5,
            100.0,
        )

        if cpu > max_cpu:
            reasons.append(
                f"CPU {cpu:.1f}% przekracza limit {max_cpu:.1f}%."
            )
        if memory > max_memory:
            reasons.append(
                f"RAM {memory:.1f}% przekracza limit {max_memory:.1f}%."
            )
        if disk < min_disk:
            reasons.append(
                f"Wolne miejsce {disk:.2f} GB jest poniżej {min_disk:.2f} GB."
            )
        if bool(values.get("require_ac_power", False)) and on_ac_power is False:
            reasons.append("Komputer nie jest podłączony do zasilania.")

        return {
            "allowed": not reasons,
            "status": (
                "RESOURCES_AVAILABLE"
                if not reasons
                else "RESOURCES_BLOCKED"
            ),
            "sample": sample,
            "limits": {
                "max_cpu_percent": max_cpu,
                "max_memory_percent": max_memory,
                "min_disk_free_gb": min_disk,
                "require_ac_power": bool(
                    values.get("require_ac_power", False)
                ),
            },
            "reasons": reasons,
        }

    def _system_sample(self) -> dict[str, Any]:
        try:
            import psutil

            disk = psutil.disk_usage(str(self.project_root.anchor or "/"))
            battery = (
                psutil.sensors_battery()
                if hasattr(psutil, "sensors_battery")
                else None
            )
            return {
                "cpu_percent": float(psutil.cpu_percent(interval=None)),
                "memory_percent": float(
                    psutil.virtual_memory().percent
                ),
                "disk_free_gb": float(
                    disk.free / (1024 ** 3)
                ),
                "on_ac_power": (
                    None
                    if battery is None
                    else bool(battery.power_plugged)
                ),
            }
        except Exception:
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_free_gb": 9999.0,
                "on_ac_power": None,
            }

    @staticmethod
    def _float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _bounded(
        cls,
        value: Any,
        minimum: float,
        maximum: float,
    ) -> float:
        return min(
            maximum,
            max(minimum, cls._float(value, minimum)),
        )
