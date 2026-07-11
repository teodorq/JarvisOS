from __future__ import annotations

from typing import Any

from app.ai.continuous_dev.continuous_developer import (
    ContinuousDeveloper,
)


class ContinuousDevController:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        continuous_developer: ContinuousDeveloper | None = None,
        research_service: Any | None = None,
        reasoning_service: Any | None = None,
        developer_controller: Any | None = None,
        project_analyzer: Any | None = None,
        autonomous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
        ).strip()

        if not self.project_root:
            raise ValueError(
                "ContinuousDevController wymaga project_root."
            )

        self.autonomous_dev_controller = (
            autonomous_dev_controller
        )

        self.continuous_developer = (
            continuous_developer
            if continuous_developer is not None
            else ContinuousDeveloper(
                project_root=self.project_root,
                research_service=research_service,
                reasoning_service=reasoning_service,
                developer_controller=developer_controller,
                project_analyzer=project_analyzer,
            )
        )

    def create_cycle(
        self,
        objective: str,
        max_iterations: int = 10,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.continuous_developer.create_cycle(
            objective=objective,
            max_iterations=max_iterations,
            metadata=metadata,
        )

    def start_cycle(
        self,
        cycle_id: str,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.continuous_developer.start_cycle(
            cycle_id=cycle_id,
            auto_approve=auto_approve,
            context=context,
        )

    def create_and_start(
        self,
        objective: str,
        max_iterations: int = 10,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        created = self.create_cycle(
            objective=objective,
            max_iterations=max_iterations,
            metadata=metadata,
        )

        if created.get(
            "success"
        ) is not True:
            return created

        cycle_id = str(
            created.get(
                "cycle_id",
                "",
            )
        )

        if not cycle_id:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "ContinuousDevController nie otrzymał cycle_id."
                ),
            }

        result = self.start_cycle(
            cycle_id=cycle_id,
            auto_approve=auto_approve,
            context=context,
        )

        if (
            auto_approve
            and result.get(
                "success",
                False,
            )
        ):
            result = dict(
                result
            )

            result["autodev"] = self._delegate_to_autodev(
                objective=objective,
                context=context,
            )

        return result

    def run_iteration(
        self,
        cycle_id: str,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.continuous_developer.run_iteration(
            cycle_id=cycle_id,
            auto_approve=auto_approve,
            context=context,
        )

        if (
            auto_approve
            and result.get(
                "success",
                False,
            )
        ):
            objective = str(
                result.get(
                    "objective",
                    "",
                )
            ).strip()

            if objective:
                result = dict(
                    result
                )

                result["autodev"] = self._delegate_to_autodev(
                    objective=objective,
                    context=context,
                )

        return result

    def approve_cycle(
        self,
        cycle_id: str,
        approved: bool,
        note: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.continuous_developer.approve_cycle(
            cycle_id=cycle_id,
            approved=approved,
            note=note,
            context=context,
        )

    def pause_cycle(
        self,
        cycle_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        return self.continuous_developer.pause_cycle(
            cycle_id=cycle_id,
            reason=reason,
        )

    def resume_cycle(
        self,
        cycle_id: str,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.continuous_developer.resume_cycle(
            cycle_id=cycle_id,
            auto_approve=auto_approve,
            context=context,
        )

    def cancel_cycle(
        self,
        cycle_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        return self.continuous_developer.cancel_cycle(
            cycle_id=cycle_id,
            reason=reason,
        )

    def get_cycle(
        self,
        cycle_id: str,
    ) -> dict[str, Any] | None:

        return self.continuous_developer.get_cycle(
            cycle_id=cycle_id
        )

    def list_cycles(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        return self.continuous_developer.list_cycles(
            limit=limit
        )

    def system_summary(
        self,
    ) -> dict[str, Any]:

        summary = self.continuous_developer.system_summary()

        if not isinstance(
            summary,
            dict,
        ):
            return {
                "summary": summary,
                "autodev_connected": (
                    self.autonomous_dev_controller
                    is not None
                ),
            }

        result = dict(
            summary
        )

        result["autodev_connected"] = (
            self.autonomous_dev_controller
            is not None
        )

        return result

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_command = str(
            command
        ).strip()

        if not normalized_command:
            return {
                "success": False,
                "status": "EMPTY_COMMAND",
                "error": (
                    "Polecenie Continuous Developer jest puste."
                ),
            }

        lowered = normalized_command.lower()

        if lowered.startswith(
            "continuous dev autonomous "
        ):
            objective = normalized_command[
                len("continuous dev autonomous "):
            ].strip()

            return self.create_and_start(
                objective=objective,
                auto_approve=True,
                context=context,
                metadata={
                    "source": "ContinuousDevController",
                    "autonomous": True,
                },
            )

        if lowered.startswith(
            "continuous dev autodev "
        ):
            objective = normalized_command[
                len("continuous dev autodev "):
            ].strip()

            return self._delegate_to_autodev(
                objective=objective,
                context=context,
            )

        if lowered.startswith(
            "continuous dev start "
        ):
            objective = normalized_command[
                len("continuous dev start "):
            ].strip()

            return self.create_and_start(
                objective=objective,
                context=context,
            )

        if lowered.startswith(
            "continuous dev create "
        ):
            objective = normalized_command[
                len("continuous dev create "):
            ].strip()

            return self.create_cycle(
                objective=objective
            )

        if lowered.startswith(
            "continuous dev status "
        ):
            cycle_id = normalized_command[
                len("continuous dev status "):
            ].strip()

            cycle = self.get_cycle(
                cycle_id
            )

            if cycle is None:
                return {
                    "success": False,
                    "status": "NOT_FOUND",
                    "cycle_id": cycle_id,
                }

            return {
                "success": True,
                "status": "FOUND",
                "cycle_id": cycle_id,
                "cycle": cycle,
            }

        if lowered.startswith(
            "continuous dev approve "
        ):
            cycle_id = normalized_command[
                len("continuous dev approve "):
            ].strip()

            return self.approve_cycle(
                cycle_id=cycle_id,
                approved=True,
                context=context,
            )

        if lowered.startswith(
            "continuous dev reject "
        ):
            cycle_id = normalized_command[
                len("continuous dev reject "):
            ].strip()

            return self.approve_cycle(
                cycle_id=cycle_id,
                approved=False,
                note="Odrzucono z polecenia użytkownika.",
                context=context,
            )

        if lowered.startswith(
            "continuous dev pause "
        ):
            cycle_id = normalized_command[
                len("continuous dev pause "):
            ].strip()

            return self.pause_cycle(
                cycle_id=cycle_id
            )

        if lowered.startswith(
            "continuous dev resume "
        ):
            cycle_id = normalized_command[
                len("continuous dev resume "):
            ].strip()

            return self.resume_cycle(
                cycle_id=cycle_id,
                context=context,
            )

        if lowered.startswith(
            "continuous dev cancel "
        ):
            cycle_id = normalized_command[
                len("continuous dev cancel "):
            ].strip()

            return self.cancel_cycle(
                cycle_id=cycle_id
            )

        if lowered in {
            "continuous dev list",
            "continuous dev cycles",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "cycles": self.list_cycles(),
            }

        if lowered in {
            "continuous dev summary",
            "continuous dev system",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "summary": self.system_summary(),
            }

        return {
            "success": False,
            "status": "UNKNOWN_COMMAND",
            "command": normalized_command,
            "error": (
                "Nie rozpoznano polecenia Continuous Developer."
            ),
        }

    def can_handle(
        self,
        command: str,
    ) -> bool:

        normalized = str(
            command
        ).strip().lower()

        prefixes = (
            "continuous dev ",
            "continuous developer ",
            "ciągły rozwój ",
            "ciagly rozwoj ",
            "sam rozwijaj ",
            "rozwijaj projekt ciągle ",
            "rozwijaj projekt ciagle ",
        )

        return normalized.startswith(
            prefixes
        )

    def _delegate_to_autodev(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_objective = str(
            objective
        ).strip()

        if not normalized_objective:
            return {
                "success": False,
                "status": "EMPTY_OBJECTIVE",
                "error": (
                    "Continuous Developer nie otrzymał "
                    "celu dla AutoDev."
                ),
            }

        controller = self.autonomous_dev_controller

        if controller is None:
            return {
                "success": False,
                "status": "AUTODEV_UNAVAILABLE",
                "error": (
                    "AutonomousDevController "
                    "nie został podłączony."
                ),
            }

        normalized_context = self._safe_dict(
            context
        )

        metadata = self._safe_dict(
            normalized_context.get(
                "metadata"
            )
        )

        metadata.update(
            {
                "source": "ContinuousDevController",
                "autonomous": True,
                "safe_execution": True,
                "auto_rollback": True,
            }
        )

        normalized_context[
            "project_root"
        ] = self.project_root

        normalized_context[
            "metadata"
        ] = metadata

        handle_method = getattr(
            controller,
            "handle",
            None,
        )

        if callable(handle_method):
            try:
                result = handle_method(
                    command=normalized_objective,
                    context=normalized_context,
                )
            except TypeError:
                try:
                    result = handle_method(
                        normalized_objective,
                        normalized_context,
                    )
                except TypeError:
                    result = handle_method(
                        normalized_objective
                    )

            return self._normalize_autodev_result(
                result
            )

        execute_method = getattr(
            controller,
            "execute",
            None,
        )

        if callable(execute_method):
            payload = {
                "command": normalized_objective,
                "goal": normalized_objective,
                "context": normalized_context,
            }

            try:
                result = execute_method(
                    payload
                )
            except TypeError:
                result = execute_method(
                    normalized_objective
                )

            return self._normalize_autodev_result(
                result
            )

        return {
            "success": False,
            "status": "AUTODEV_INVALID",
            "error": (
                "AutonomousDevController nie posiada "
                "metody handle ani execute."
            ),
        }

    def _normalize_autodev_result(
        self,
        result: Any,
    ) -> dict[str, Any]:

        if isinstance(
            result,
            dict,
        ):
            return dict(
                result
            )

        to_dict = getattr(
            result,
            "to_dict",
            None,
        )

        if callable(
            to_dict
        ):
            normalized = to_dict()

            if isinstance(
                normalized,
                dict,
            ):
                return normalized

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(
                value
            )

        return {}
