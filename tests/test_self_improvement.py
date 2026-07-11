from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from app.ai.self_improvement.improvement_brain import (
    ImprovementBrain,
)
from app.ai.self_improvement.improvement_controller import (
    ImprovementController,
)
from app.ai.self_improvement.improvement_memory import (
    ImprovementMemory,
)


class FakeResearchService:

    def execute(
        self,
        command: str,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "status": "COMPLETED",
            "report": (
                "Przeanalizowano projekt "
                "i zależności ulepszenia."
            ),
            "command": command,
        }


class FakeReasoningService:

    def reason(
        self,
        user_request: str,
        research_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
        auto_execute: bool = False,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "status": "COMPLETED",
            "requires_confirmation": False,
            "strategy": {
                "name": "SAFE_INCREMENTAL_CHANGE",
            },
            "user_request": user_request,
            "research_context": research_context or {},
            "project_context": project_context or {},
            "auto_execute": auto_execute,
        }


class FakeEvolutionController:

    def __init__(
        self,
    ) -> None:

        self.calls: list[
            dict[str, Any]
        ] = []

    def create_and_start(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        self.calls.append(
            {
                "objective": objective,
                "mode": mode,
                "context": context or {},
                "metadata": metadata or {},
            }
        )

        return {
            "success": True,
            "status": "COMPLETED",
            "evolution_id": "evolution_test",
            "lessons": [
                "Evolution Engine zakończył zmianę."
            ],
            "summary": {
                "lessons": [
                    "Evolution Engine zakończył zmianę."
                ]
            },
        }


class FakeContinuousDevController:

    def __init__(
        self,
    ) -> None:

        self.calls: list[
            dict[str, Any]
        ] = []

    def create_and_start(
        self,
        objective: str,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        self.calls.append(
            {
                "objective": objective,
                "auto_approve": auto_approve,
                "context": context or {},
                "metadata": metadata or {},
            }
        )

        return {
            "success": True,
            "status": "COMPLETED",
            "cycle_id": "development_cycle_test",
            "lessons": [
                "Continuous Developer zakończył zmianę."
            ],
            "summary": {
                "lessons": [
                    "Continuous Developer zakończył zmianę."
                ]
            },
        }


class SelfImprovementTests(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        root = Path(
            self.temp_directory.name
        )

        self.memory = ImprovementMemory(
            storage_path=(
                root
                / "improvement_memory.json"
            )
        )

        self.research = FakeResearchService()
        self.reasoning = FakeReasoningService()
        self.evolution = FakeEvolutionController()
        self.continuous = FakeContinuousDevController()

        self.brain = ImprovementBrain(
            project_root=self.temp_directory.name,
            research_service=self.research,
            reasoning_service=self.reasoning,
            evolution_controller=self.evolution,
            continuous_dev_controller=(
                self.continuous
            ),
        )

        self.controller = ImprovementController(
            project_root=self.temp_directory.name,
            improvement_brain=self.brain,
            improvement_memory=self.memory,
        )

    def tearDown(
        self,
    ) -> None:

        self.temp_directory.cleanup()

    def test_brain_generates_proposal(
        self,
    ) -> None:

        result = self.brain.analyze(
            objective="Poprawić stabilność projektu.",
            project_context={
                "problems": [
                    {
                        "title": "Błąd importu",
                        "description": (
                            "ImportError powoduje awarię."
                        ),
                        "severity": "MEDIUM",
                        "affected_files": [
                            "app/test_module.py"
                        ],
                    }
                ]
            },
        )

        self.assertTrue(
            result["success"]
        )

        self.assertGreater(
            len(result["proposals"]),
            0,
        )

        selected = result[
            "selected_proposal"
        ]

        self.assertEqual(
            selected["category"],
            "BUG_FIX",
        )

        self.assertEqual(
            selected["priority"],
            "MEDIUM",
        )

    def test_high_priority_waits_for_approval(
        self,
    ) -> None:

        result = self.brain.analyze(
            objective="Naprawić krytyczny problem.",
            project_context={
                "problems": [
                    {
                        "title": (
                            "Krytyczny błąd systemu"
                        ),
                        "description": (
                            "Awaria powoduje utratę danych."
                        ),
                        "severity": "CRITICAL",
                    }
                ]
            },
            auto_execute=True,
            approved=None,
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "WAITING_FOR_APPROVAL",
        )

        self.assertEqual(
            result["decision"],
            "WAIT_FOR_APPROVAL",
        )

    def test_approved_session_executes(
        self,
    ) -> None:

        analyzed = self.brain.analyze(
            objective="Naprawić krytyczny problem.",
            project_context={
                "problems": [
                    {
                        "title": (
                            "Krytyczny błąd systemu"
                        ),
                        "description": (
                            "Awaria powoduje utratę danych."
                        ),
                        "severity": "CRITICAL",
                    }
                ]
            },
            auto_execute=True,
        )

        result = self.brain.execute(
            session_id=analyzed[
                "session_id"
            ],
            approved=True,
            context={},
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        self.assertGreater(
            len(result["lessons"]),
            0,
        )

    def test_autonomous_mode_uses_evolution(
        self,
    ) -> None:

        result = self.brain.analyze(
            objective=(
                "Automatycznie popraw jakość projektu."
            ),
            project_context={
                "suggestions": [
                    {
                        "title": (
                            "Uprościć strukturę kodu"
                        ),
                        "description": (
                            "Zmniejszyć duplikację."
                        ),
                        "severity": "MEDIUM",
                    }
                ]
            },
            auto_execute=True,
            approved=True,
            mode="AUTONOMOUS",
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        self.assertEqual(
            len(self.evolution.calls),
            1,
        )

        self.assertEqual(
            self.evolution.calls[0]["mode"],
            "AUTONOMOUS",
        )

    def test_manual_analysis_selects_continuous_dev(
        self,
    ) -> None:

        result = self.brain.analyze(
            objective="Poprawić moduł testowy.",
            project_context={
                "suggestions": [
                    {
                        "title": (
                            "Dodać brakujące testy"
                        ),
                        "description": (
                            "Zwiększyć pokrycie testami."
                        ),
                        "severity": "MEDIUM",
                    }
                ]
            },
            auto_execute=False,
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["decision"],
            "START_CONTINUOUS_DEV",
        )

        self.assertEqual(
            result["status"],
            "PLANNING",
        )

    def test_execute_manual_session_uses_continuous_dev(
        self,
    ) -> None:

        analyzed = self.brain.analyze(
            objective="Poprawić moduł testowy.",
            project_context={
                "suggestions": [
                    {
                        "title": (
                            "Dodać brakujące testy"
                        ),
                        "description": (
                            "Zwiększyć pokrycie testami."
                        ),
                        "severity": "MEDIUM",
                    }
                ]
            },
            auto_execute=False,
        )

        result = self.brain.execute(
            session_id=analyzed[
                "session_id"
            ],
            approved=True,
            context={},
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        self.assertEqual(
            len(self.continuous.calls),
            1,
        )

    def test_memory_records_completed_session(
        self,
    ) -> None:

        result = self.controller.handle(
            command=(
                "self improvement autonomous "
                "popraw jakość projektu"
            ),
            context={
                "suggestions": [
                    {
                        "title": (
                            "Uprościć strukturę kodu"
                        ),
                        "description": (
                            "Zmniejszyć duplikację."
                        ),
                        "severity": "MEDIUM",
                    }
                ]
            },
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        memory_entry = self.memory.get(
            result["session_id"]
        )

        self.assertIsNotNone(
            memory_entry
        )

        self.assertEqual(
            memory_entry["status"],
            "COMPLETED",
        )

    def test_memory_summary(
        self,
    ) -> None:

        self.memory.remember(
            session={
                "session_id": "session_test",
                "status": "COMPLETED",
                "decision": "START_EVOLUTION",
                "selected_proposal": {
                    "proposal_id": "proposal_test",
                    "title": "Test ulepszenia",
                    "category": "TESTING",
                    "priority": "HIGH",
                    "score": 80.0,
                },
                "lessons": [
                    "Test zakończony poprawnie."
                ],
                "metadata": {
                    "objective": (
                        "Sprawdzić pamięć."
                    ),
                },
            },
            result={
                "success": True,
                "status": "COMPLETED",
            },
        )

        summary = self.memory.summary()

        self.assertEqual(
            summary["entries_count"],
            1,
        )

        self.assertEqual(
            summary["completed_sessions"],
            1,
        )

        self.assertEqual(
            summary["categories"]["TESTING"],
            1,
        )

        self.assertEqual(
            summary["priorities"]["HIGH"],
            1,
        )

    def test_memory_save_and_load(
        self,
    ) -> None:

        self.memory.remember(
            session={
                "session_id": "session_saved",
                "status": "COMPLETED",
                "decision": "START_EVOLUTION",
                "selected_proposal": {
                    "title": "Zapis pamięci",
                    "category": "GENERAL",
                    "priority": "MEDIUM",
                    "score": 50.0,
                },
                "metadata": {
                    "objective": (
                        "Sprawdzić zapis."
                    ),
                },
            }
        )

        loaded_memory = ImprovementMemory(
            storage_path=(
                Path(
                    self.temp_directory.name
                )
                / "improvement_memory.json"
            )
        )

        loaded = loaded_memory.get(
            "session_saved"
        )

        self.assertIsNotNone(
            loaded
        )

        self.assertEqual(
            loaded["objective"],
            "Sprawdzić zapis.",
        )

    def test_controller_recognizes_commands(
        self,
    ) -> None:

        self.assertTrue(
            self.controller.can_handle(
                "self improvement summary"
            )
        )

        self.assertTrue(
            self.controller.can_handle(
                "samodoskonalenie start "
                "popraw projekt"
            )
        )

        self.assertTrue(
            self.controller.can_handle(
                "ulepsz siebie popraw testy"
            )
        )

        self.assertFalse(
            self.controller.can_handle(
                "otwórz youtube"
            )
        )

    def test_controller_status_command(
        self,
    ) -> None:

        result = self.controller.analyze(
            objective="Sprawdzić status sesji.",
            project_context={
                "suggestions": [
                    {
                        "title": "Dodać test",
                        "description": (
                            "Dodać brakujący test."
                        ),
                        "severity": "MEDIUM",
                    }
                ]
            },
        )

        status_result = self.controller.handle(
            command=(
                "self improvement status "
                + result["session_id"]
            )
        )

        self.assertTrue(
            status_result["success"]
        )

        self.assertEqual(
            status_result["status"],
            "FOUND",
        )

        self.assertEqual(
            status_result["session_id"],
            result["session_id"],
        )

    def test_unknown_session_returns_not_found(
        self,
    ) -> None:

        result = self.brain.execute(
            session_id="missing_session",
            approved=True,
        )

        self.assertFalse(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "NOT_FOUND",
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
