from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class LongRunningAutonomyScheduler:
    """Normalizes schedules and selects due jobs deterministically."""

    DUE_STATES = {
        "QUEUED",
        "SCHEDULED",
        "WAITING_RESOURCES",
        "RECOVERING",
    }

    def normalize(
        self,
        schedule: dict[str, Any] | None,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self._utc(now)
        value = dict(schedule or {})
        kind = str(value.get("type", "immediate")).strip().casefold()
        if kind not in {"immediate", "once", "interval", "daily"}:
            kind = "immediate"

        normalized: dict[str, Any] = {
            "type": kind,
            "timezone": "UTC",
        }

        if kind == "interval":
            seconds = self._bounded_int(
                value.get(
                    "interval_seconds",
                    int(value.get("interval_minutes", 15)) * 60,
                ),
                60,
                86400 * 30,
            )
            normalized["interval_seconds"] = seconds
            normalized["next_run_at"] = self._iso(
                self._parse(value.get("next_run_at"))
                or current
            )
        elif kind == "daily":
            hour = self._bounded_int(value.get("hour", 3), 0, 23)
            minute = self._bounded_int(value.get("minute", 0), 0, 59)
            normalized.update({"hour": hour, "minute": minute})
            normalized["next_run_at"] = self._iso(
                self._next_daily(current, hour, minute)
            )
        elif kind == "once":
            normalized["next_run_at"] = self._iso(
                self._parse(
                    value.get("run_at", value.get("next_run_at"))
                )
                or current
            )
        else:
            normalized["next_run_at"] = self._iso(current)

        return normalized

    def due_jobs(
        self,
        jobs: list[dict[str, Any]],
        *,
        now: datetime | None = None,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        current = self._utc(now)
        due: list[dict[str, Any]] = []
        for job in jobs:
            if str(job.get("state", "")).upper() not in self.DUE_STATES:
                continue
            attempts = self._bounded_int(
                job.get("attempts", 0),
                0,
                10_000,
            )
            max_attempts = self._bounded_int(
                job.get("max_attempts", 3),
                1,
                10,
            )
            if attempts >= max_attempts:
                continue
            next_run = (
                self._parse(job.get("next_run_at"))
                or self._parse(
                    dict(job.get("schedule", {}) or {}).get("next_run_at")
                )
                or current
            )
            if next_run <= current:
                due.append(dict(job))

        due.sort(
            key=lambda item: (
                -self._bounded_int(item.get("priority", 50), 0, 100),
                str(item.get("next_run_at", "")),
                str(item.get("created_at", "")),
                str(item.get("job_id", "")),
            )
        )
        return due[:max(1, int(limit))]

    def next_after_success(
        self,
        schedule: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> str:
        current = self._utc(now)
        kind = str(schedule.get("type", "immediate")).casefold()
        if kind == "interval":
            seconds = self._bounded_int(
                schedule.get("interval_seconds", 900),
                60,
                86400 * 30,
            )
            return self._iso(current + timedelta(seconds=seconds))
        if kind == "daily":
            return self._iso(
                self._next_daily(
                    current + timedelta(seconds=1),
                    self._bounded_int(schedule.get("hour", 3), 0, 23),
                    self._bounded_int(schedule.get("minute", 0), 0, 59),
                )
            )
        return ""

    @staticmethod
    def is_recurring(schedule: dict[str, Any]) -> bool:
        return str(schedule.get("type", "")).casefold() in {
            "interval",
            "daily",
        }

    @staticmethod
    def _next_daily(
        current: datetime,
        hour: int,
        minute: int,
    ) -> datetime:
        candidate = current.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        if candidate <= current:
            candidate += timedelta(days=1)
        return candidate

    @staticmethod
    def _utc(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is None:
            return current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    @classmethod
    def _parse(cls, value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return cls._utc(parsed)

    @classmethod
    def _iso(cls, value: datetime) -> str:
        return cls._utc(value).isoformat()

    @staticmethod
    def _bounded_int(
        value: Any,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = minimum
        return min(maximum, max(minimum, parsed))
