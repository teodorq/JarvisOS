from __future__ import annotations

from typing import Any

from .execution_recovery import (
    ExecutionRecoveryOrchestrator,
    ExecutionRecoveryPolicy,
)
from .implementation_graph import ImplementationGraph
from .software_engineer_advanced_change_router import (
    SoftwareEngineerAdvancedChangeRouter,
)

_ADVANCED_CHANGE_ROUTER = SoftwareEngineerAdvancedChangeRouter()


class SoftwareEngineerCommandRouter:
    """Bezstanowy router poleceń Autonomous Software Engineer."""

    def handle(
        self,
        controller: Any,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = dict(
            context or {}
        )
        operation = str(
            context.get(
                "operation",
                context.get("mode", ""),
            )
        ).strip().casefold()
        full_autonomy_requested = (
            context.get("full_autonomy") is True
            or operation in {
                "full_autonomy",
                "large_goal_autonomy",
                "end_to_end_autonomy",
                "autonomous_goal",
            }
        )
        long_running_requested = (
            context.get("long_running_autonomy") is True
            or operation in {
                "long_running_autonomy",
                "autonomy_supervisor",
                "scheduled_autonomy",
                "persistent_autonomy",
            }
        )

        if (
            not controller.can_handle(command)
            and not full_autonomy_requested
            and not long_running_requested
        ):
            return {
                "success": False,
                "status": "UNSUPPORTED_COMMAND",
                "errors": [
                    "Polecenie nie uruchamia "
                    "Autonomous Software Engineer."
                ],
            }

        objective = str(
            context.get(
                "objective",
                controller._extract_objective(
                    command
                ),
            )
        ).strip()

        if not objective:
            objective = (
                "Zaimplementuj bezpieczne ulepszenie "
                "w projekcie JARVIS OS."
            )

        advanced = _ADVANCED_CHANGE_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )

        if advanced is not None:
            return advanced

        if controller._is_multi_file_request(
            command,
            context,
        ):
            return self._handle_multi_file(
                controller,
                objective=objective,
                context=context,
            )

        return self._handle_single_file(
            controller,
            command=command,
            objective=objective,
            context=context,
        )

    def _handle_multi_file(
        self,
        controller: Any,
        *,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        replacements = context.get(
            "replacements"
        )

        if not isinstance(
            replacements,
            dict,
        ):
            replacements = None

        return controller.multi_file_workflow.run(
            objective,
            feature_name=(
                str(
                    context.get(
                        "feature_name",
                        "",
                    )
                ).strip()
                or None
            ),
            package_path=(
                str(
                    context.get(
                        "package_path",
                        "",
                    )
                ).strip()
                or None
            ),
            include_controller=bool(
                context.get(
                    "include_controller",
                    True,
                )
            ),
            include_repository=bool(
                context.get(
                    "include_repository",
                    False,
                )
            ),
            auto_execute=bool(
                context.get(
                    "auto_execute",
                    True,
                )
            ),
            auto_approve=bool(
                context.get(
                    "auto_approve",
                    False,
                )
            ),
            auto_rollback=bool(
                context.get(
                    "auto_rollback",
                    True,
                )
            ),
            replacements=replacements,
            allow_existing=bool(
                context.get(
                    "allow_existing",
                    False,
                )
            ),
        )


    def _handle_single_file(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        plan = (
            controller.decomposition_controller
            .engine
            .decompose(
                objective
            )
        )
        graph = ImplementationGraph.build(
            plan
        )
        target_path = str(
            context.get(
                "target_path",
                context.get(
                    "path",
                    controller._extract_target_path(
                        command
                    ),
                ),
            )
            or ""
        ).strip().replace(
            "\\",
            "/",
        )
        auto_execute = bool(
            context.get(
                "auto_execute",
                bool(target_path),
            )
        )
        can_execute = bool(
            auto_execute
            and target_path
        )
        enqueue_plan = bool(
            context.get(
                "enqueue_plan",
                not can_execute,
            )
        )
        queue_result = (
            controller.decomposition_controller
            .enqueue_plan(
                plan
            )
            if enqueue_plan
            else {
                "success": True,
                "status": "SKIPPED",
                "created": 0,
                "duplicates": 0,
            }
        )
        scheduling = controller._schedule_code_task(
            plan=plan,
            target_path=target_path,
            proposed_content=str(
                context.get(
                    "proposed_content",
                    "",
                )
                or ""
            ),
        )
        base_result: dict[str, Any] = {
            "success": True,
            "status": (
                "EXECUTION_READY"
                if target_path
                else "PLAN_READY"
            ),
            "objective": objective,
            "target_path": target_path,
            "plan": plan.to_dict(),
            "graph": graph,
            "queue": queue_result,
            "scheduling": scheduling,
            "execution": {},
        }

        if not can_execute:
            return base_result

        scheduled_task = scheduling.get(
            "scheduled_task"
        )

        if not isinstance(
            scheduled_task,
            dict,
        ):
            return {
                **base_result,
                "success": False,
                "status": "SCHEDULING_FAILED",
                "errors": [
                    "Nie udało się przygotować "
                    "zadania implementacyjnego."
                ],
            }

        recovery = ExecutionRecoveryOrchestrator(
            implementation_executor=(
                controller.implementation_executor
            ),
            policy=ExecutionRecoveryPolicy(
                max_attempts=max(
                    1,
                    int(
                        context.get(
                            "max_attempts",
                            3,
                        )
                    ),
                ),
                auto_approve=bool(
                    context.get(
                        "auto_approve",
                        False,
                    )
                ),
                auto_rollback=bool(
                    context.get(
                        "auto_rollback",
                        True,
                    )
                ),
                stop_on_preview=True,
            ),
        )
        execution = recovery.execute_with_recovery(
            scheduled_task
        )
        effective_status = (
            controller._effective_status(
                execution
            )
        )

        return {
            **base_result,
            "success": bool(
                execution.get(
                    "success",
                    False,
                )
                or effective_status
                == "PREVIEW_READY"
            ),
            "status": effective_status,
            "execution": execution,
            "errors": controller._execution_errors(
                execution
            ),
        }
