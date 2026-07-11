from __future__ import annotations

from typing import Any

from app.autodev.autonomous_manager import AutonomousManager
from app.autodev.lifecycle_state import (
    LifecycleState,
    LifecycleStateStore,
)
from app.autodev.task_recovery import TaskRecovery
from app.autodev.work_selector import WorkSelector


class AutonomousLifecycle:

    def __init__(
        self,
        *,
        controller: Any,
        manager: AutonomousManager | None = None,
        state_store: LifecycleStateStore | None = None,
        selector: WorkSelector | None = None,
        recovery: TaskRecovery | None = None,
    ) -> None:
        self.controller = controller
        self.manager = manager or AutonomousManager()
        self.state_store = (
            state_store or LifecycleStateStore()
        )
        self.selector = selector or WorkSelector()
        self.recovery = recovery or TaskRecovery()
        self.state = self.state_store.load()

    def startup(self) -> dict[str, Any]:
        recovery_result = self.recovery.recover(
            self.controller
        )

        self.state.running = False
        self.state.last_status = "READY"
        self.state.recovery_count += len(
            recovery_result.get(
                "recovered",
                [],
            )
        )

        self.state_store.save(
            self.state
        )

        return {
            "success": bool(
                recovery_result.get(
                    "success",
                    True,
                )
            ),
            "status": "READY",
            "recovery": recovery_result,
            "state": self.state.to_dict(),
        }

    def run_next(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tasks = self.controller.list_tasks()
        selected = self.selector.select(tasks)

        if selected is None:
            result = {
                "success": True,
                "status": "NO_TASKS",
                "task": None,
            }
            self._update_state(result)
            return result

        task_id = str(
            selected.get(
                "task_id",
                "",
            )
        )

        self.state.running = True
        self.state.last_task_id = task_id
        self.state.last_status = "RUNNING"
        self.state_store.save(self.state)

        try:
            result = self.manager.start(
                max_cycles=1,
                context={
                    "selected_task_id": task_id,
                    "selected_task": selected,
                    **dict(context or {}),
                },
            )
        except Exception as error:
            result = {
                "success": False,
                "status": "FAILED",
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
                "task": selected,
            }

        self._update_state(
            result,
            task_id=task_id,
        )

        return {
            **dict(result),
            "selected_task": selected,
        }

    def run_until_idle(
        self,
        *,
        max_tasks: int = 10,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if max_tasks < 1:
            raise ValueError(
                "max_tasks musi być większe od 0."
            )

        results: list[dict[str, Any]] = []
        stop_reason = "MAX_TASKS_REACHED"

        for _ in range(max_tasks):
            result = self.run_next(
                context=context
            )
            results.append(result)

            if result.get("status") == "NO_TASKS":
                stop_reason = "NO_TASKS"
                break

            if not result.get("success", False):
                stop_reason = "FAILURE"
                break

        return {
            "success": stop_reason != "FAILURE",
            "status": "STOPPED",
            "stop_reason": stop_reason,
            "tasks_run": len(results),
            "results": results,
            "state": self.state.to_dict(),
        }

    def stop(self) -> dict[str, Any]:
        result = self.manager.stop()
        self.state.running = False
        self.state.last_status = "STOP_REQUESTED"
        self.state_store.save(self.state)

        return {
            **dict(result),
            "state": self.state.to_dict(),
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": self.state.last_status,
            "state": self.state.to_dict(),
            "manager": self.manager.status(),
        }

    def _update_state(
        self,
        result: dict[str, Any],
        task_id: str = "",
    ) -> None:
        self.state.running = False
        self.state.last_task_id = task_id
        self.state.last_status = str(
            result.get(
                "status",
                "UNKNOWN",
            )
        )
        self.state.cycles_completed += 1
        self.state_store.save(self.state)
