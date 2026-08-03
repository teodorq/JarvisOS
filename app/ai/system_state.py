from __future__ import annotations

from typing import Any

from app.cloud.client import (
    CloudPlannerClient,
    CloudPlannerError,
    CloudPlannerSettings,
)


class SystemState:

    def __init__(self, cloud_client: CloudPlannerClient | None = None):
        self.brain_online = True
        self.vision_online = True
        self.memory_online = True
        self.voice_online = False
        self.agent_online = True
        settings = CloudPlannerSettings.from_environment()
        self.cloud_client = cloud_client or CloudPlannerClient(
            CloudPlannerSettings(
                base_url=settings.base_url,
                api_token=settings.api_token,
                timeout_seconds=min(settings.timeout_seconds, 15.0),
            )
        )

    def as_dict(self):
        return {
            "brain": self.brain_online,
            "vision": self.vision_online,
            "memory": self.memory_online,
            "voice": self.voice_online,
            "agent": self.agent_online
        }

    def cloud_status(self) -> dict[str, Any]:
        if not self.cloud_client.is_configured:
            return {
                "configured": False,
                "online": False,
                "mode": "local",
            }
        try:
            health = self.cloud_client.health()
        except CloudPlannerError:
            return {
                "configured": True,
                "online": False,
                "mode": "local",
            }
        online = health.get("status") == "ok"
        return {
            "configured": True,
            "online": online,
            "mode": "azure" if online else "local",
        }

    @staticmethod
    def _availability(online: bool) -> str:
        return "działa" if online else "niedostępny"

    def summary(self) -> str:
        cloud = self.cloud_status()
        planner = (
            "Azure — połączony"
            if cloud["online"]
            else "lokalny — bezpieczny fallback"
        )
        return "\n".join(
            [
                "JARVIS OS — status",
                f"• Rdzeń: {self._availability(self.brain_online)}",
                f"• Pamięć: {self._availability(self.memory_online)}",
                f"• Analiza obrazu: {self._availability(self.vision_online)}",
                f"• Głos: {self._availability(self.voice_online)}",
                f"• Agent lokalny: {self._availability(self.agent_online)}",
                f"• Planer: {planner}",
                "• Tryb awaryjny: gotowy",
            ]
        )
