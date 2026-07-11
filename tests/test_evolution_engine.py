from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from app.ai.evolution.evolution_controller import (
    EvolutionController,
)
from app.ai.evolution.evolution_engine import (
    EvolutionEngine,
    EvolutionMode,
    EvolutionStatus,
)
from app.ai.evolution.evolution_memory import (
    EvolutionMemory,
)
from app.ai.evolution.evolution_planner import (
    EvolutionPlanner,
)


class FakeContinuousDevController:

    def __init__(
        self,
    ) -> None:

        self.cycles: dict[
            str,
            dict[str, Any],
        ] = {}

        self.counter = 0

    def create_and_start(
        self,
        objective: str,
        max_iterations: int = 1,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        self.counter += 1

        cycle_id = (
            f"development_cycle_{self.counter}"
        )

        self.cycles[cycle_id] = {
            "objective": objective,
            "approved": auto_approve,
            "context": context or {},
            "metadata": metadata or {},
        }

        if auto_approve:
            return {
                "success": True,
                "status": "COMPLETED",
                "cycle_id": cycle_id,
                "lessons": [
                    "Zmiana została wykonana poprawnie."
                ],
                "summary": {
                    "current_stage": "REPORT",
                    "iteration": 1,
                },
            }

        return {
            "success": True,
            "status": "WAITING_FOR_APPROVAL",
            "cycle_id": cycle_id,
            "summary": {
                "current_stage": "APPROVE",
                "iteration": 1,
            },
        }

    def approve_cycle(
        self,
        cycle_id: str,
        approved: bool,
        note: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        if cycle_id not in self.cycles:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "cycle_id": cycle_id,
            }

        if not approved:
            return {
                "success": False,
                "status": "CANCELLED",
                "cycle_id": cycle_id,
                "note": note,
            }

        self.cycles[
            cycle_id
        ]["approved"] = True

        return {
            "success": True,
            "status": "COMPLETED",
            "cycle_id": cycle_id,
            "lessons": [
                "Akceptacja została obsłużona."
            ],
            "summary": {
                "current_stage": "REPORT",
                "iteration": 1,
            },
        }

    def cancel_cycle(
        self,
        cycle_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        return {
            "success": False,
            "status": "CANCELLED",
            "cycle_id": cycle_id,
            "reason": reason,
        }


class EvolutionEngineTests(
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

        self.fake_continuous = (
            FakeContinuousDevController()
        )

        self.engine = EvolutionEngine(
            project_root=self.temp_directory.name,
            continuous_dev_controller=(
                self.fake_continuous
            ),
            storage_path=(
                root
                / "evolution_runs.json"
            ),
            default_max_iterations=3,
        )

        self.memory = EvolutionMemory(
            storage_path=(
                root
                / "evolution_memory.json"
            )
        )

        self.controller = EvolutionController(
            project_root=self.temp_directory.name,
            evolution_engine=self.engine,
            evolution_memory=self.memory,
            evolution_planner=(
                EvolutionPlanner()
            ),
        )

    def tearDown(
        self,
    ) -> None:

        self.temp_directory.cleanup()

    def test_evolution_planner_builds_plan(
        self,
    ) -> None:

        planner = EvolutionPlanner()

        plan = planner.build(
            objective=(
                "Poprawić stabilność JARVIS OS."
            ),
            mode="SAFE_AUTONOMOUS",
            iterations=4,
            context={
                "priority": "CRITICAL",
            },
        )

        self.assertTrue(
            plan["plan_id"].startswith(
                "evolution_plan_"
            )
        )

        self.assertEqual(
            plan["iterations"],
            4,
        )

        self.assertEqual(
            plan["priority"],
            "CRITICAL",
        )

        self.assertTrue(
            plan["requires_approval"]
        )

        self.assertEqual(
            len(plan["steps"]),
            4,
        )

    def test_create_evolution_run(
        self,
    ) -> None:

        run = self.engine.create_run(
            objective=(
                "Rozwinąć system pamięci."
            ),
            mode="SAFE_AUTONOMOUS",
            max_iterations=3,
        )

        self.assertTrue(
            run["evolution_id"].startswith(
                "evolution_"
            )
        )

        self.assertEqual(
            run["status"],
            "CREATED",
        )

        self.assertEqual(
            run["mode"],
            "SAFE_AUTONOMOUS",
        )

        self.assertEqual(
            run["iteration"],
            0,
        )

    def test_safe_autonomous_waits_for_approval(
        self,
    ) -> None:

        result = self.engine.create_and_start(
            objective=(
                "Naprawić problemy projektu."
            ),
            mode=(
                EvolutionMode
                .SAFE_AUTONOMOUS
                .value
            ),
            max_iterations=2,
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

        self.assertIsNotNone(
            result[
                "continuous_cycle_id"
            ]
        )

    def test_autonomous_mode_completes_iteration(
        self,
    ) -> None:

        result = self.engine.create_and_start(
            objective=(
                "Automatycznie popraw projekt."
            ),
            mode=(
                EvolutionMode
                .AUTONOMOUS
                .value
            ),
            max_iterations=1,
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        self.assertEqual(
            result["iteration"],
            1,
        )

        run = self.engine.get_run(
            result["evolution_id"]
        )

        self.assertIn(
            "Zmiana została wykonana poprawnie.",
            run["lessons"],
        )

    def test_approval_completes_safe_run(
        self,
    ) -> None:

        started = self.engine.create_and_start(
            objective=(
                "Popraw testy projektu."
            ),
            mode="SAFE_AUTONOMOUS",
            max_iterations=1,
        )

        result = self.engine.approve(
            evolution_id=started[
                "evolution_id"
            ],
            approved=True,
            note="Akceptuję zmianę.",
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        self.assertEqual(
            result["decision"],
            "STOP",
        )

    def test_rejection_cancels_run(
        self,
    ) -> None:

        started = self.engine.create_and_start(
            objective=(
                "Przygotować ryzykowną zmianę."
            ),
            mode="SAFE_AUTONOMOUS",
            max_iterations=2,
        )

        result = self.engine.approve(
            evolution_id=started[
                "evolution_id"
            ],
            approved=False,
            note="Odrzucam zmianę.",
        )

        self.assertFalse(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "CANCELLED",
        )

    def test_pause_and_resume_run(
        self,
    ) -> None:

        created = self.engine.create_run(
            objective=(
                "Rozwinąć architekturę."
            ),
            mode="AUTONOMOUS",
            max_iterations=2,
        )

        paused = self.engine.pause(
            evolution_id=created[
                "evolution_id"
            ],
            reason="Testowa pauza.",
        )

        self.assertEqual(
            paused["status"],
            "PAUSED",
        )

        resumed = self.engine.resume(
            evolution_id=created[
                "evolution_id"
            ],
        )

        self.assertTrue(
            resumed["success"]
        )

        self.assertIn(
            resumed["status"],
            {
                "LEARNING",
                "COMPLETED",
            },
        )

    def test_engine_saves_and_loads_runs(
        self,
    ) -> None:

        created = self.engine.create_run(
            objective=(
                "Sprawdzić zapis stanu."
            ),
        )

        self.engine.save()

        loaded_engine = EvolutionEngine(
            project_root=self.temp_directory.name,
            continuous_dev_controller=(
                self.fake_continuous
            ),
            storage_path=(
                Path(
                    self.temp_directory.name
                )
                / "evolution_runs.json"
            ),
        )

        loaded = loaded_engine.get_run(
            created["evolution_id"]
        )

        self.assertIsNotNone(
            loaded
        )

        self.assertEqual(
            loaded["objective"],
            "Sprawdzić zapis stanu.",
        )

    def test_evolution_memory_records_run(
        self,
    ) -> None:

        run = {
            "evolution_id": (
                "evolution_memory_test"
            ),
            "objective": (
                "Poprawić pamięć projektu."
            ),
            "mode": "AUTONOMOUS",
            "status": "COMPLETED",
            "decision": "STOP",
            "iteration": 2,
            "max_iterations": 2,
            "continuous_cycle_id": (
                "development_cycle_test"
            ),
            "lessons": [
                "Warto wykonywać małe zmiany."
            ],
            "errors": [],
            "warnings": [],
        }

        self.memory.remember(
            evolution_run=run,
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
            summary["completed_runs"],
            1,
        )

        self.assertIn(
            "Warto wykonywać małe zmiany.",
            summary["recent_lessons"],
        )

    def test_controller_handles_start_command(
        self,
    ) -> None:

        result = self.controller.handle(
            command=(
                "evolution autonomous "
                "popraw jakość projektu"
            )
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "LEARNING",
        )

        self.assertEqual(
            result["mode"],
            "AUTONOMOUS",
        )

    def test_controller_recognizes_commands(
        self,
    ) -> None:

        self.assertTrue(
            self.controller.can_handle(
                "evolution summary"
            )
        )

        self.assertTrue(
            self.controller.can_handle(
                "ewolucja start popraw projekt"
            )
        )

        self.assertFalse(
            self.controller.can_handle(
                "otwórz youtube"
            )
        )

    def test_terminal_run_is_saved_in_memory(
        self,
    ) -> None:

        result = self.controller.create_and_start(
            objective=(
                "Jedna autonomiczna poprawka."
            ),
            mode="AUTONOMOUS",
            max_iterations=1,
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        memory_entry = self.memory.get(
            result["evolution_id"]
        )

        self.assertIsNotNone(
            memory_entry
        )

        self.assertEqual(
            memory_entry["status"],
            "COMPLETED",
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )