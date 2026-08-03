from __future__ import annotations

from typing import Any

from app.ai.planner_llm import PlannerLLM
from app.cloud.client import CloudPlannerClient, CloudPlannerError


class HybridPlanner:
    """Uses cloud planning when configured and fails back to the desktop."""

    def __init__(
        self,
        local_planner: PlannerLLM | None = None,
        cloud_client: CloudPlannerClient | None = None,
    ) -> None:
        self.local_planner = local_planner or PlannerLLM()
        self.cloud_client = cloud_client or CloudPlannerClient()
        self.last_backend = "local"
        self.last_cloud_error = ""

    def create_plan(self, user_command: str) -> dict[str, Any]:
        if self.cloud_client.is_configured:
            try:
                plan = self.cloud_client.create_plan(user_command)
                self.last_backend = "cloud"
                self.last_cloud_error = ""
                return plan
            except CloudPlannerError as error:
                self.last_cloud_error = type(error).__name__
        self.last_backend = "local"
        return self.local_planner.create_plan(user_command)

    def detect_handler(self, user_command: str) -> str:
        return self.local_planner.detect_handler(user_command)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.cloud_client.is_configured,
            "last_backend": self.last_backend,
            "last_cloud_error": self.last_cloud_error,
            "fallback_enabled": True,
        }
