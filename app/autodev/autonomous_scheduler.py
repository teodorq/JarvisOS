from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class AutonomousSchedulePolicy:
    interval_seconds: float = 30.0
    max_runs: int = 10

    def validate(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError(
                "interval_seconds musi być większe od 0."
            )
        if self.max_runs < 1:
            raise ValueError(
                "max_runs musi być większe od 0."
            )


class AutonomousScheduler:

    def __init__(
        self,
        callback: Callable[[], dict[str, Any]],
        policy: AutonomousSchedulePolicy | None = None,
    ) -> None:
        self.callback = callback
        self.policy = policy or AutonomousSchedulePolicy()
        self.policy.validate()
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True

    def run(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for index in range(self.policy.max_runs):
            if self.stop_requested:
                break

            results.append(self.callback())

            if index + 1 < self.policy.max_runs:
                time.sleep(self.policy.interval_seconds)

        return results
