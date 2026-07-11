import time
from typing import Any

from app.agent.loop import AgentLoop
from app.agent.task_planner import TaskPlanner
from app.ai.actions import ActionTypes
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
from app.autodev.autodev_pipeline import (
    AutoDevPipeline,
    AutoDevPipelinePolicy,
)
from app.autodev.research_service import ResearchService
from app.automation.command_executor import CommandExecutor
from app.memory.memory import Memory


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

    def __init__(
        self,
    ) -> None:

        self.planner = PlannerLLM()

        self.executor = CommandExecutor()

        self.memory = Memory()

        self.task_planner = TaskPlanner()

        self.agent_loop = AgentLoop()

        self.cognitive = CognitiveEngine()

        self.research_service = ResearchService(
            project_root="C:/JarvisAI"
        )

        self.autodev_router = AutoDevRouter(
            project_root="C:/JarvisAI"
        )

        self.autodev_pipeline = AutoDevPipeline(
            policy=AutoDevPipelinePolicy(
                project_root="C:/JarvisAI",
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
                project_root="C:/JarvisAI",
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
                project_root="C:/JarvisAI"
            )
        )

        self.improvement_controller = (
            ImprovementController(
                project_root="C:/JarvisAI",
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
                project_root="C:/JarvisAI",
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

        self.executive_controller = (
            ExecutiveController(
                project_root="C:/JarvisAI",
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
                project_root="C:/JarvisAI",
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

        self.cognitive.before_think(
            command
        )

        autonomous_controller = getattr(
            self,
            "autonomous_dev_controller",
            None,
        )

        if (
            autonomous_controller is not None
            and callable(
                getattr(
                    autonomous_controller,
                    "can_handle",
                    None,
                )
            )
            and autonomous_controller.can_handle(
                command
            )
        ):
            thought = {
                "command": command,
                "goal": (
                    "Uruchomić autonomiczny "
                    "proces rozwoju JARVIS OS"
                ),
                "plan": [
                    "Rozpoznać problem lub cel rozwoju",
                    "Przygotować autonomiczny plan zmian",
                    "Dodać bezpieczne zadanie do kolejki AutoDev",
                    "Wygenerować i sprawdzić proponowane zmiany",
                    "Wykonać testy oraz walidację",
                    "Wdrożyć zmianę albo wykonać rollback",
                    "Wygenerować raport końcowy",
                ],
                "actions": [],
                "can_execute": True,
                "handler": "autonomous_autodev",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.meta_controller.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Uruchomić lub obsłużyć "
                    "Meta Executive"
                ),
                "plan": [
                    (
                        "Rozpoznać nadrzędny cel "
                        "dla całego JARVIS OS"
                    ),
                    (
                        "Przeanalizować zakres, "
                        "priorytet i ryzyko"
                    ),
                    (
                        "Wybrać nadrzędną strategię"
                    ),
                    (
                        "Wybrać warstwę wykonawczą"
                    ),
                    (
                        "Delegować cel do Executive AI "
                        "lub innego modułu"
                    ),
                    (
                        "Zweryfikować wynik i zapisać "
                        "wnioski w pamięci Meta Executive"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "meta_executive",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.executive_controller.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Uruchomić lub obsłużyć "
                    "Executive AI"
                ),
                "plan": [
                    (
                        "Rozpoznać cel strategiczny "
                        "dla JARVIS OS"
                    ),
                    (
                        "Przeanalizować zakres, "
                        "priorytet i ryzyko"
                    ),
                    (
                        "Wybrać strategię wykonania"
                    ),
                    (
                        "Delegować cel do "
                        "Project Director lub "
                        "innego modułu"
                    ),
                    (
                        "Zweryfikować wynik "
                        "delegowanego działania"
                    ),
                    (
                        "Zapisać decyzję, wynik "
                        "i wnioski w pamięci Executive AI"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "executive_ai",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.director_controller.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Uruchomić lub obsłużyć "
                    "Autonomous Project Director"
                ),
                "plan": [
                    (
                        "Rozpoznać cel nadrzędnego "
                        "zarządzania projektem"
                    ),
                    (
                        "Przeanalizować kontekst "
                        "oraz stan projektu"
                    ),
                    (
                        "Wybrać najlepszy moduł "
                        "wykonawczy"
                    ),
                    (
                        "Ocenić priorytet, ryzyko "
                        "i potrzebę akceptacji"
                    ),
                    (
                        "Uruchomić Research, Reasoner, "
                        "Self Improvement, Evolution "
                        "lub Continuous Developer"
                    ),
                    (
                        "Zweryfikować wynik i zapisać "
                        "wnioski w pamięci Directora"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "project_director",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.improvement_controller.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Przeprowadzić analizę "
                    "Self Improvement Brain"
                ),
                "plan": [
                    (
                        "Rozpoznać cel "
                        "samodoskonalenia"
                    ),
                    (
                        "Przeanalizować projekt "
                        "i możliwe ulepszenia"
                    ),
                    (
                        "Ocenić priorytet, score "
                        "oraz confidence"
                    ),
                    (
                        "Wybrać najlepszą "
                        "propozycję ulepszenia"
                    ),
                    (
                        "Przekazać zadanie do "
                        "Evolution Engine lub "
                        "Continuous Developer"
                    ),
                    (
                        "Zapisać wynik i wnioski "
                        "w pamięci ulepszeń"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "self_improvement",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.evolution_controller.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Uruchomić lub obsłużyć "
                    "Auto Evolution Engine"
                ),
                "plan": [
                    (
                        "Rozpoznać polecenie "
                        "Evolution Engine"
                    ),
                    (
                        "Utworzyć albo odczytać "
                        "proces ewolucji"
                    ),
                    (
                        "Zaplanować iteracje "
                        "rozwoju projektu"
                    ),
                    (
                        "Uruchomić bezpieczny "
                        "proces ewolucji"
                    ),
                    (
                        "Zapisać wynik, błędy "
                        "i wnioski w pamięci"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "evolution",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.continuous_dev_controller.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Uruchomić lub obsłużyć "
                    "Continuous Developer Loop"
                ),
                "plan": [
                    (
                        "Rozpoznać polecenie "
                        "Continuous Developer"
                    ),
                    (
                        "Utworzyć albo odczytać "
                        "cykl rozwoju"
                    ),
                    (
                        "Przeprowadzić analizę "
                        "projektu"
                    ),
                    (
                        "Wykryć i zaplanować "
                        "ulepszenie"
                    ),
                    (
                        "Przekazać zmianę do "
                        "Research, Reasonera i AutoDev"
                    ),
                    (
                        "Wykonać walidację "
                        "oraz rollback w razie błędu"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "continuous_dev",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.reasoning_service.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Przeprowadzić pełny proces "
                    "rozumowania AI Reasonera"
                ),
                "plan": [
                    (
                        "Rozpoznać rzeczywisty cel "
                        "użytkownika"
                    ),
                    (
                        "Zbudować graf decyzji"
                    ),
                    (
                        "Wygenerować możliwe "
                        "strategie"
                    ),
                    (
                        "Ocenić ryzyko każdej "
                        "strategii"
                    ),
                    (
                        "Wybrać najlepszą "
                        "strategię"
                    ),
                    (
                        "Przekazać wynik do "
                        "Research lub AutoDev"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "reasoner",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.research_service.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Przeprowadzić analizę "
                    "projektu przez Research Agent"
                ),
                "plan": [
                    (
                        "Rozpoznać cel "
                        "i kategorię analizy"
                    ),
                    (
                        "Uruchomić Research Workflow"
                    ),
                    (
                        "Przeskanować projekt "
                        "i odczytać kod"
                    ),
                    (
                        "Wykryć problemy "
                        "oraz przygotować plan"
                    ),
                    (
                        "Wygenerować raport Research"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "research",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        if self.autodev_router.can_handle(
            command
        ):
            thought = {
                "command": command,
                "goal": (
                    "Obsłużyć polecenie AutoDev"
                ),
                "plan": [
                    (
                        "Przekazać polecenie "
                        "do AutoDev Router"
                    ),
                    (
                        "Wykonać operację AutoDev"
                    ),
                    (
                        "Wygenerować raport"
                    ),
                ],
                "actions": [],
                "can_execute": True,
                "handler": "autodev",
            }

            self.cognitive.after_plan(
                thought
            )

            return thought

        plan = self.planner.create_plan(
            command
        )

        self.cognitive.after_plan(
            plan
        )

        return {
            "command": command,
            "goal": plan.get(
                "goal",
                "",
            ),
            "plan": plan.get(
                "steps",
                [],
            ),
            "actions": plan.get(
                "actions",
                [],
            ),
            "can_execute": plan.get(
                "execute",
                False,
            ),
            "handler": "standard",
        }

    def execute(
        self,
        thought: dict,
    ):

        command = thought.get(
            "command",
            "",
        )

        handler = thought.get(
            "handler",
            "standard",
        )

        if handler == "autonomous_autodev":
            response = self._execute_autonomous_dev(
                command
            )

            result = self._format_autonomous_dev_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "meta_executive":
            response = self.meta_controller.handle(
                command=command,
                context={
                    "project_root": "C:/JarvisAI",
                    "metadata": {
                        "source": "Brain",
                    },
                },
            )

            result = self._format_meta_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "executive_ai":
            response = self.executive_controller.handle(
                command=command,
                context={
                    "project_root": "C:/JarvisAI",
                    "metadata": {
                        "source": "Brain",
                    },
                },
            )

            result = self._format_executive_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "project_director":
            response = self.director_controller.handle(
                command=command,
                context={
                    "project_root": "C:/JarvisAI",
                    "metadata": {
                        "source": "Brain",
                    },
                },
            )

            result = self._format_project_director_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "self_improvement":
            response = self.improvement_controller.handle(
                command=command,
                context={
                    "project_root": "C:/JarvisAI",
                    "metadata": {
                        "source": "Brain",
                    },
                },
            )

            result = self._format_improvement_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "evolution":
            response = self.evolution_controller.handle(
                command=command,
                context={
                    "project_root": "C:/JarvisAI",
                    "metadata": {
                        "source": "Brain",
                    },
                },
            )

            result = self._format_evolution_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "continuous_dev":
            response = (
                self.continuous_dev_controller.handle(
                    command=command,
                    context={
                        "project_root": "C:/JarvisAI",
                        "metadata": {
                            "source": "Brain",
                        },
                    },
                )
            )

            result = self._format_continuous_dev_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "reasoner":
            response = self.reasoning_service.handle(
                command=command,
                context={
                    "metadata": {
                        "source": "Brain",
                    },
                },
            )

            result = self._format_reasoning_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "research":
            response = (
                self.research_service.execute(
                    command
                )
            )

            result = self._format_research_response(
                response
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        if handler == "autodev":
            result = self.autodev_router.handle(
                command
            )

            self._remember_execution(
                command,
                result,
            )

            return result

        actions = thought.get(
            "actions",
            [],
        )

        if actions:
            results = []

            for action in actions:
                action_result = (
                    self.executor.execute_action(
                        action
                    )
                )

                results.append(
                    str(action_result)
                )

                if (
                    action.get(
                        "action_type"
                    )
                    == ActionTypes.OPEN_APP
                ):
                    time.sleep(2)

            final_result = " | ".join(
                results
            )

            self._remember_execution(
                command,
                final_result,
            )

            return final_result

        task = self.task_planner.create_task(
            command
        )

        result = self.agent_loop.run(
            task
        )

        self._remember_execution(
            command,
            result,
        )

        return result

    def _build_autonomous_dev_controller(
        self,
    ) -> AutonomousDevController:

        constructors = (
            {
                "project_root": "C:/JarvisAI",
                "pipeline": self.autodev_pipeline,
            },
            {
                "pipeline": self.autodev_pipeline,
            },
            {
                "project_root": "C:/JarvisAI",
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
                        pass

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
            "project_root": "C:/JarvisAI",
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

    def _format_autonomous_dev_response(
        self,
        response: dict[str, Any],
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = bool(
            response.get(
                "success",
                False,
            )
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        task_id = str(
            response.get(
                "task_id",
                response.get(
                    "autodev_task_id",
                    "",
                ),
            )
        ).strip()

        lines = [
            (
                "Autonomous AutoDev "
                "obsłużył polecenie."
                if success
                else (
                    "Autonomous AutoDev nie zakończył "
                    "operacji poprawnie."
                )
            ),
            f"Status: {status}",
        ]

        if task_id:
            lines.append(
                f"Task ID: {task_id}"
            )

        message = response.get(
            "message"
        )

        if message:
            lines.append(
                f"Wynik: {message}"
            )

        if status.upper() in {
            "QUEUED",
            "PENDING",
            "READY",
        }:
            lines.append(
                "Zadanie zostało dodane "
                "do autonomicznej kolejki."
            )

        if status.upper() == "WAITING_FOR_APPROVAL":
            lines.append(
                "Zmiany są przygotowane "
                "i czekają na akceptację."
            )

        if status.upper() == "COMPLETED":
            lines.append(
                "Zmiany zostały wykonane "
                "i zweryfikowane."
            )

        if status.upper() == "ROLLED_BACK":
            lines.append(
                "Wykryto błąd i bezpiecznie "
                "cofnięto zmiany."
            )

        changed_files = response.get(
            "changed_files",
            [],
        )

        if isinstance(
            changed_files,
            list,
        ) and changed_files:
            lines.append(
                "Zmienione pliki: "
                + ", ".join(
                    str(path)
                    for path in changed_files
                )
            )

        error = response.get(
            "error"
        )

        if error:
            lines.append(
                f"Błąd: {error}"
            )

        errors = response.get(
            "errors",
            [],
        )

        if isinstance(
            errors,
            list,
        ) and errors:
            lines.append(
                "Błędy: "
                + "; ".join(
                    str(item)
                    for item in errors
                )
            )

        return "\n".join(
            lines
        )

    def _format_meta_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        meta_id = str(
            response.get(
                "meta_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Meta Executive "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if meta_id:
                lines.append(
                    f"Meta ID: {meta_id}"
                )

            selected_strategy = response.get(
                "selected_strategy"
            )

            if selected_strategy:
                lines.append(
                    "Strategia: "
                    f"{selected_strategy}"
                )

            selected_layer = response.get(
                "selected_layer"
            )

            if selected_layer:
                lines.append(
                    "Wybrana warstwa: "
                    f"{selected_layer}"
                )

            cycle = response.get(
                "cycle"
            )

            if cycle is not None:
                lines.append(
                    f"Cykl: {cycle}"
                )

            if response.get(
                "requires_approval",
                False,
            ):
                lines.append(
                    "Proces wymaga akceptacji "
                    "przed wykonaniem."
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Meta Executive czeka "
                    "na akceptację."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces nadrzędnego zarządzania "
                    "został zakończony poprawnie."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                current_stage = summary.get(
                    "current_stage"
                )

                priority = summary.get(
                    "priority"
                )

                risk_level = summary.get(
                    "risk_level"
                )

                if current_stage:
                    lines.append(
                        f"Etap: {current_stage}"
                    )

                if priority:
                    lines.append(
                        f"Priorytet: {priority}"
                    )

                if risk_level:
                    lines.append(
                        f"Ryzyko: {risk_level}"
                    )

            sessions = response.get(
                "sessions"
            )

            if isinstance(
                sessions,
                list,
            ):
                lines.append(
                    "Liczba sesji: "
                    f"{len(sessions)}"
                )

            memory_summary = response.get(
                "memory_summary"
            )

            if isinstance(
                memory_summary,
                dict,
            ):
                total_records = memory_summary.get(
                    "total_records"
                )

                if total_records is not None:
                    lines.append(
                        "Rekordy pamięci: "
                        f"{total_records}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Meta Executive zakończył "
                    "operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Meta Executive nie zakończył "
                "operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if meta_id:
            lines.append(
                f"Meta ID: {meta_id}"
            )

        return "\n".join(
            lines
        )

    def _format_executive_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        executive_id = str(
            response.get(
                "executive_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Executive AI "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if executive_id:
                lines.append(
                    f"Executive ID: {executive_id}"
                )

            selected_strategy = response.get(
                "selected_strategy"
            )

            if selected_strategy:
                lines.append(
                    "Strategia: "
                    f"{selected_strategy}"
                )

            delegated_module = response.get(
                "delegated_module"
            )

            if delegated_module:
                lines.append(
                    "Delegowany moduł: "
                    f"{delegated_module}"
                )

            phase = response.get(
                "phase"
            )

            if phase is not None:
                lines.append(
                    f"Faza: {phase}"
                )

            if response.get(
                "requires_approval",
                False,
            ):
                lines.append(
                    "Proces wymaga akceptacji "
                    "przed wykonaniem."
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Executive AI czeka "
                    "na akceptację."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces strategiczny został "
                    "zakończony poprawnie."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                current_phase = summary.get(
                    "current_phase"
                )

                priority = summary.get(
                    "priority"
                )

                risk_level = summary.get(
                    "risk_level"
                )

                if current_phase:
                    lines.append(
                        f"Etap: {current_phase}"
                    )

                if priority:
                    lines.append(
                        f"Priorytet: {priority}"
                    )

                if risk_level:
                    lines.append(
                        f"Ryzyko: {risk_level}"
                    )

            sessions = response.get(
                "sessions"
            )

            if isinstance(
                sessions,
                list,
            ):
                lines.append(
                    "Liczba sesji: "
                    f"{len(sessions)}"
                )

            memory_summary = response.get(
                "memory_summary"
            )

            if isinstance(
                memory_summary,
                dict,
            ):
                total_records = memory_summary.get(
                    "total_records"
                )

                if total_records is not None:
                    lines.append(
                        "Rekordy pamięci: "
                        f"{total_records}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Executive AI zakończył "
                    "operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Executive AI nie zakończył "
                "operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if executive_id:
            lines.append(
                f"Executive ID: {executive_id}"
            )

        return "\n".join(
            lines
        )

    def _format_project_director_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        director_id = str(
            response.get(
                "director_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Autonomous Project Director "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if director_id:
                lines.append(
                    f"Director ID: {director_id}"
                )

            selected_module = response.get(
                "selected_module"
            )

            if selected_module:
                lines.append(
                    "Wybrany moduł: "
                    f"{selected_module}"
                )

            iteration = response.get(
                "iteration"
            )

            if iteration is not None:
                lines.append(
                    f"Iteracja: {iteration}"
                )

            if response.get(
                "requires_approval",
                False,
            ):
                lines.append(
                    "Proces wymaga akceptacji "
                    "przed wykonaniem."
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Project Director czeka "
                    "na akceptację."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces zarządzania projektem "
                    "został zakończony poprawnie."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                current_stage = summary.get(
                    "current_stage"
                )

                priority = summary.get(
                    "priority"
                )

                risk_level = summary.get(
                    "risk_level"
                )

                if current_stage:
                    lines.append(
                        f"Etap: {current_stage}"
                    )

                if priority:
                    lines.append(
                        f"Priorytet: {priority}"
                    )

                if risk_level:
                    lines.append(
                        f"Ryzyko: {risk_level}"
                    )

            sessions = response.get(
                "sessions"
            )

            if isinstance(
                sessions,
                list,
            ):
                lines.append(
                    "Liczba sesji: "
                    f"{len(sessions)}"
                )

            memory_summary = response.get(
                "memory_summary"
            )

            if isinstance(
                memory_summary,
                dict,
            ):
                total_records = memory_summary.get(
                    "total_records"
                )

                if total_records is not None:
                    lines.append(
                        "Rekordy pamięci: "
                        f"{total_records}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Autonomous Project Director "
                    "zakończył operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Autonomous Project Director nie "
                "zakończył operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if director_id:
            lines.append(
                f"Director ID: {director_id}"
            )

        return "\n".join(
            lines
        )

    def _format_improvement_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        session_id = str(
            response.get(
                "session_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Self Improvement Brain "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if session_id:
                lines.append(
                    f"Session ID: {session_id}"
                )

            decision = response.get(
                "decision"
            )

            if decision:
                lines.append(
                    f"Decyzja: {decision}"
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Sesja czeka na akceptację "
                    "przed wykonaniem zmian."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces samodoskonalenia został "
                    "zakończony poprawnie."
                )

            if status == "NO_ACTION":
                lines.append(
                    "Nie wykryto działania, które "
                    "należy teraz wykonać."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                sessions = summary.get(
                    "sessions"
                )

                memory = summary.get(
                    "memory"
                )

                if isinstance(
                    sessions,
                    list,
                ):
                    lines.append(
                        "Liczba sesji: "
                        f"{len(sessions)}"
                    )

                if isinstance(
                    memory,
                    dict,
                ):
                    total_records = memory.get(
                        "total_records",
                        memory.get(
                            "count"
                        ),
                    )

                    if total_records is not None:
                        lines.append(
                            "Rekordy pamięci: "
                            f"{total_records}"
                        )

            error = response.get(
                "error"
            )

            if error:
                lines.append(
                    f"Informacja: {error}"
                )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Self Improvement Brain "
                    "zakończył operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Self Improvement Brain nie "
                "zakończył operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if session_id:
            lines.append(
                f"Session ID: {session_id}"
            )

        return "\n".join(
            lines
        )

    def _format_evolution_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        evolution_id = str(
            response.get(
                "evolution_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Auto Evolution Engine "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if evolution_id:
                lines.append(
                    f"Evolution ID: {evolution_id}"
                )

            iteration = response.get(
                "iteration"
            )

            if iteration is not None:
                lines.append(
                    f"Iteracja: {iteration}"
                )

            decision = response.get(
                "decision"
            )

            if decision:
                lines.append(
                    f"Decyzja: {decision}"
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Proces ewolucji czeka na "
                    "akceptację zmian."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces ewolucji został "
                    "zakończony poprawnie."
                )

            if status == "NO_CHANGES":
                lines.append(
                    "Nie wykryto zmian wymagających "
                    "wykonania."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                runs = summary.get(
                    "runs"
                )

                if isinstance(
                    runs,
                    list,
                ):
                    lines.append(
                        "Liczba procesów ewolucji: "
                        f"{len(runs)}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Auto Evolution Engine "
                    "zakończył operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Auto Evolution Engine nie "
                "zakończył operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if evolution_id:
            lines.append(
                f"Evolution ID: {evolution_id}"
            )

        return "\n".join(
            lines
        )

    def _format_continuous_dev_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        cycle_id = str(
            response.get(
                "cycle_id",
                "",
            )
        )

        if success:
            lines = [
                (
                    "Continuous Developer "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if cycle_id:
                lines.append(
                    f"Cycle ID: {cycle_id}"
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Cykl czeka na akceptację "
                    "przed wykonaniem zmian."
                )

            if status == "COMPLETED":
                lines.append(
                    "Cykl rozwoju został "
                    "zakończony poprawnie."
                )

            if status == "NO_CHANGES":
                lines.append(
                    "Nie wykryto zmian wymagających "
                    "wykonania."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                current_stage = summary.get(
                    "current_stage"
                )

                iteration = summary.get(
                    "iteration"
                )

                if current_stage:
                    lines.append(
                        f"Etap: {current_stage}"
                    )

                if iteration is not None:
                    lines.append(
                        f"Iteracja: {iteration}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Continuous Developer "
                    "zakończył operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Continuous Developer nie zakończył "
                "operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if cycle_id:
            lines.append(
                f"Cycle ID: {cycle_id}"
            )

        return "\n".join(
            lines
        )

    def _format_reasoning_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(response)

        if not response.get(
            "handled",
            False,
        ):
            return (
                "AI Reasoner nie rozpoznał "
                "tego polecenia."
            )

        if response.get(
            "success",
            False,
        ) is False:
            error = response.get(
                "error",
                "",
            )

            result = response.get(
                "result",
                {},
            )

            if (
                not error
                and isinstance(
                    result,
                    dict,
                )
            ):
                error = result.get(
                    "error",
                    "",
                )

            if error:
                return (
                    "AI Reasoner zakończył proces "
                    f"błędem: {error}"
                )

        result = response.get(
            "result",
            {},
        )

        if not isinstance(
            result,
            dict,
        ):
            return str(result)

        session_id = result.get(
            "session_id",
            "",
        )

        strategy = result.get(
            "strategy",
            {},
        )

        if not isinstance(
            strategy,
            dict,
        ):
            strategy = {}

        selected_option = strategy.get(
            "selected_option",
            {},
        )

        if not isinstance(
            selected_option,
            dict,
        ):
            selected_option = {}

        risk_assessment = strategy.get(
            "risk_assessment",
            {},
        )

        if not isinstance(
            risk_assessment,
            dict,
        ):
            risk_assessment = {}

        strategy_name = strategy.get(
            "name",
            selected_option.get(
                "name",
                "Brak strategii",
            ),
        )

        risk_level = risk_assessment.get(
            "risk_level",
            result.get(
                "risk_result",
                {},
            ).get(
                "overall_risk_level",
                "UNKNOWN",
            )
            if isinstance(
                result.get(
                    "risk_result",
                    {},
                ),
                dict,
            )
            else "UNKNOWN",
        )

        status = result.get(
            "status",
            response.get(
                "status",
                "UNKNOWN",
            ),
        )

        requires_confirmation = result.get(
            "requires_confirmation",
            strategy.get(
                "requires_confirmation",
                False,
            ),
        )

        blocking_reasons = result.get(
            "blocking_reasons",
            strategy.get(
                "blocking_reasons",
                [],
            ),
        )

        lines = [
            "AI Reasoner zakończył analizę.",
            f"Status: {status}",
            f"Strategia: {strategy_name}",
            f"Poziom ryzyka: {risk_level}",
        ]

        if session_id:
            lines.append(
                f"Session ID: {session_id}"
            )

        if requires_confirmation:
            lines.append(
                "Wymagana jest akceptacja "
                "przed wykonaniem zmian."
            )

        if isinstance(
            blocking_reasons,
            list,
        ) and blocking_reasons:
            lines.append(
                "Blokady: "
                + "; ".join(
                    str(reason)
                    for reason in blocking_reasons
                )
            )

        return "\n".join(lines)

    def _format_research_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        report = response.get(
            "report",
            "",
        )

        if report:
            return str(
                report
            )

        success = response.get(
            "success",
            False,
        )

        if success:
            return (
                "Research Agent zakończył "
                "analizę projektu."
            )

        error = response.get(
            "error",
            "",
        )

        if error:
            return (
                "Research Agent nie zakończył "
                f"analizy: {error}"
            )

        return (
            "Research Agent nie zwrócił raportu."
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
