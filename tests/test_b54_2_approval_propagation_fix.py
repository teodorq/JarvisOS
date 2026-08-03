from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomous_campaign_director import (
    AutonomousCampaignDirector,
)
from app.ai.software_engineer.full_autonomy_store import (
    FullAutonomyStore,
)
from app.ai.software_engineer.full_autonomy_workflow import (
    FullAutonomyWorkflow,
)
from app.ai.software_engineer.multi_campaign_models import (
    ManagedCampaign,
    MultiCampaignPortfolio,
)
from app.ai.software_engineer.multi_campaign_workflow import (
    MultiCampaignWorkflow,
)
from tools.repair_b54_2_approval_propagation import repair


class B542ApprovalPropagationFixTests(unittest.TestCase):

    def test_director_recovers_preview_campaign_as_paused(
        self,
    ) -> None:
        item = ManagedCampaign(
            campaign_id="campaign-preview",
            objective="goal",
            stages=[],
            targets=[],
            status="RUNNING",
            result={
                "campaign": {
                    "status": "CAMPAIGN_PREVIEW_READY",
                },
            },
        )
        portfolio = self.portfolio(item)

        recovered = (
            AutonomousCampaignDirector
            ._recover_interrupted_campaigns(
                portfolio
            )
        )

        self.assertEqual(
            recovered,
            ["campaign-preview"],
        )
        self.assertEqual(item.status, "PAUSED")
        self.assertEqual(
            portfolio.current_campaign_id,
            "",
        )

    def test_director_recovers_other_running_campaign_as_pending(
        self,
    ) -> None:
        item = ManagedCampaign(
            campaign_id="campaign-running",
            objective="goal",
            stages=[],
            targets=[],
            status="RUNNING",
            result={},
        )
        portfolio = self.portfolio(item)

        AutonomousCampaignDirector._recover_interrupted_campaigns(
            portfolio
        )

        self.assertEqual(item.status, "PENDING")

    def test_runtime_approval_overrides_persisted_false(
        self,
    ) -> None:
        campaign_workflow = MagicMock()
        campaign_workflow.get_campaign.return_value = {
            "campaign_id": "campaign-one",
        }
        campaign_workflow.resume.return_value = {
            "success": True,
            "status": "CAMPAIGN_COMPLETED",
        }
        workflow = MultiCampaignWorkflow.__new__(
            MultiCampaignWorkflow
        )
        workflow.campaign_workflow = campaign_workflow
        item = self.managed(
            options={"auto_approve": False}
        )

        workflow._run_campaign(
            item,
            auto_approve=True,
            auto_rollback=True,
            final_validation=True,
        )

        self.assertTrue(
            campaign_workflow.resume.call_args.kwargs[
                "auto_approve"
            ]
        )
        self.assertFalse(
            item.metadata["options"]["auto_approve"]
        )

    def test_stored_approval_still_works_without_runtime_override(
        self,
    ) -> None:
        campaign_workflow = MagicMock()
        campaign_workflow.get_campaign.return_value = None
        campaign_workflow.run.return_value = {
            "success": True,
            "status": "CAMPAIGN_COMPLETED",
        }
        workflow = MultiCampaignWorkflow.__new__(
            MultiCampaignWorkflow
        )
        workflow.campaign_workflow = campaign_workflow
        item = self.managed(
            options={"auto_approve": True}
        )

        workflow._run_campaign(
            item,
            auto_approve=False,
            auto_rollback=True,
            final_validation=True,
        )

        self.assertTrue(
            campaign_workflow.run.call_args.kwargs[
                "auto_approve"
            ]
        )

    def test_one_time_approval_reaches_director_but_is_not_persisted(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            store = FullAutonomyStore(root)
            store.save({
                "run_id": "autonomy-one",
                "objective": "goal",
                "status": "FULL_AUTONOMY_PAUSED",
                "success": True,
                "portfolio_id": "portfolio-one",
                "policy": {
                    "auto_execute": True,
                    "auto_approve": False,
                    "auto_rollback": True,
                    "final_validation": True,
                },
                "events": [],
                "errors": [],
                "portfolio": {},
                "plan": {},
            })
            director = MagicMock()
            director.direct.return_value = {
                "success": True,
                "status": (
                    "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS"
                ),
                "portfolio": {},
                "director_run": {},
                "errors": [],
            }
            learning = MagicMock()
            learning.store.get_profile.return_value = {
                "active": False,
            }
            workflow = FullAutonomyWorkflow(
                root,
                planner=MagicMock(),
                portfolio_workflow=MagicMock(),
                optimizer=MagicMock(),
                director=director,
                validator=MagicMock(),
                store=store,
                learning_engine=learning,
            )
            workflow._update_execution = MagicMock()

            result = workflow.resume(
                "autonomy-one",
                context={
                    "auto_approve": True,
                    "_b54_one_time_auto_approve": True,
                    "_b54_repair_id": "repair-one",
                },
            )

            self.assertEqual(
                result["status"],
                "FULL_AUTONOMY_PAUSED",
            )
            self.assertTrue(
                director.direct.call_args.kwargs[
                    "auto_approve"
                ]
            )
            saved = store.get("autonomy-one")
            self.assertFalse(
                saved["policy"]["auto_approve"]
            )
            self.assertTrue(
                any(
                    event.get("event")
                    == "AUTONOMY_ONE_TIME_APPROVAL_FORWARDED"
                    for event in saved["events"]
                )
            )

    def test_regular_approval_can_still_be_persisted(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            store = FullAutonomyStore(root)
            store.save({
                "run_id": "autonomy-regular",
                "objective": "goal",
                "status": "FULL_AUTONOMY_PAUSED",
                "success": True,
                "portfolio_id": "portfolio-one",
                "policy": {
                    "auto_execute": True,
                    "auto_approve": False,
                },
                "events": [],
                "errors": [],
            })
            director = MagicMock()
            director.direct.return_value = {
                "success": True,
                "status": (
                    "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS"
                ),
                "portfolio": {},
                "director_run": {},
                "errors": [],
            }
            learning = MagicMock()
            learning.store.get_profile.return_value = {
                "active": False,
            }
            workflow = FullAutonomyWorkflow(
                root,
                planner=MagicMock(),
                portfolio_workflow=MagicMock(),
                optimizer=MagicMock(),
                director=director,
                validator=MagicMock(),
                store=store,
                learning_engine=learning,
            )
            workflow._update_execution = MagicMock()

            workflow.resume(
                "autonomy-regular",
                context={"auto_approve": True},
            )

            self.assertTrue(
                store.get("autonomy-regular")[
                    "policy"
                ]["auto_approve"]
            )

    def test_repair_rearms_only_consumed_waiting_approval(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data" / "autodev"
            data.mkdir(parents=True)
            queue = {
                "version": 1,
                "jobs": {
                    "longrun-one": {
                        "job_id": "longrun-one",
                        "state": "WAITING_APPROVAL",
                        "attempts": 1,
                        "autonomy_run_id": "autonomy-one",
                        "execution_context": {
                            "auto_approve": False,
                        },
                        "metadata": {
                            "b54_last_repair_id": "repair-one",
                            "b54_last_repair_type": (
                                "ONE_TIME_APPROVAL"
                            ),
                            "b54_repair_approval_consumed": True,
                            "b54_repair_approval_consumed_id": (
                                "repair-one"
                            ),
                        },
                    },
                    "longrun-other": {
                        "job_id": "longrun-other",
                        "state": "WAITING_APPROVAL",
                        "execution_context": {},
                        "metadata": {},
                    },
                },
                "order": [
                    "longrun-one",
                    "longrun-other",
                ],
                "events": [],
                "runtime": {},
                "policy": {
                    "auto_approve": False,
                },
            }
            runs = {
                "version": 1,
                "runs": {
                    "autonomy-one": {
                        "run_id": "autonomy-one",
                        "policy": {
                            "auto_approve": True,
                        },
                    },
                },
                "order": ["autonomy-one"],
            }
            (data / "long_running_autonomy.json").write_text(
                json.dumps(queue),
                encoding="utf-8",
            )
            (data / "full_autonomy_runs.json").write_text(
                json.dumps(runs),
                encoding="utf-8",
            )

            result = repair(root)

            saved_queue = json.loads(
                (
                    data
                    / "long_running_autonomy.json"
                ).read_text(encoding="utf-8")
            )
            saved_runs = json.loads(
                (
                    data
                    / "full_autonomy_runs.json"
                ).read_text(encoding="utf-8")
            )
            repaired = saved_queue["jobs"][
                "longrun-one"
            ]
            untouched = saved_queue["jobs"][
                "longrun-other"
            ]

            self.assertEqual(result["rearmed"], 1)
            self.assertEqual(
                repaired["state"],
                "QUEUED",
            )
            self.assertEqual(repaired["attempts"], 0)
            self.assertTrue(
                repaired["execution_context"][
                    "_b54_one_time_auto_approve"
                ]
            )
            self.assertEqual(
                untouched["state"],
                "WAITING_APPROVAL",
            )
            self.assertFalse(
                saved_runs["runs"]["autonomy-one"][
                    "policy"
                ]["auto_approve"]
            )

    @staticmethod
    def managed(
        *,
        options: dict,
    ) -> ManagedCampaign:
        return ManagedCampaign(
            campaign_id="campaign-one",
            objective="goal",
            stages=[],
            targets=[],
            metadata={
                "options": dict(options),
            },
        )

    @staticmethod
    def portfolio(
        item: ManagedCampaign,
    ) -> MultiCampaignPortfolio:
        return MultiCampaignPortfolio(
            portfolio_id="portfolio-one",
            objective="goal",
            campaigns=[item],
            execution_order=[item.campaign_id],
            fingerprint="fingerprint",
            status="MULTI_CAMPAIGN_RUNNING",
            current_campaign_id=item.campaign_id,
        )


if __name__ == "__main__":
    unittest.main()
