"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from app.ai.brain import Brain


class FakeCognitiveEngine:

    def __init__(self) -> None:
        self.before_commands: list[str] = []
        self.plans: list[dict[str, Any]] = []
        self.executions: list[tuple[str, str]] = []

    def before_think(
        self,
        command: str,
    ) -> None:
        self.before_commands.append(
            command
        )

    def after_plan(
        self,
        plan: dict[str, Any],
    ) -> None:
        self.plans.append(
            dict(plan)
        )

    def after_execute(
        self,
        command: str,
        result: str,
    ) -> None:
        self.executions.append(
            (
                command,
                result,
            )
        )


class FakeMemory:

    def __init__(
        self,
    ) -> None:
        self.history: list[
            tuple[str, str]
        ] = []

    def add_history(
        self,
        command: str,
        result: str,
    ) -> None:
        self.history.append(
            (
                command,
                result,
            )
        )


class FakeContinuousDevController:

    def __init__(
        self,
        can_handle_result: bool = True,
        response: dict[str, Any] | None = None,
    ) -> None:

        self.can_handle_result = (
            can_handle_result
        )

        self.response = (
            dict(response)
            if isinstance(
                response,
                dict,
            )
            else {
                "success": True,
                "status": (
                    "WAITING_FOR_APPROVAL"
                ),
                "cycle_id": (
                    "development_cycle_test"
                ),
                "summary": {
                    "current_stage": (
                        "APPROVE"
                    ),
                    "iteration": 1,
                },
            }
        )

        self.handled_commands: list[
            tuple[
                str,
                dict[str, Any],
            ]
        ] = []

    def can_handle(
        self,
        command: str,
    ) -> bool:

        return self.can_handle_result

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        self.handled_commands.append(
            (
                command,
                dict(context or {}),
            )
        )

        return dict(
            self.response
        )


class FakeReasoningService:

    def __init__(
        self,
        can_handle_result: bool = False,
    ) -> None:

        self.can_handle_result = (
            can_handle_result
        )

    def can_handle(
        self,
        command: str,
    ) -> bool:

        return self.can_handle_result


class FakeResearchService:

    def __init__(
        self,
        can_handle_result: bool = False,
    ) -> None:

        self.can_handle_result = (
            can_handle_result
        )

    def can_handle(
        self,
        command: str,
    ) -> bool:

        return self.can_handle_result


class FakeAutoDevRouter:

    def __init__(
        self,
        can_handle_result: bool = False,
    ) -> None:

        self.can_handle_result = (
            can_handle_result
        )

    def can_handle(
        self,
        command: str,
    ) -> bool:

        return self.can_handle_result


class BrainContinuousDevIntegrationTests(
    unittest.TestCase
):

    def build_brain(
        self,
        continuous_controller: (
            FakeContinuousDevController
            | None
        ) = None,
    ) -> Brain:

        brain = Brain.__new__(
            Brain
        )

        brain.cognitive = (
            FakeCognitiveEngine()
        )

        brain.memory = FakeMemory()


        brain.meta_controller = MagicMock()
        brain.meta_controller.can_handle.return_value = False

        brain.executive_controller = MagicMock()
        brain.executive_controller.can_handle.return_value = False

        brain.director_controller = MagicMock()
        brain.director_controller.can_handle.return_value = False

        brain.improvement_controller = MagicMock()
        brain.improvement_controller.can_handle.return_value = False

        brain.evolution_controller = MagicMock()
        brain.evolution_controller.can_handle.return_value = False


        brain.continuous_dev_controller = (
            continuous_controller
            or FakeContinuousDevController()
        )

        brain.reasoning_service = (
            FakeReasoningService(
                can_handle_result=False
            )
        )

        brain.research_service = (
            FakeResearchService(
                can_handle_result=False
            )
        )

        brain.autodev_router = (
            FakeAutoDevRouter(
                can_handle_result=False
            )
        )

        brain.planner = MagicMock()
        brain.executor = MagicMock()
        brain.task_planner = MagicMock()
        brain.agent_loop = MagicMock()

        return brain

    def test_brain_routes_continuous_dev_command(
        self,
    ) -> None:

        brain = self.build_brain()

        thought = brain.think(
            "continuous dev start "
            "popraw stabilność projektu"
        )

        self.assertEqual(
            thought["handler"],
            "continuous_dev",
        )

        self.assertTrue(
            thought["can_execute"]
        )

        self.assertGreater(
            len(
                thought["plan"]
            ),
            3,
        )

        self.assertEqual(
            brain.cognitive.before_commands,
            [
                (
                    "continuous dev start "
                    "popraw stabilność projektu"
                )
            ],
        )

    def test_continuous_dev_has_routing_priority(
        self,
    ) -> None:

        brain = self.build_brain()

        brain.reasoning_service = (
            FakeReasoningService(
                can_handle_result=True
            )
        )

        brain.research_service = (
            FakeResearchService(
                can_handle_result=True
            )
        )

        brain.autodev_router = (
            FakeAutoDevRouter(
                can_handle_result=True
            )
        )

        thought = brain.think(
            "continuous dev summary"
        )

        self.assertEqual(
            thought["handler"],
            "continuous_dev",
        )

    def test_brain_executes_continuous_dev(
        self,
    ) -> None:

        controller = (
            FakeContinuousDevController(
                response={
                    "success": True,
                    "status": (
                        "WAITING_FOR_APPROVAL"
                    ),
                    "cycle_id": (
                        "development_cycle_123"
                    ),
                    "summary": {
                        "current_stage": (
                            "APPROVE"
                        ),
                        "iteration": 1,
                    },
                }
            )
        )

        brain = self.build_brain(
            continuous_controller=controller
        )

        result = brain.execute(
            {
                "command": (
                    "continuous dev start "
                    "napraw błędy projektu"
                ),
                "handler": (
                    "continuous_dev"
                ),
            }
        )

        self.assertIn(
            "Continuous Developer",
            result,
        )

        self.assertIn(
            "WAITING_FOR_APPROVAL",
            result,
        )

        self.assertIn(
            "development_cycle_123",
            result,
        )

        self.assertEqual(
            len(
                controller.handled_commands
            ),
            1,
        )

        command, context = (
            controller.handled_commands[0]
        )

        self.assertEqual(
            command,
            (
                "continuous dev start "
                "napraw błędy projektu"
            ),
        )

        self.assertEqual(
            context["project_root"],
            "C:/JarvisAI",
        )

    def test_brain_remembers_continuous_dev_result(
        self,
    ) -> None:

        brain = self.build_brain()

        command = (
            "continuous dev start "
            "popraw testy"
        )

        result = brain.execute(
            {
                "command": command,
                "handler": (
                    "continuous_dev"
                ),
            }
        )

        self.assertEqual(
            len(
                brain.memory.history
            ),
            1,
        )

        remembered_command, remembered_result = (
            brain.memory.history[0]
        )

        self.assertEqual(
            remembered_command,
            command,
        )

        self.assertEqual(
            remembered_result,
            result,
        )

        self.assertEqual(
            len(
                brain.cognitive.executions
            ),
            1,
        )

    def test_brain_formats_completed_cycle(
        self,
    ) -> None:

        controller = (
            FakeContinuousDevController(
                response={
                    "success": True,
                    "status": "COMPLETED",
                    "cycle_id": (
                        "development_cycle_done"
                    ),
                    "summary": {
                        "current_stage": "REPORT",
                        "iteration": 2,
                    },
                }
            )
        )

        brain = self.build_brain(
            continuous_controller=controller
        )

        result = brain.execute(
            {
                "command": (
                    "continuous dev summary"
                ),
                "handler": (
                    "continuous_dev"
                ),
            }
        )

        self.assertIn(
            "COMPLETED",
            result,
        )

        self.assertIn(
            "zakończony poprawnie",
            result,
        )

        self.assertIn(
            "REPORT",
            result,
        )

        self.assertIn(
            "Iteracja: 2",
            result,
        )

    def test_brain_formats_continuous_dev_error(
        self,
    ) -> None:

        controller = (
            FakeContinuousDevController(
                response={
                    "success": False,
                    "status": "FAILED",
                    "cycle_id": (
                        "development_cycle_failed"
                    ),
                    "error": (
                        "Testowy błąd integracji."
                    ),
                }
            )
        )

        brain = self.build_brain(
            continuous_controller=controller
        )

        result = brain.execute(
            {
                "command": (
                    "continuous dev start test"
                ),
                "handler": (
                    "continuous_dev"
                ),
            }
        )

        self.assertIn(
            "FAILED",
            result,
        )

        self.assertIn(
            "Testowy błąd integracji",
            result,
        )

        self.assertIn(
            "development_cycle_failed",
            result,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
