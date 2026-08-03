"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.ai.continuous_dev.continuous_dev_controller import (
    ContinuousDevController,
)
from app.ai.continuous_dev.continuous_developer import (
    ContinuousDeveloper,
)
from app.ai.continuous_dev.cycle_memory import (
    CycleMemory,
)
from app.ai.continuous_dev.cycle_state import (
    CycleState,
)
from app.ai.continuous_dev.development_cycle import (
    DevelopmentCycle,
)
from app.ai.continuous_dev.execution_coordinator import (
    ExecutionCoordinator,
)
from app.ai.continuous_dev.improvement_detector import (
    ImprovementDetector,
)
from app.ai.continuous_dev.improvement_planner import (
    ImprovementPlanner,
)
from app.ai.continuous_dev.rollback_coordinator import (
    RollbackCoordinator,
)
from app.ai.continuous_dev.task_queue import (
    TaskQueue,
)
from app.ai.continuous_dev.validation_loop import (
    ValidationLoop,
)


class FakeResearchService:

    def execute(
        self,
        request: str,
    ) -> dict:
        return {
            "success": True,
            "status": "COMPLETED",
            "report": (
                "Przeanalizowano problem "
                "i zależności projektu."
            ),
            "request": request,
        }


class FakeReasoningService:

    def handle(
        self,
        command: str,
        context: dict | None = None,
    ) -> dict:
        return {
            "success": True,
            "status": "COMPLETED",
            "decision": (
                "Wykonać mały bezpieczny patch."
            ),
            "command": command,
            "context": context or {},
        }


class FakeDeveloperController:

    def create_backup(
        self,
        payload: dict,
    ) -> dict:
        return {
            "success": True,
            "status": "COMPLETED",
            "backup_id": "backup_test",
            "files": payload.get(
                "affected_files",
                [],
            ),
        }

    def execute(
        self,
        payload: dict,
    ) -> dict:
        return {
            "success": True,
            "status": "COMPLETED",
            "message": (
                "Patch został wykonany."
            ),
            "payload": payload,
            "syntax_validation": {
                "success": True,
                "status": "PASSED",
            },
            "import_validation": {
                "success": True,
                "status": "PASSED",
            },
            "unit_tests": {
                "success": True,
                "status": "PASSED",
            },
            "integration_tests": {
                "success": True,
                "status": "PASSED",
            },
            "functional_tests": {
                "success": True,
                "status": "PASSED",
            },
        }

    def rollback(
        self,
        payload: dict,
    ) -> dict:
        return {
            "success": True,
            "status": "ROLLED_BACK",
            "restored_files": [
                "app/test_module.py"
            ],
            "payload": payload,
        }


class ContinuousDeveloperTests(
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

        self.task_queue = TaskQueue(
            storage_path=(
                root
                / "task_queue.json"
            )
        )

        self.cycle_memory = CycleMemory(
            storage_path=(
                root
                / "cycle_memory.json"
            )
        )

        self.developer_controller = (
            FakeDeveloperController()
        )

        self.validation_loop = (
            ValidationLoop()
        )

        self.rollback_coordinator = (
            RollbackCoordinator(
                developer_controller=(
                    self.developer_controller
                )
            )
        )

        self.execution_coordinator = (
            ExecutionCoordinator(
                developer_controller=(
                    self.developer_controller
                ),
                validator=(
                    self.validation_loop
                ),
                rollback_coordinator=(
                    self.rollback_coordinator
                ),
            )
        )

        self.continuous_developer = (
            ContinuousDeveloper(
                project_root=(
                    self.temp_directory.name
                ),
                research_service=(
                    FakeResearchService()
                ),
                reasoning_service=(
                    FakeReasoningService()
                ),
                developer_controller=(
                    self.developer_controller
                ),
                task_queue=self.task_queue,
                validation_loop=(
                    self.validation_loop
                ),
                rollback_coordinator=(
                    self.rollback_coordinator
                ),
                execution_coordinator=(
                    self.execution_coordinator
                ),
                cycle_memory=(
                    self.cycle_memory
                ),
            )
        )

        self.controller = (
            ContinuousDevController(
                project_root=(
                    self.temp_directory.name
                ),
                continuous_developer=(
                    self.continuous_developer
                ),
            )
        )

    def tearDown(
        self,
    ) -> None:
        self.temp_directory.cleanup()

    def test_development_cycle_creation(
        self,
    ) -> None:
        cycle = DevelopmentCycle(
            project_root=(
                self.temp_directory.name
            ),
            objective=(
                "Poprawić stabilność projektu."
            ),
        )

        self.assertTrue(
            cycle.cycle_id.startswith(
                "development_cycle_"
            )
        )

        self.assertEqual(
            cycle.status,
            "CREATED",
        )

        cycle.start()

        self.assertEqual(
            cycle.current_stage,
            "ANALYZE",
        )

    def test_cycle_state_tracks_progress(
        self,
    ) -> None:
        state = CycleState(
            cycle_id="cycle_test",
            storage_path=(
                Path(
                    self.temp_directory.name
                )
                / "state.json"
            ),
        )

        state.activate(
            stage="ANALYZE"
        )

        state.set_progress(
            0.5
        )

        self.assertEqual(
            state.status,
            "ACTIVE",
        )

        self.assertEqual(
            state.progress,
            0.5,
        )

        self.assertTrue(
            len(state.snapshots) >= 2
        )

    def test_cycle_memory_records_cycle(
        self,
    ) -> None:
        cycle = {
            "cycle_id": "cycle_memory_test",
            "objective": (
                "Poprawić testy projektu."
            ),
            "project_root": (
                self.temp_directory.name
            ),
            "status": "COMPLETED",
            "result": "SUCCESS",
            "progress": 1.0,
            "iteration": 1,
            "selected_improvement": {
                "improvement_id": (
                    "improvement_test"
                ),
                "title": (
                    "Dodać brakujące testy"
                ),
            },
            "errors": [],
            "warnings": [],
            "lessons": [
                "Testy należy uruchamiać "
                "po każdej zmianie."
            ],
        }

        self.cycle_memory.remember(
            cycle=cycle,
            result={
                "success": True,
                "status": "COMPLETED",
                "result": "SUCCESS",
            },
        )

        summary = (
            self.cycle_memory.summary()
        )

        self.assertEqual(
            summary["entries_count"],
            1,
        )

        self.assertEqual(
            summary[
                "successful_cycles"
            ],
            1,
        )

    def test_task_queue_dependencies(
        self,
    ) -> None:
        first = self.task_queue.add_task(
            cycle_id="cycle_queue",
            title="Analiza",
            task_type="ANALYZE",
            priority="HIGH",
        )

        second = self.task_queue.add_task(
            cycle_id="cycle_queue",
            title="Wykonanie",
            task_type="EXECUTE",
            priority="HIGH",
            dependencies=[
                first["task_id"]
            ],
        )

        next_task = (
            self.task_queue.next_task(
                cycle_id="cycle_queue"
            )
        )

        self.assertEqual(
            next_task["task_id"],
            first["task_id"],
        )

        self.task_queue.start_task(
            first["task_id"]
        )

        self.task_queue.complete_task(
            first["task_id"],
            output_data={
                "success": True
            },
        )

        next_task = (
            self.task_queue.next_task(
                cycle_id="cycle_queue"
            )
        )

        self.assertEqual(
            next_task["task_id"],
            second["task_id"],
        )

    def test_improvement_detector(
        self,
    ) -> None:
        detector = ImprovementDetector()

        result = detector.detect(
            analysis={
                "problems": [
                    {
                        "title": (
                            "Błąd importu modułu"
                        ),
                        "description": (
                            "ImportError powoduje "
                            "awarię aplikacji."
                        ),
                        "severity": "HIGH",
                        "affected_files": [
                            "app/test_module.py"
                        ],
                    }
                ]
            }
        )

        self.assertGreater(
            len(result["candidates"]),
            0,
        )

        candidate = result[
            "candidates"
        ][0]

        self.assertEqual(
            candidate[
                "improvement_type"
            ],
            "BUG_FIX",
        )

        self.assertEqual(
            candidate["severity"],
            "HIGH",
        )

    def test_improvement_planner(
        self,
    ) -> None:
        planner = ImprovementPlanner()

        result = planner.build(
            improvement={
                "improvement_id": (
                    "improvement_plan_test"
                ),
                "title": (
                    "Naprawić błąd importu"
                ),
                "description": (
                    "Usunąć ImportError."
                ),
                "improvement_type": (
                    "BUG_FIX"
                ),
                "severity": "HIGH",
                "affected_files": [
                    "app/test_module.py"
                ],
                "affected_modules": [
                    "test_module"
                ],
                "risks": [
                    "Możliwa regresja."
                ],
            },
            research_context={
                "success": True
            },
            reasoning_context={
                "success": True
            },
        )

        self.assertTrue(
            result["plan_id"].startswith(
                "improvement_plan_"
            )
        )

        self.assertGreater(
            len(result["steps"]),
            5,
        )

        self.assertTrue(
            result["requires_approval"]
        )

    def test_validation_loop_passes(
        self,
    ) -> None:
        result = (
            self.validation_loop.validate(
                cycle_id="cycle_validation",
                execution_result={
                    "success": True,
                    "status": "COMPLETED",
                    "syntax_validation": {
                        "success": True,
                        "status": "PASSED",
                    },
                    "import_validation": {
                        "success": True,
                        "status": "PASSED",
                    },
                    "unit_tests": {
                        "success": True,
                        "status": "PASSED",
                    },
                },
            )
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "PASSED",
        )

    def test_rollback_coordinator(
        self,
    ) -> None:
        result = (
            self.rollback_coordinator.rollback(
                {
                    "cycle_id": (
                        "cycle_rollback"
                    ),
                    "backup": {
                        "success": True,
                        "status": "COMPLETED",
                        "backup_id": "backup_test",
                    },
                    "execution": {
                        "success": False,
                        "status": "FAILED",
                    },
                    "validation": {
                        "success": False,
                        "status": "FAILED",
                    },
                    "context": {},
                }
            )
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

    def test_execution_coordinator(
        self,
    ) -> None:
        plan = {
            "plan_id": "plan_execution",
            "improvement_id": (
                "improvement_execution"
            ),
            "objective": (
                "Naprawić błąd testowy."
            ),
            "strategy": (
                "SAFE_INCREMENTAL_CHANGE"
            ),
            "requires_approval": True,
            "execution_order": [],
            "steps": [],
            "metadata": {
                "affected_files": [
                    "app/test_module.py"
                ]
            },
        }

        result = (
            self.execution_coordinator.coordinate(
                cycle_id="cycle_execution",
                plan=plan,
                approved=True,
            )
        )

        self.assertTrue(
            result["status"]
            in {
                "COMPLETED",
                "ROLLED_BACK",
            }
        )

        self.assertIn(
            "execution",
            result,
        )

        self.assertIn(
            "validation",
            result,
        )

    def test_continuous_developer_waits_for_approval(
        self,
    ) -> None:
        created = (
            self.continuous_developer.create_cycle(
                objective=(
                    "Naprawić krytyczny błąd importu."
                )
            )
        )

        result = (
            self.continuous_developer.start_cycle(
                cycle_id=created[
                    "cycle_id"
                ],
                auto_approve=False,
                context={
                    "problems": [
                        {
                            "title": (
                                "Krytyczny błąd importu"
                            ),
                            "description": (
                                "ImportError powoduje "
                                "awarię systemu."
                            ),
                            "severity": "CRITICAL",
                            "affected_files": [
                                "app/test_module.py"
                            ],
                            "affected_modules": [
                                "test_module"
                            ],
                        }
                    ]
                },
            )
        )

        self.assertEqual(
            result["status"],
            "WAITING_FOR_APPROVAL",
        )

    def test_continuous_developer_full_cycle(
        self,
    ) -> None:
        result = (
            self.controller.create_and_start(
                objective=(
                    "Naprawić błąd importu "
                    "w module testowym."
                ),
                auto_approve=True,
                context={
                    "problems": [
                        {
                            "title": (
                                "Błąd importu"
                            ),
                            "description": (
                                "ImportError powoduje "
                                "awarię aplikacji."
                            ),
                            "severity": "HIGH",
                            "affected_files": [
                                "app/test_module.py"
                            ],
                            "affected_modules": [
                                "test_module"
                            ],
                        }
                    ]
                },
            )
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

        self.assertIn(
            "coordination",
            result,
        )

        memory_summary = (
            self.cycle_memory.summary()
        )

        self.assertGreaterEqual(
            memory_summary[
                "entries_count"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
