from __future__ import annotations

from typing import Any

from app.autodev.autonomous_loop import (
    AutonomousLoop,
    AutonomousLoopPolicy,
)


class AutonomousManager:

    def __init__(
        self,
        loop: AutonomousLoop | None = None,
    ) -> None:
        self.loop = loop or AutonomousLoop()
        self.last_result: dict[str, Any] | None = None

    def start(
        self,
        *,
        max_cycles: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.last_result = self.loop.run(
            max_cycles=max_cycles,
            context=context,
        )
        return dict(self.last_result)

    def stop(self) -> dict[str, Any]:
        self.loop.request_stop()
        return {
            "success": True,
            "status": "STOP_REQUESTED",
        }

    def status(self) -> dict[str, Any]:
        return {
            "loop": self.loop.status(),
            "last_result": self.last_result,
        }

    def configure(
        self,
        *,
        max_cycles: int,
        stop_on_failure: bool = True,
        stop_when_code_required: bool = True,
    ) -> dict[str, Any]:
        policy = AutonomousLoopPolicy(
            max_cycles=max_cycles,
            stop_on_failure=stop_on_failure,
            stop_when_code_required=stop_when_code_required,
        )
        policy.validate()
        self.loop.policy = policy

        return {
            "success": True,
            "status": "CONFIGURED",
            "policy": {
                "max_cycles": policy.max_cycles,
                "stop_on_failure": policy.stop_on_failure,
                "stop_when_code_required": (
                    policy.stop_when_code_required
                ),
            },
        }
