from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
)


ContextProvider = Callable[
    [dict[str, Any] | None],
    dict[str, Any],
]


@dataclass(slots=True)
class AutoDevRuntimePolicy:

    max_cycles: int = 10
    auto_approve: bool = False
    auto_execute: bool = False
    stop_on_failure: bool = True
    stop_when_code_required: bool = True

    def validate(
        self,
    ) -> None:

        if self.max_cycles < 1:
            raise ValueError(
                "max_cycles musi być większe od 0."
            )


class AutoDevRuntime:
    """
    Bezpieczna, ograniczona pętla AutoDev.

    Runtime nie działa w nieskończoność. Każde uruchomienie
    ma limit cykli i zatrzymuje się, gdy:
    - nie ma kolejnych zadań,
    - potrzebny jest kod wejściowy,
    - pojawi się błąd,
    - osiągnięto limit cykli.
    """

    TERMINAL_STATUSES = {
        "NO_TASKS",
        "CODE_INPUT_REQUIRED",
        "PLANNING_FAILED",
        "request_invalid",
        "prepare_failed",
        "patch_generation_failed",
        "transaction_invalid",
        "execution_blocked",
        "execution_exception",
        "failed",
        "failed_and_rolled_back",
        "rollback_failed",
    }

    def __init__(
        self,
        *,
        controller: AutonomousDevController | None = None,
        policy: AutoDevRuntimePolicy | None = None,
        context_provider: ContextProvider | None = None,
    ) -> None:

        self.controller = (
            controller
            if controller is not None
            else AutonomousDevController()
        )

        self.policy = policy or AutoDevRuntimePolicy()
        self.policy.validate()

        self.context_provider = context_provider

        self.running = False
        self.stop_requested = False
        self.cycles_completed = 0
        self.history: list[dict[str, Any]] = []
        self.last_result: dict[str, Any] | None = None

    def run_once(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        prepared_context = self._resolve_context(
            context
        )

        generation = self.controller.run_generation_cycle(
            context=prepared_context
        )

        result = {
            "success": bool(
                generation.get(
                    "success",
                    False,
                )
            ),
            "status": str(
                generation.get(
                    "status",
                    "UNKNOWN",
                )
            ),
            "generation": generation,
            "execution": None,
        }

        if (
            result["status"] == "waiting_for_approval"
            and self.policy.auto_approve
        ):
            execution = (
                self.controller.approve_generated_change(
                    auto_execute=self.policy.auto_execute
                )
            )

            result["execution"] = execution
            result["success"] = bool(
                execution.get(
                    "success",
                    False,
                )
            )
            result["status"] = str(
                execution.get(
                    "status",
                    result["status"],
                )
            )

        self.cycles_completed += 1
        self.last_result = dict(result)
        self.history.append(
            dict(result)
        )

        return result

    def run(
        self,
        *,
        max_cycles: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        limit = (
            self.policy.max_cycles
            if max_cycles is None
            else int(max_cycles)
        )

        if limit < 1:
            raise ValueError(
                "max_cycles musi być większe od 0."
            )

        self.running = True
        self.stop_requested = False

        run_results: list[
            dict[str, Any]
        ] = []

        stop_reason = "MAX_CYCLES_REACHED"

        try:
            for _ in range(limit):
                if self.stop_requested:
                    stop_reason = "STOP_REQUESTED"
                    break

                result = self.run_once(
                    context=context
                )

                run_results.append(
                    result
                )

                status = str(
                    result.get(
                        "status",
                        "UNKNOWN",
                    )
                )

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
                    not result.get(
                        "success",
                        False,
                    )
                    and self.policy.stop_on_failure
                ):
                    stop_reason = "FAILURE"
                    break

                if status in self.TERMINAL_STATUSES:
                    stop_reason = status
                    break

        finally:
            self.running = False

        return {
            "success": (
                stop_reason
                not in {
                    "FAILURE",
                    "PLANNING_FAILED",
                    "execution_exception",
                    "failed",
                    "failed_and_rolled_back",
                    "rollback_failed",
                }
            ),
            "status": "STOPPED",
            "stop_reason": stop_reason,
            "cycles_run": len(run_results),
            "results": run_results,
            "runtime": self.status(),
        }

    def request_stop(
        self,
    ) -> None:

        self.stop_requested = True

    def reset(
        self,
    ) -> None:

        self.running = False
        self.stop_requested = False
        self.cycles_completed = 0
        self.history.clear()
        self.last_result = None

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "running": self.running,
            "stop_requested": self.stop_requested,
            "cycles_completed": self.cycles_completed,
            "history_count": len(
                self.history
            ),
            "last_result": self.last_result,
            "policy": asdict(
                self.policy
            ),
        }

    def _resolve_context(
        self,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:

        base_context = dict(
            context
            or {}
        )

        if self.context_provider is None:
            return base_context

        provided = self.context_provider(
            self.last_result
        )

        if not isinstance(
            provided,
            dict,
        ):
            raise TypeError(
                "context_provider musi zwracać dict."
            )

        return {
            **base_context,
            **provided,
        }
