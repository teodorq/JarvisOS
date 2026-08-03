from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class SelfDirectedDevelopmentPolicy:
    interval_seconds: float = 60.0
    scan_interval_seconds: float = 300.0
    max_dispatch_per_cycle: int = 1
    max_active_jobs: int = 1
    max_dispatches_per_day: int = 10
    max_consecutive_failures: int = 3
    cooldown_after_failure_seconds: float = 600.0
    rescan_backlog_below: int = 20
    pause_on_waiting_approval: bool = True
    auto_dispatch: bool = False
    auto_approve: bool = False
    auto_rollback: bool = True
    final_validation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any] | None,
    ) -> "SelfDirectedDevelopmentPolicy":
        source = dict(value or {})
        return cls(
            interval_seconds=min(
                86400.0,
                max(30.0, float(source.get("interval_seconds", 60.0))),
            ),
            scan_interval_seconds=min(
                86400.0,
                max(60.0, float(source.get("scan_interval_seconds", 300.0))),
            ),
            max_dispatch_per_cycle=min(
                3,
                max(1, int(source.get("max_dispatch_per_cycle", 1))),
            ),
            max_active_jobs=min(
                3,
                max(1, int(source.get("max_active_jobs", 1))),
            ),
            max_dispatches_per_day=min(
                100,
                max(1, int(source.get("max_dispatches_per_day", 10))),
            ),
            max_consecutive_failures=min(
                10,
                max(1, int(source.get("max_consecutive_failures", 3))),
            ),
            cooldown_after_failure_seconds=min(
                86400.0,
                max(
                    30.0,
                    float(source.get("cooldown_after_failure_seconds", 600.0)),
                ),
            ),
            rescan_backlog_below=min(
                200,
                max(1, int(source.get("rescan_backlog_below", 20))),
            ),
            pause_on_waiting_approval=bool(
                source.get("pause_on_waiting_approval", True)
            ),
            auto_dispatch=bool(source.get("auto_dispatch", False)),
            auto_approve=False,
            auto_rollback=bool(source.get("auto_rollback", True)),
            final_validation=bool(source.get("final_validation", True)),
        )
