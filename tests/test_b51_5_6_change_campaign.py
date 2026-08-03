"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.brain_response_formatter import (
    BrainResponseFormatter,
)
from app.ai.software_engineer.change_campaign_models import (
    ChangeCampaign,
)
from app.ai.software_engineer.change_campaign_planner import (
    ChangeCampaignPlanner,
)
from app.ai.software_engineer.change_campaign_snapshot import (
    ChangeCampaignSnapshotManager,
)
from app.ai.software_engineer.change_campaign_store import (
    ChangeCampaignStore,
)
from app.ai.software_engineer.change_campaign_workflow import (
    ChangeCampaignWorkflow,
)
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_campaign_router import (
    SoftwareEngineerCampaignRouter,
)
from app.autodev.execution_result import (
    ExecutionResult,
)


class ApplyingCrossModuleWorkflow:

    def __init__(
        self,
        project_root: Path,
        *,
        fail_on_call: int | None = None,
        raise_on_call: int | None = None,
    ) -> None:
        self.project_root = project_root
        self.fail_on_call = fail_on_call
        self.raise_on_call = raise_on_call
        self.calls: list[dict] = []

    def run(
        self,
        objective: str,
        *,
        replacements=None,
        targets=None,
        **kwargs,
    ) -> dict:
        self.calls.append(
            {
                "objective": objective,
                "replacements": dict(
                    replacements or {}
                ),
                "targets": list(
                    targets or []
                ),
                "kwargs": dict(kwargs),
            }
        )
        call_number = len(
            self.calls
        )

        if self.raise_on_call == call_number:
            raise RuntimeError(
                "symulowane przerwanie"
            )

        for relative, content in dict(
            replacements or {}
        ).items():
            target = (
                self.project_root
                / relative
            )
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            target.write_text(
                content,
                encoding="utf-8",
            )

        if self.fail_on_call == call_number:
            return {
                "success": False,
                "status": (
                    "CROSS_MODULE_STAGE_FAILED"
                ),
                "errors": [
                    "symulowana awaria etapu",
                ],
            }

        return {
            "success": True,
            "status": (
                "CROSS_MODULE_COMPLETED"
            ),
            "errors": [],
            "verification": {
                "success": True,
                "status": "VERIFIED",
            },
        }


class ValidatorStub:

    def __init__(
        self,
        success: bool = True,
    ) -> None:
        self.success = success
        self.calls: list[dict] = []

    def run_test_suite(
        self,
        *,
        changed_files,
        full_suite,
    ):
        self.calls.append(
            {
                "changed_files": list(
                    changed_files
                ),
                "full_suite": full_suite,
            }
        )

        return ExecutionResult(
            success=self.success,
            step_name="run_test_suite",
            message=(
                "OK"
                if self.success
                else "FAIL"
            ),
            errors=(
                []
                if self.success
                else [
                    "test failure",
                ]
            ),
        )


class B5156ChangeCampaignTests(
    unittest.TestCase
):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp.name
        )
        self.originals = {
            "app/ai/alpha.py": "ALPHA = 1\n",
            "app/autodev/beta.py": "BETA = 1\n",
            "app/gui/gamma.py": "GAMMA = 1\n",
            "app/core/delta.py": "DELTA = 1\n",
        }

        for relative, content in self.originals.items():
            target = self.root / relative
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            target.write_text(
                content,
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def stages(self) -> list[dict]:
        return [
            {
                "stage_id": "core-change",
                "objective": (
                    "Zmień warstwę AI i AutoDev"
                ),
                "replacements": {
                    "app/ai/alpha.py": (
                        "ALPHA = 2\n"
                    ),
                    "app/autodev/beta.py": (
                        "BETA = 2\n"
                    ),
                },
            },
            {
                "stage_id": "ui-integration",
                "objective": (
                    "Połącz GUI z nowym API"
                ),
                "depends_on": [
                    "core-change",
                ],
                "replacements": {
                    "app/gui/gamma.py": (
                        "GAMMA = 2\n"
                    ),
                    "app/core/delta.py": (
                        "DELTA = 2\n"
                    ),
                },
            },
        ]

    def workflow(
        self,
        *,
        cross=None,
        validator=None,
    ) -> ChangeCampaignWorkflow:
        return ChangeCampaignWorkflow(
            project_root=self.root,
            cross_module_workflow=(
                cross
                or ApplyingCrossModuleWorkflow(
                    self.root
                )
            ),
            validator=(
                validator
                or ValidatorStub()
            ),
        )

    def test_planner_orders_stages_by_dependencies(
        self,
    ) -> None:
        stages = list(
            reversed(
                self.stages()
            )
        )
        campaign = ChangeCampaignPlanner(
            self.root
        ).plan(
            "Duża zmiana systemowa",
            stages,
            campaign_id="campaign-order",
        )

        self.assertEqual(
            campaign.execution_order,
            [
                "core-change",
                "ui-integration",
            ],
        )
        self.assertEqual(
            campaign.metadata[
                "stage_count"
            ],
            2,
        )
        self.assertGreater(
            campaign.metadata[
                "estimated_risk"
            ],
            0,
        )

    def test_planner_rejects_dependency_cycle(
        self,
    ) -> None:
        stages = self.stages()
        stages[0][
            "depends_on"
        ] = [
            "ui-integration",
        ]

        with self.assertRaises(
            ValueError
        ):
            ChangeCampaignPlanner(
                self.root
            ).plan(
                "Cykl",
                stages,
            )

    def test_planner_rejects_duplicate_stage_ids(
        self,
    ) -> None:
        stages = self.stages()
        stages[1][
            "stage_id"
        ] = "core-change"

        with self.assertRaises(
            ValueError
        ):
            ChangeCampaignPlanner(
                self.root
            ).plan(
                "Duplikat",
                stages,
            )

    def test_snapshot_restores_existing_and_removes_new_file(
        self,
    ) -> None:
        new_path = (
            self.root
            / "app/gui/new_file.py"
        )
        manager = (
            ChangeCampaignSnapshotManager(
                self.root
            )
        )
        manager.create(
            "campaign-snapshot",
            [
                "app/ai/alpha.py",
                "app/gui/new_file.py",
            ],
        )
        (
            self.root
            / "app/ai/alpha.py"
        ).write_text(
            "ALPHA = 99\n",
            encoding="utf-8",
        )
        new_path.write_text(
            "NEW = True\n",
            encoding="utf-8",
        )

        result = manager.restore(
            "campaign-snapshot"
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            (
                self.root
                / "app/ai/alpha.py"
            ).read_text(
                encoding="utf-8",
            ),
            "ALPHA = 1\n",
        )
        self.assertFalse(
            new_path.exists()
        )

    def test_tampered_snapshot_is_rejected_before_restore(
        self,
    ) -> None:
        manager = (
            ChangeCampaignSnapshotManager(
                self.root
            )
        )
        manifest = manager.create(
            "campaign-tamper",
            [
                "app/ai/alpha.py",
                "app/autodev/beta.py",
            ],
        )
        entry = next(
            item
            for item in manifest[
                "entries"
            ]
            if item["existed"]
        )
        backup = (
            Path(
                manager.snapshot_path(
                    "campaign-tamper"
                )
            )
            / entry["backup_file"]
        )
        backup.write_bytes(
            b"tampered"
        )
        (
            self.root
            / "app/ai/alpha.py"
        ).write_text(
            "ALPHA = 99\n",
            encoding="utf-8",
        )

        result = manager.restore(
            "campaign-tamper"
        )

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            (
                self.root
                / "app/ai/alpha.py"
            ).read_text(
                encoding="utf-8",
            ),
            "ALPHA = 99\n",
        )

    def test_plan_only_is_persisted_without_writes(
        self,
    ) -> None:
        workflow = self.workflow()

        result = workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-plan",
            auto_execute=False,
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "CAMPAIGN_PLAN_READY",
        )
        self.assertEqual(
            (
                self.root
                / "app/ai/alpha.py"
            ).read_text(
                encoding="utf-8",
            ),
            "ALPHA = 1\n",
        )
        stored = workflow.get_campaign(
            "campaign-plan"
        )
        self.assertIsNotNone(
            stored
        )
        self.assertEqual(
            stored["status"],
            "CAMPAIGN_PLAN_READY",
        )

    def test_full_campaign_executes_validates_and_retains_snapshot(
        self,
    ) -> None:
        cross = ApplyingCrossModuleWorkflow(
            self.root
        )
        validator = ValidatorStub()
        workflow = self.workflow(
            cross=cross,
            validator=validator,
        )

        result = workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-complete",
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "CAMPAIGN_COMPLETED",
        )
        self.assertEqual(
            result["completed_stages"],
            2,
        )
        self.assertEqual(
            len(cross.calls),
            2,
        )
        self.assertEqual(
            len(validator.calls),
            1,
        )
        self.assertTrue(
            workflow.snapshot_manager.exists(
                "campaign-complete"
            )
        )
        self.assertEqual(
            (
                self.root
                / "app/core/delta.py"
            ).read_text(
                encoding="utf-8",
            ),
            "DELTA = 2\n",
        )

    def test_invalid_stage_limit_returns_safe_error(
        self,
    ) -> None:
        workflow = self.workflow()

        result = workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-invalid-limit",
            max_stages_per_run=0,
        )

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "CAMPAIGN_POLICY_INVALID",
        )
        self.assertTrue(
            result["errors"]
        )

    def test_completed_campaign_can_be_manually_rolled_back(
        self,
    ) -> None:
        workflow = self.workflow()
        completed = workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-manual-rollback",
        )

        self.assertEqual(
            completed["status"],
            "CAMPAIGN_COMPLETED",
        )
        rolled_back = workflow.rollback(
            "campaign-manual-rollback"
        )

        self.assertTrue(
            rolled_back["success"]
        )
        self.assertEqual(
            rolled_back["status"],
            "CAMPAIGN_ROLLED_BACK",
        )
        self.assertFalse(
            workflow.snapshot_manager.exists(
                "campaign-manual-rollback"
            )
        )

        for relative, content in self.originals.items():
            self.assertEqual(
                (
                    self.root
                    / relative
                ).read_text(
                    encoding="utf-8",
                ),
                content,
            )

    def test_campaign_pauses_and_resumes_from_checkpoint(
        self,
    ) -> None:
        cross = ApplyingCrossModuleWorkflow(
            self.root
        )
        workflow = self.workflow(
            cross=cross
        )

        paused = workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-resume",
            max_stages_per_run=1,
        )

        self.assertEqual(
            paused["status"],
            "CAMPAIGN_PAUSED",
        )
        self.assertEqual(
            paused["completed_stages"],
            1,
        )
        self.assertTrue(
            workflow.snapshot_manager.exists(
                "campaign-resume"
            )
        )

        completed = workflow.resume(
            "campaign-resume"
        )

        self.assertEqual(
            completed["status"],
            "CAMPAIGN_COMPLETED",
        )
        self.assertEqual(
            completed["completed_stages"],
            2,
        )
        self.assertEqual(
            len(cross.calls),
            2,
        )
        events = [
            item["event"]
            for item in completed[
                "campaign"
            ]["checkpoints"]
        ]
        self.assertIn(
            "CAMPAIGN_RESUMED",
            events,
        )

    def test_running_stage_is_recovered_after_interruption(
        self,
    ) -> None:
        workflow = self.workflow()
        planned = workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-interrupted",
            auto_execute=False,
        )
        campaign = workflow.store.get(
            "campaign-interrupted"
        )
        campaign.stage(
            "core-change"
        ).status = "RUNNING"
        workflow.store.save(
            campaign
        )

        result = workflow.resume(
            "campaign-interrupted"
        )

        self.assertEqual(
            result["status"],
            "CAMPAIGN_COMPLETED",
        )
        self.assertTrue(
            any(
                "Odzyskano kampanię"
                in warning
                for warning in result[
                    "campaign"
                ]["warnings"]
            )
        )

    def test_stage_failure_rolls_back_every_completed_stage(
        self,
    ) -> None:
        cross = ApplyingCrossModuleWorkflow(
            self.root,
            fail_on_call=2,
        )
        workflow = self.workflow(
            cross=cross
        )

        result = workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-stage-fail",
        )

        self.assertEqual(
            result["status"],
            "CAMPAIGN_FAILED_AND_ROLLED_BACK",
        )
        self.assertTrue(
            result["rollback"]["success"]
        )

        for relative, content in self.originals.items():
            self.assertEqual(
                (
                    self.root
                    / relative
                ).read_text(
                    encoding="utf-8",
                ),
                content,
            )

    def test_final_validation_failure_rolls_back_entire_campaign(
        self,
    ) -> None:
        workflow = self.workflow(
            validator=ValidatorStub(
                success=False
            )
        )

        result = workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-validation-fail",
        )

        self.assertEqual(
            result["status"],
            (
                "CAMPAIGN_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK"
            ),
        )
        self.assertTrue(
            result["rollback"]["success"]
        )

        for relative, content in self.originals.items():
            self.assertEqual(
                (
                    self.root
                    / relative
                ).read_text(
                    encoding="utf-8",
                ),
                content,
            )

    def test_completed_campaign_resume_is_idempotent(
        self,
    ) -> None:
        cross = ApplyingCrossModuleWorkflow(
            self.root
        )
        workflow = self.workflow(
            cross=cross
        )
        workflow.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-idempotent",
        )

        result = workflow.resume(
            "campaign-idempotent"
        )

        self.assertEqual(
            result["status"],
            "CAMPAIGN_COMPLETED",
        )
        self.assertEqual(
            len(cross.calls),
            2,
        )

    def test_store_is_atomic_bounded_and_returns_recent(
        self,
    ) -> None:
        store = ChangeCampaignStore(
            self.root,
            max_records=10,
        )
        planner = ChangeCampaignPlanner(
            self.root
        )

        for index in range(12):
            campaign = planner.plan(
                f"Kampania {index}",
                self.stages(),
                campaign_id=(
                    f"campaign-{index}"
                ),
            )
            store.save(campaign)

        recent = store.list_recent(
            limit=20
        )

        self.assertEqual(
            len(recent),
            10,
        )
        self.assertEqual(
            recent[0][
                "campaign_id"
            ],
            "campaign-11",
        )
        self.assertIsNone(
            store.get(
                "campaign-0"
            )
        )

    def test_campaign_resumes_after_new_process_instance(
        self,
    ) -> None:
        first_cross = ApplyingCrossModuleWorkflow(
            self.root
        )
        first = self.workflow(
            cross=first_cross
        )
        paused = first.run(
            "Duża zmiana",
            stages=self.stages(),
            campaign_id="campaign-restart",
            max_stages_per_run=1,
        )

        self.assertEqual(
            paused["status"],
            "CAMPAIGN_PAUSED",
        )

        second_cross = ApplyingCrossModuleWorkflow(
            self.root
        )
        second = self.workflow(
            cross=second_cross
        )
        completed = second.resume(
            "campaign-restart"
        )

        self.assertEqual(
            completed["status"],
            "CAMPAIGN_COMPLETED",
        )
        self.assertEqual(
            len(first_cross.calls),
            1,
        )
        self.assertEqual(
            len(second_cross.calls),
            1,
        )

    def test_controller_handle_routes_campaign_workflow(
        self,
    ) -> None:
        controller = (
            AutonomousSoftwareEngineerController
            .__new__(
                AutonomousSoftwareEngineerController
            )
        )
        controller.project_root = self.root
        controller.cross_module_workflow = MagicMock()
        controller.change_campaign_workflow = MagicMock()
        controller.change_campaign_workflow.run.return_value = {
            "success": True,
            "status": "CAMPAIGN_PLAN_READY",
            "campaign_id": "campaign-controller",
            "campaign": {
                "campaign_id": "campaign-controller",
            },
        }

        result = controller.handle(
            "Uruchom kampanię zmian autonomicznie",
            context={
                "operation": "change_campaign",
                "campaign_id": "campaign-controller",
                "campaign_stages": self.stages(),
                "auto_execute": False,
            },
        )

        self.assertEqual(
            result["status"],
            "CAMPAIGN_PLAN_READY",
        )
        controller.change_campaign_workflow.run.assert_called_once()

    def test_router_routes_campaign_start_and_resume(
        self,
    ) -> None:
        workflow = MagicMock()
        workflow.run.return_value = {
            "success": True,
            "status": "CAMPAIGN_PAUSED",
            "campaign_id": "campaign-router",
            "campaign": {
                "campaign_id": "campaign-router",
            },
        }
        workflow.resume.return_value = {
            "success": True,
            "status": "CAMPAIGN_COMPLETED",
            "campaign_id": "campaign-router",
            "campaign": {
                "campaign_id": "campaign-router",
            },
        }
        controller = SimpleNamespace(
            project_root=self.root,
            cross_module_workflow=MagicMock(),
            change_campaign_workflow=workflow,
            _normalize=lambda value: str(
                value
            ).casefold(),
        )
        router = SoftwareEngineerCampaignRouter()

        started = router.try_handle(
            controller,
            command="Uruchom kampanię zmian",
            objective="Duża zmiana",
            context={
                "operation": "change_campaign",
                "campaign_id": "campaign-router",
                "campaign_stages": self.stages(),
            },
        )
        resumed = router.try_handle(
            controller,
            command="Wznów kampanię",
            objective="Duża zmiana",
            context={
                "operation": "change_campaign",
                "campaign_action": "resume",
                "campaign_id": "campaign-router",
            },
        )

        self.assertEqual(
            started["status"],
            "CAMPAIGN_PAUSED",
        )
        self.assertEqual(
            resumed["status"],
            "CAMPAIGN_COMPLETED",
        )
        workflow.run.assert_called_once()
        workflow.resume.assert_called_once()

    def test_formatter_reports_campaign_checkpoint_and_progress(
        self,
    ) -> None:
        formatter = BrainResponseFormatter()
        text = (
            formatter
            ._format_software_engineer_response(
                {
                    "success": True,
                    "status": "CAMPAIGN_PAUSED",
                    "campaign_id": "campaign-1",
                    "stages_count": 3,
                    "completed_stages": 1,
                    "campaign": {
                        "campaign_id": "campaign-1",
                        "current_stage_id": "",
                        "stages": [
                            {},
                            {},
                            {},
                        ],
                        "completed_stage_ids": [
                            "stage-1",
                        ],
                        "checkpoints": [
                            {
                                "event": (
                                    "CAMPAIGN_PAUSED"
                                ),
                            }
                        ],
                    },
                    "report_path": (
                        "data/autodev/"
                        "change_campaigns.json"
                    ),
                }
            )
        )

        self.assertIn(
            "Kampania zmian: campaign-1",
            text,
        )
        self.assertIn(
            "Postęp etapów: 1/3",
            text,
        )
        self.assertIn(
            "Ostatni checkpoint: CAMPAIGN_PAUSED",
            text,
        )

    def test_controller_and_router_remain_below_audit_limits(
        self,
    ) -> None:
        project_root = Path(
            __file__
        ).resolve().parents[1]
        controller_lines = len(
            (
                project_root
                / "app/ai/software_engineer/"
                "autonomous_software_engineer.py"
            ).read_text(
                encoding="utf-8",
            ).splitlines()
        )
        advanced_router_lines = len(
            (
                project_root
                / "app/ai/software_engineer/"
                "software_engineer_advanced_change_router.py"
            ).read_text(
                encoding="utf-8",
            ).splitlines()
        )

        self.assertLess(
            controller_lines,
            440,
        )
        self.assertLess(
            advanced_router_lines,
            360,
        )


if __name__ == "__main__":
    unittest.main()
