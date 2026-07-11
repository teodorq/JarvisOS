from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class BackgroundAutonomyPolicy:
    enabled: bool = True
    idle_seconds_required: float = 300.0
    max_cpu_percent: float = 65.0
    max_cycles_per_run: int = 2
    check_interval_seconds: float = 5.0
    stop_on_user_activity: bool = True
    background_enabled: bool = True

    def validate(self) -> None:
        if self.idle_seconds_required < 0:
            raise ValueError(
                "idle_seconds_required nie może być ujemne."
            )
        if not 0 <= self.max_cpu_percent <= 100:
            raise ValueError(
                "max_cpu_percent musi być w zakresie 0-100."
            )
        if self.max_cycles_per_run < 1:
            raise ValueError(
                "max_cycles_per_run musi być większe od 0."
            )
        if self.check_interval_seconds <= 0:
            raise ValueError(
                "check_interval_seconds musi być większe od 0."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
