from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from app.ai.planner_llm import PlannerLLM
from app.cloud.client import CloudPlannerClient, CloudPlannerError


class HybridPlanner:
    """Uses cloud planning when configured and fails back to the desktop."""

    def __init__(
        self,
        local_planner: PlannerLLM | None = None,
        cloud_client: CloudPlannerClient | None = None,
        failure_cooldown_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.local_planner = local_planner or PlannerLLM()
        self.cloud_client = cloud_client or CloudPlannerClient()
        self.last_backend = "local"
        self.last_cloud_error = ""
        self.failure_cooldown_seconds = _bounded_cooldown(
            failure_cooldown_seconds
            if failure_cooldown_seconds is not None
            else _cooldown_from_environment()
        )
        self._clock = clock
        self._retry_after = 0.0

    def create_plan(self, user_command: str) -> dict[str, Any]:
        if self.cloud_client.is_configured and not self._circuit_open():
            try:
                plan = self.cloud_client.create_plan(user_command)
                self.last_backend = "cloud"
                self.last_cloud_error = ""
                self._retry_after = 0.0
                return plan
            except CloudPlannerError as error:
                self.last_cloud_error = type(error).__name__
                self._retry_after = (
                    self._clock() + self.failure_cooldown_seconds
                )
        self.last_backend = "local"
        return self.local_planner.create_plan(user_command)

    def detect_handler(self, user_command: str) -> str:
        return self.local_planner.detect_handler(user_command)

    def status(self) -> dict[str, Any]:
        retry_in_seconds = max(0.0, self._retry_after - self._clock())
        return {
            "configured": self.cloud_client.is_configured,
            "last_backend": self.last_backend,
            "last_cloud_error": self.last_cloud_error,
            "fallback_enabled": True,
            "circuit_open": retry_in_seconds > 0,
            "retry_in_seconds": round(retry_in_seconds, 1),
        }

    def _circuit_open(self) -> bool:
        return self._clock() < self._retry_after


def _cooldown_from_environment() -> float:
    value = (
        os.getenv("JARVIS_OS_CLOUD_FAILURE_COOLDOWN_SECONDS", "").strip()
        or os.getenv("JARVIS_CLOUD_FAILURE_COOLDOWN_SECONDS", "60").strip()
    )
    try:
        return float(value)
    except ValueError:
        return 60.0


def _bounded_cooldown(value: float) -> float:
    return min(max(float(value), 5.0), 900.0)
