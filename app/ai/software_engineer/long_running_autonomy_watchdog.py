from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class LongRunningAutonomyWatchdog:
    """Detects interrupted jobs and provides durable heartbeats."""

    def heartbeat(
        self,
        job: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        value = dict(job)
        value["heartbeat_at"] = self._iso(now)
        value["updated_at"] = value["heartbeat_at"]
        return value

    def is_stale(
        self,
        job: dict[str, Any],
        *,
        stale_after_seconds: float,
        now: datetime | None = None,
    ) -> bool:
        if str(job.get("state", "")).upper() != "RUNNING":
            return False
        heartbeat = self._parse(
            job.get("heartbeat_at")
            or job.get("updated_at")
            or job.get("started_at")
        )
        if heartbeat is None:
            return True
        age = (
            self._utc(now) - heartbeat
        ).total_seconds()
        return age >= max(30.0, float(stale_after_seconds))

    def recover(
        self,
        jobs: list[dict[str, Any]],
        *,
        stale_after_seconds: float,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        for item in jobs:
            if not self.is_stale(
                item,
                stale_after_seconds=stale_after_seconds,
                now=now,
            ):
                continue
            job = dict(item)
            policy = str(job.get("restart_policy", "RESUME")).upper()
            job["state"] = (
                "RECOVERING"
                if policy == "RESUME"
                else "FAILED"
            )
            job["last_error"] = (
                "Wykryto przerwany przebieg po restarcie."
            )
            job["updated_at"] = self._iso(now)
            recovered.append(job)
        return recovered

    @staticmethod
    def _utc(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is None:
            return current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    @classmethod
    def _iso(cls, value: datetime | None) -> str:
        return cls._utc(value).isoformat()

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
