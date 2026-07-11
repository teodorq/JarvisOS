from __future__ import annotations

from typing import Any

from app.autodev.autonomous_policy import BackgroundAutonomyPolicy
from app.autodev.autonomous_service import AutonomousService
from app.autodev.autonomous_triggers import AutonomousTriggers
from app.autodev.background_events import BackgroundEventLog


class BackgroundWorker:

    def __init__(
        self,
        *,
        service: AutonomousService | None = None,
        policy: BackgroundAutonomyPolicy | None = None,
        triggers: AutonomousTriggers | None = None,
        events: BackgroundEventLog | None = None,
    ) -> None:
        self.service = service or AutonomousService()
        self.policy = policy or BackgroundAutonomyPolicy()
        self.policy.validate()

        self.triggers = triggers or AutonomousTriggers(
            policy=self.policy
        )
        self.events = events or BackgroundEventLog()

        self.enabled = False
        self.last_evaluation: dict[str, Any] | None = None

    def enable(self) -> dict[str, Any]:
        self.enabled = True
        self.events.add(
            "ENABLED",
            "Background AutoDev został włączony.",
        )
        return {
            "success": True,
            "status": "ENABLED",
        }

    def disable(self) -> dict[str, Any]:
        self.enabled = False
        stop_result = self.service.stop()
        self.events.add(
            "DISABLED",
            "Background AutoDev został wyłączony.",
        )
        return {
            "success": True,
            "status": "DISABLED",
            "stop": stop_result,
        }

    def tick(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "success": True,
                "status": "DISABLED",
            }

        if self.service.is_running():
            return {
                "success": True,
                "status": "ALREADY_RUNNING",
            }

        evaluation = self.triggers.evaluate()
        self.last_evaluation = dict(evaluation)

        if not evaluation["allowed"]:
            self.events.add(
                "SKIPPED",
                "Warunki uruchomienia AutoDev nie zostały spełnione.",
                evaluation,
            )
            return {
                "success": True,
                "status": "SKIPPED",
                "evaluation": evaluation,
            }

        result = self.service.start(
            max_cycles=self.policy.max_cycles_per_run,
            context={
                "background": True,
                "safe_execution": True,
                "auto_rollback": True,
                **dict(context or {}),
            },
            background=self.policy.background_enabled,
        )

        self.events.add(
            "START_ATTEMPT",
            "Podjęto próbę uruchomienia AutoDev w tle.",
            result,
        )

        return result

    def on_user_activity(self) -> dict[str, Any]:
        if (
            self.policy.stop_on_user_activity
            and self.service.is_running()
        ):
            result = self.service.stop()
            self.events.add(
                "STOP_USER_ACTIVITY",
                "AutoDev zatrzymany po wykryciu aktywności użytkownika.",
                result,
            )
            return result

        return {
            "success": True,
            "status": "NO_ACTION",
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "ENABLED" if self.enabled else "DISABLED",
            "enabled": self.enabled,
            "policy": self.policy.to_dict(),
            "service": self.service.status(),
            "last_evaluation": self.last_evaluation,
            "events": self.events.summary(),
        }
