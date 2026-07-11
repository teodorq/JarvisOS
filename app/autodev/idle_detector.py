from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


class IdleDetector:

    def __init__(
        self,
        provider: Callable[[], float] | None = None,
    ) -> None:
        self.provider = provider

    def idle_seconds(self) -> float:
        if self.provider is not None:
            return max(0.0, float(self.provider()))

        try:
            info = _LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(_LASTINPUTINFO)

            if not ctypes.windll.user32.GetLastInputInfo(
                ctypes.byref(info)
            ):
                return 0.0

            tick_count = ctypes.windll.kernel32.GetTickCount()
            elapsed_ms = int(tick_count) - int(info.dwTime)

            return max(0.0, elapsed_ms / 1000.0)

        except Exception:
            return 0.0

    def is_idle(self, required_seconds: float) -> bool:
        return self.idle_seconds() >= max(
            0.0,
            float(required_seconds),
        )
