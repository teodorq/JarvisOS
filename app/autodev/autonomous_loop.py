from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.autodev.autodev_runtime import AutoDevRuntime
from app.autodev.autonomous_monitor import AutonomousMonitor
from app.autodev.autonomous_statistics import AutonomousStatistics
from app.autodev.learning_engine import LearningEngine


@dataclass(slots=True)
class AutonomousLoopPolicy:
    max_cycles: int = 5
    stop_on_failure: bool = True
    stop_when_code_required: bool = True

    def validate(self) -> None:
        if self.max_cycles < 1:
            raise ValueError(
                "max_cycles musi być większe od 0."
            )


class AutonomousLoop:

    def __init__(
        self,
        *,
        runtime: AutoDevRuntime | None = None,
        learning_engine: LearningEngine | None = None,
        monitor: AutonomousMonitor | None = None,
        statistics: AutonomousStatistics | None = None,
        policy: AutonomousLoopPolicy | None = None,
    ) -> None:
        self.runtime = runtime or AutoDevRuntime()
        self.learning_engine = learning_engine or LearningEngine()
        self.monitor = monitor or AutonomousMonitor()
        self.statistics = statistics or AutonomousStatistics()
        self.policy = policy or AutonomousLoopPolicy()
        self.policy.validate()

        self.running = False
        self.stop_requested = False
        self.history: list[dict[str, Any]] = []

    def request_stop(self) -> None:
        self.stop_requested = True
        request_stop = getattr(self.runtime, "request_stop", None)
        if callable(request_stop):
            request_stop()

    def run(
        self,
        *,
        context: dict[str, Any] | None = None,
        max_cycles: int | None = None,
    ) -> dict[str, Any]:
        limit = self.policy.max_cycles if max_cycles is None else int(max_cycles)

        if limit < 1:
            raise ValueError(
                "max_cycles musi być większe od 0."
            )

        self.running = True
        self.stop_requested = False
        cycle_results: list[dict[str, Any]] = []
        stop_reason = "MAX_CYCLES_REACHED"

        try:
            for _ in range(limit):
                if self.stop_requested:
                    stop_reason = "STOP_REQUESTED"
                    break

                result = self.runtime.run_once(context=context)
                learning = self.learning_engine.learn_from_result(result)
                health = self.monitor.inspect(result)
                stats = self.statistics.update(result)

                combined = {
                    "result": result,
                    "learning": learning,
                    "health": health,
                    "statistics": stats,
                }

                cycle_results.append(combined)
                self.history.append(combined)

                status = str(result.get("status", "UNKNOWN"))

                if status == "NO_TASKS":
                    stop_reason = "NO_TASKS"
                    break

                if (
                    status == "CODE_INPUT_REQUIRED"
                    and self.policy.stop_when_code_required
                ):
                    stop_reason = "CODE_INPUT_REQUIRED"
                    break

                if (
                    not result.get("success", False)
                    and self.policy.stop_on_failure
                ):
                    stop_reason = "FAILURE"
                    break

        finally:
            self.running = False

        return {
            "success": stop_reason not in {"FAILURE"},
            "status": "STOPPED",
            "stop_reason": stop_reason,
            "cycles_run": len(cycle_results),
            "cycles": cycle_results,
            "statistics": self.statistics.summary(),
            "learning": self.learning_engine.summary(),
        }

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "stop_requested": self.stop_requested,
            "history_count": len(self.history),
            "statistics": self.statistics.summary(),
            "learning": self.learning_engine.summary(),
        }
