from __future__ import annotations

from typing import Any

from app.autodev.autonomous_improvement_service import (
    AutonomousImprovementService,
)
from app.autodev.developer_decision_engine import (
    DeveloperDecisionEngine,
)


class BrainAutoDevController:
    """
    Warstwa pośrednia pomiędzy Brain a AutoDev.

    Moduł:
    - rozpoznaje komendy,
    - zwraca status,
    - wykonuje bezpieczny preview,
    - wymaga jawnej akceptacji dla wykonania.
    """

    COMMANDS = (
        "brain autodev status",
        "status brain autodev",
        "brain autodev preview",
        "podgląd brain autodev",
        "podglad brain autodev",
        "brain autodev execute",
        "wykonaj brain autodev",
        "brain autodev decision",
        "decyzja brain autodev",
    )

    def __init__(
        self,
        service: AutonomousImprovementService,
        decision_engine: DeveloperDecisionEngine,
    ) -> None:

        self.service = service
        self.decision_engine = decision_engine
        self.last_result: dict[str, Any] | None = None

    def can_handle(
        self,
        command: str,
    ) -> bool:

        normalized = str(
            command
        ).strip().casefold()

        return any(
            phrase in normalized
            for phrase in self.COMMANDS
        )

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized = str(
            command
        ).strip().casefold()

        context = dict(
            context or {}
        )

        if "status" in normalized:
            result = {
                "success": True,
                "status": "BRAIN_AUTODEV_STATUS",
                "service": self.service.status(),
                "decision_engine": (
                    self.decision_engine.status()
                ),
            }

            return self._finish(
                result
            )

        if "decision" in normalized or "decyzja" in normalized:
            issue_type = str(
                context.get(
                    "issue_type",
                    "UNKNOWN",
                )
            )

            result = self.decision_engine.decide(
                issue_type=issue_type,
                context=context,
            )

            return self._finish(
                {
                    "controller_status": (
                        "BRAIN_AUTODEV_DECISION"
                    ),
                    **result,
                }
            )

        if "execute" in normalized or "wykonaj" in normalized:
            result = (
                self.service.execute_approved()
            )

            return self._finish(
                {
                    "controller_status": (
                        "BRAIN_AUTODEV_EXECUTION"
                    ),
                    **result,
                }
            )

        result = self.service.preview()

        return self._finish(
            {
                "controller_status": (
                    "BRAIN_AUTODEV_PREVIEW"
                ),
                **result,
            }
        )

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        self.last_result = dict(
            result
        )

        return dict(
            result
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": self.last_result,
            "service": self.service.status(),
            "decision_engine": (
                self.decision_engine.status()
            ),
        }
