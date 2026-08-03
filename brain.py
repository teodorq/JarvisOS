"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from typing import Any

from app.agent.loop import AgentLoop
from app.agent.task_planner import TaskPlanner
from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.brain_command_router import BrainCommandRouter
from app.ai.architecture.architect_controller import (
    ArchitectController,
)
from app.ai.autodev_router import AutoDevRouter
from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
)
from app.ai.cognitive_engine import CognitiveEngine
from app.ai.continuous_dev.continuous_dev_controller import (
    ContinuousDevController,
)
from app.ai.evolution.evolution_controller import (
    EvolutionController,
)
from app.ai.executive_ai.executive_controller import (
    ExecutiveController,
)
from app.ai.meta_executive.meta_controller import (
    MetaController,
)
from app.ai.planner_llm import PlannerLLM
from app.ai.project_director.director_controller import (
    DirectorController,
)
from app.ai.reasoner.reasoning_controller import (
    ReasoningController,
)
from app.ai.reasoning_service import ReasoningService
from app.ai.self_improvement.improvement_controller import (
    ImprovementController,
)
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.autodev.autodev_pipeline import (
    AutoDevPipeline,
    AutoDevPipelinePolicy,
)
from app.autodev.research_service import ResearchService
from app.automation.command_executor import CommandExecutor
from app.memory.memory import Memory
from app.core.project_paths import resolve_project_root


_BRAIN_RESPONSE_FORMATTER = BrainResponseFormatter()
_BRAIN_COMMAND_ROUTER = BrainCommandRouter()


class AutoDevReasonerAdapter:

    def __init__(
        self,
        autodev_router: AutoDevRouter,
    ) -> None:
        self.autodev_router = autodev_router

    def execute(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(payload, dict):
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "AutoDevReasonerAdapter wymaga "
                    "payload typu dict."
                ),
            }

        goal = payload.get(
            "goal",
            {},
        )

        strategy = payload.get(
            "strategy",
            {},
        )

        command = ""

        if isinstance(goal, dict):
            command = str(
                goal.get(
                    "original_request",
                    goal.get(
                        "goal",
                        "",
                    ),
                )
            ).strip()

        if not command and isinstance(
            strategy,
            dict,
        ):
            selected_option = strategy.get(
                "selected_option",
                {},
            )

            if isinstance(
                selected_option,
                dict,
            ):
                command = str(
                    selected_option.get(
                        "description",
                        selected_option.get(
                            "name",
                            "",
                        ),
                    )
                ).strip()

        if not command:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "Nie udało się zbudować polecenia "
                    "dla AutoDevRouter."
                ),
            }

        result = self.autodev_router.handle(
            command
        )

        if isinstance(result, dict):
            return result

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }


class Brain:

    @property
    def project_root(
        self,
    ) -> str:
        stored = getattr(
            self,
            "_project_root",
            None,
        )

        if stored:
            return str(stored).replace(
                "\\",
                "/",
            )

        resolved = str(
            resolve_project_root()
        ).replace(
            "\\",
            "/",
        )
        self._project_root = resolved

        return resolved

    @project_root.setter
    def project_root(
        self,
        value: str | None,
    ) -> None:
        self._project_root = str(
            resolve_project_root(
                value
            )
        ).replace(
            "\\",
            "/",
        )

    def __init__(
        self,
        project_root: str | None = None,
    ) -> None:

        self.project_root = str(
            resolve_project_root(
                project_root
            )
        )

        self.planner = PlannerLLM()

        self.executor = CommandExecutor()

        self.memory = Memory()

        self.task_planner = TaskPlanner()

        self.agent_loop = AgentLoop()

        self.cognitive = CognitiveEngine()

        self.research_service = ResearchService(
            project_root=self.project_root
        )

        self.autodev_router = AutoDevRouter(
            project_root=self.project_root
        )

        self.autodev_pipeline = AutoDevPipeline(
            policy=AutoDevPipelinePolicy(
                project_root=self.project_root,
                auto_approve=False,
                auto_execute=True,
                auto_rollback=True,
                worker_count=1,
                max_parallel_tasks=1,
            )
        )

        self.autonomous_dev_controller = (
            self._build_autonomous_dev_controller()
        )

        self.background_autodev_start_result = (
            self.autonomous_dev_controller
            .start_background(
                context={
                    "project_root": self.project_root,
                    "auto_approve": True,
                    "auto_execute": True,
                    "stop_on_failure": False,
                    "metadata": {
                        "source": "BrainAutostart",
                        "safe_execution": True,
                        "auto_rollback": True,
                    },
                },
                interval_seconds=2.0,
            )
        )

        self.autodev_reasoner_adapter = (
            AutoDevReasonerAdapter(
                autodev_router=self.autodev_router
            )
        )

        self.reasoning_controller = (
            ReasoningController(
                research_service=(
                    self.research_service
                ),
                developer_controller=(
                    self.autodev_reasoner_adapter
                ),
            )
        )

        self.reasoning_service = ReasoningService(
            controller=self.reasoning_controller
        )

        self.continuous_dev_controller = (
            ContinuousDevController(
                project_root=self.project_root,
                research_service=(
                    self.research_service
                ),
                reasoning_service=(
                    self.reasoning_service
                ),
                developer_controller=(
                    self.autodev_reasoner_adapter
                ),
            )
        )

        self.evolution_controller = (
            EvolutionController(
                project_root=self.project_root
            )
        )

        self.improvement_controller = (
            ImprovementController(
                project_root=self.project_root,
                research_service=(
                    self.research_service
                ),
                reasoning_service=(
                    self.reasoning_service
                ),
                evolution_controller=(
                    self.evolution_controller
                ),
                continuous_dev_controller=(
                    self.continuous_dev_controller
                ),
            )
        )

        self.director_controller = (
            DirectorController(
                project_root=self.project_root,
                research_service=(
                    self.research_service
                ),
                reasoning_service=(
                    self.reasoning_service
                ),
                improvement_controller=(
                    self.improvement_controller
                ),
                evolution_controller=(
                    self.evolution_controller
                ),
                continuous_dev_controller=(
                    self.continuous_dev_controller
                ),
            )
        )

        autodev_queue = getattr(
            self.autodev_pipeline,
            "queue",
            None,
        )

        if autodev_queue is None:
            pipeline = getattr(
                self.autonomous_dev_controller,
                "pipeline",
                None,
            )
            autodev_queue = getattr(
                pipeline,
                "queue",
                None,
            )

        self.architect_controller = (
            ArchitectController(
                project_root=self.project_root,
                evolution_controller=(
                    self.evolution_controller
                ),
                director_controller=(
                    self.director_controller
                ),
                task_queue=autodev_queue,
            )
        )

        self.software_engineer_controller = (
            AutonomousSoftwareEngineerController(
                project_root=self.project_root,
                task_queue=autodev_queue,
            )
        )

        self.executive_controller = (
            ExecutiveController(
                project_root=self.project_root,
                project_director=(
                    self.director_controller
                ),
                reasoning_service=(
                    self.reasoning_service
                ),
                research_service=(
                    self.research_service
                ),
                improvement_controller=(
                    self.improvement_controller
                ),
                evolution_controller=(
                    self.evolution_controller
                ),
                continuous_dev_controller=(
                    self.continuous_dev_controller
                ),
            )
        )

        self.meta_controller = (
            MetaController(
                project_root=self.project_root,
                executive_controller=(
                    self.executive_controller
                ),
                project_director=(
                    self.director_controller
                ),
                improvement_controller=(
                    self.improvement_controller
                ),
                evolution_controller=(
                    self.evolution_controller
                ),
                continuous_dev_controller=(
                    self.continuous_dev_controller
                ),
                reasoning_service=(
                    self.reasoning_service
                ),
                research_service=(
                    self.research_service
                ),
            )
        )

    def think(
        self,
        command: str,
    ) -> dict:
        return _BRAIN_COMMAND_ROUTER.think(
            self,
            command,
        )


    def execute(
        self,
        thought: dict,
    ):
        return _BRAIN_COMMAND_ROUTER.execute(
            self,
            thought,
        )


    def _build_autonomous_dev_controller(
        self,
    ) -> AutonomousDevController:

        constructors = (
            {
                "project_root": self.project_root,
                "pipeline": self.autodev_pipeline,
            },
            {
                "pipeline": self.autodev_pipeline,
            },
            {
                "project_root": self.project_root,
            },
            {},
        )

        last_error: TypeError | None = None

        for kwargs in constructors:
            try:
                controller = AutonomousDevController(
                    **kwargs
                )

                if not hasattr(
                    controller,
                    "pipeline",
                ):
                    try:
                        setattr(
                            controller,
                            "pipeline",
                            self.autodev_pipeline,
                        )
                    except Exception:
                        raise RuntimeError("AutoDev: przechwycony wyjątek")

                return controller

            except TypeError as error:
                last_error = error

        if last_error is not None:
            raise last_error

        raise RuntimeError(
            "Nie udało się utworzyć "
            "AutonomousDevController."
        )

    def _execute_autonomous_dev(
        self,
        command: str,
    ) -> dict[str, Any]:

        controller = getattr(
            self,
            "autonomous_dev_controller",
            None,
        )

        if controller is None:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "AutonomousDevController "
                    "nie jest dostępny."
                ),
            }

        context = {
            "project_root": self.project_root,
            "metadata": {
                "source": "Brain",
                "autonomous": True,
                "safe_execution": True,
                "auto_rollback": True,
            },
        }

        handle_method = getattr(
            controller,
            "handle",
            None,
        )

        if callable(handle_method):
            try:
                response = handle_method(
                    command=command,
                    context=context,
                )
            except TypeError:
                try:
                    response = handle_method(
                        command,
                        context,
                    )
                except TypeError:
                    response = handle_method(
                        command
                    )

            return self._normalize_autonomous_response(
                response
            )

        execute_method = getattr(
            controller,
            "execute",
            None,
        )

        if callable(execute_method):
            try:
                response = execute_method(
                    command=command,
                    context=context,
                )
            except TypeError:
                try:
                    response = execute_method(
                        {
                            "command": command,
                            "goal": command,
                            "context": context,
                        }
                    )
                except TypeError:
                    response = execute_method(
                        command
                    )

            return self._normalize_autonomous_response(
                response
            )

        return {
            "success": False,
            "status": "FAILED",
            "error": (
                "AutonomousDevController nie posiada "
                "metody handle ani execute."
            ),
        }

    def _normalize_autonomous_response(
        self,
        response: Any,
    ) -> dict[str, Any]:

        if isinstance(
            response,
            dict,
        ):
            return response

        to_dict_method = getattr(
            response,
            "to_dict",
            None,
        )

        if callable(to_dict_method):
            normalized = to_dict_method()

            if isinstance(
                normalized,
                dict,
            ):
                return normalized

        return {
            "success": True,
            "status": "COMPLETED",
            "result": response,
        }

    def _response_formatter(
        self,
    ) -> BrainResponseFormatter:
        return _BRAIN_RESPONSE_FORMATTER

    def _format_software_engineer_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_software_engineer_response(
            response
        )

    def _format_architect_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_architect_response(
            response
        )

    def _format_autonomous_dev_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_autonomous_dev_response(
            response
        )

    def _format_autonomous_status(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_autonomous_status(
            response
        )

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:
        return _BRAIN_RESPONSE_FORMATTER._safe_int(
            value
        )

    @staticmethod
    def _format_duration(
        total_seconds: int,
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_duration(
            total_seconds
        )

    def _format_meta_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_meta_response(
            response
        )

    def _format_executive_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_executive_response(
            response
        )

    def _format_project_director_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_project_director_response(
            response
        )

    def _format_improvement_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_improvement_response(
            response
        )

    def _format_evolution_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_evolution_response(
            response
        )

    def _format_continuous_dev_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_continuous_dev_response(
            response
        )

    def _format_reasoning_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_reasoning_response(
            response
        )

    def _format_research_response(
        self,
        response: dict[str, Any],
    ) -> str:
        return _BRAIN_RESPONSE_FORMATTER._format_research_response(
            response
        )


    def _remember_execution(
        self,
        command: str,
        result,
    ) -> None:

        result_text = str(
            result
        )

        self.memory.add_history(
            command,
            result_text,
        )

        self.cognitive.after_execute(
            command,
            result_text,
        )
    def background_status(
        self,
    ) -> dict[str, Any]:

        controller = getattr(
            self,
            "autonomous_dev_controller",
            None,
        )

        if controller is None:
            return {
                "success": False,
                "running": False,
                "status": "OFFLINE",
            }

        try:
            raw_result: Any = None

            background_method = getattr(
                controller,
                "background_status",
                None,
            )

            if callable(
                background_method
            ):
                raw_result = background_method()

            result = (
                dict(raw_result)
                if isinstance(
                    raw_result,
                    dict,
                )
                else {}
            )

            if not result:
                status_method = getattr(
                    controller,
                    "status",
                    None,
                )

                if callable(
                    status_method
                ):
                    raw_status = status_method()

                    if isinstance(
                        raw_status,
                        dict,
                    ):
                        result = dict(
                            raw_status
                        )

            running = bool(
                result.get(
                    "running",
                    result.get(
                        "background_running",
                        result.get(
                            "timed_loop_running",
                            False,
                        ),
                    ),
                )
            )

            status = str(
                result.get(
                    "status",
                    (
                        "RUNNING"
                        if running
                        else "READY"
                    ),
                )
            )

            return {
                **result,
                "success": bool(
                    result.get(
                        "success",
                        True,
                    )
                ),
                "running": running,
                "status": status,
            }

        except Exception as error:
            return {
                "success": False,
                "running": False,
                "status": "ERROR",
                "error": (
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
            }

    def shutdown(
        self,
    ) -> None:

        controller = getattr(
            self,
            "autonomous_dev_controller",
            None,
        )

        if controller is not None:
            try:
                stop_background = getattr(
                    controller,
                    "stop_background",
                    None,
                )

                if callable(
                    stop_background
                ):
                    stop_background(
                        wait=True,
                        timeout=5.0,
                    )
            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")

            try:
                stop_timed = getattr(
                    controller,
                    "stop_timed_autonomous_loop",
                    None,
                )

                if callable(
                    stop_timed
                ):
                    stop_timed()
            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")

        pipeline = getattr(
            self,
            "autodev_pipeline",
            None,
        )

        if pipeline is not None:
            try:
                pipeline.stop(
                    wait=False
                )
            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")
