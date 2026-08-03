from __future__ import annotations

from typing import Any

from .change_campaign_workflow import (
    ChangeCampaignWorkflow,
)
from .software_engineer_full_autonomy_router import (
    SoftwareEngineerFullAutonomyRouter,
)
from .software_engineer_portfolio_router import (
    SoftwareEngineerPortfolioRouter,
)


_FULL_AUTONOMY_ROUTER = SoftwareEngineerFullAutonomyRouter()
_PORTFOLIO_ROUTER = SoftwareEngineerPortfolioRouter()


class SoftwareEngineerCampaignRouter:
    """Routes create, resume, inspect and rollback campaign commands."""

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        autonomy = _FULL_AUTONOMY_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )

        if autonomy is not None:
            return autonomy

        portfolio = _PORTFOLIO_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )

        if portfolio is not None:
            return portfolio

        if not self._is_campaign(
            controller,
            command=command,
            context=context,
        ):
            return None

        workflow = getattr(
            controller,
            "change_campaign_workflow",
            None,
        )

        if workflow is None:
            workflow = ChangeCampaignWorkflow(
                project_root=(
                    controller.project_root
                ),
                cross_module_workflow=(
                    controller.cross_module_workflow
                ),
            )
            controller.change_campaign_workflow = (
                workflow
            )

        action = self._action(
            controller,
            command=command,
            context=context,
        )
        campaign_id = str(
            context.get(
                "campaign_id",
                "",
            )
        ).strip()

        if action == "recent":
            campaigns = (
                workflow.recent_campaigns(
                    limit=max(
                        1,
                        int(
                            context.get(
                                "limit",
                                20,
                            )
                        ),
                    )
                )
            )
            return {
                "success": True,
                "status": (
                    "CAMPAIGN_RECENT"
                ),
                "operation": (
                    "change_campaign"
                ),
                "campaign_id": "",
                "campaign": {},
                "campaigns": campaigns,
                "stages_count": 0,
                "completed_stages": 0,
                "errors": [],
            }

        if action == "status":
            if not campaign_id:
                return self._id_required()

            campaign = workflow.get_campaign(
                campaign_id
            )

            if campaign is None:
                return {
                    "success": False,
                    "status": (
                        "CAMPAIGN_NOT_FOUND"
                    ),
                    "campaign_id": (
                        campaign_id
                    ),
                    "campaign": {},
                    "errors": [
                        "Nie znaleziono kampanii."
                    ],
                }

            return {
                "success": True,
                "status": (
                    str(
                        campaign.get(
                            "status",
                            "UNKNOWN",
                        )
                    )
                ),
                "operation": (
                    "change_campaign"
                ),
                "campaign_id": campaign_id,
                "campaign": campaign,
                "stages_count": len(
                    campaign.get(
                        "stages",
                        [],
                    )
                ),
                "completed_stages": len(
                    campaign.get(
                        "completed_stage_ids",
                        [],
                    )
                ),
                "errors": [],
                "report_path": str(
                    workflow.store.path
                ),
            }

        if action == "resume":
            if not campaign_id:
                return self._id_required()

            return workflow.resume(
                campaign_id,
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
                final_validation=bool(
                    context.get(
                        "final_validation",
                        True,
                    )
                ),
                max_stages_per_run=(
                    context.get(
                        "max_stages_per_run"
                    )
                ),
            )

        if action == "rollback":
            if not campaign_id:
                return self._id_required()

            return workflow.rollback(
                campaign_id
            )

        stages = context.get(
            "campaign_stages",
            context.get(
                "stages",
                [],
            ),
        )

        if not isinstance(
            stages,
            list,
        ) or len(stages) < 2:
            return {
                "success": False,
                "status": (
                    "CAMPAIGN_STAGES_REQUIRED"
                ),
                "campaign_id": (
                    campaign_id
                ),
                "campaign": {},
                "errors": [
                    "Podaj co najmniej dwa etapy "
                    "w context['campaign_stages']."
                ],
            }

        return workflow.run(
            objective,
            stages=stages,
            campaign_id=(
                campaign_id
                or None
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
            final_validation=bool(
                context.get(
                    "final_validation",
                    True,
                )
            ),
            max_stages_per_run=(
                context.get(
                    "max_stages_per_run"
                )
            ),
            metadata=dict(
                context.get(
                    "campaign_metadata",
                    {},
                )
                or {}
            ),
        )

    @staticmethod
    def _is_campaign(
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> bool:
        operation = str(
            context.get(
                "operation",
                context.get(
                    "mode",
                    "",
                ),
            )
        ).strip().casefold()

        if (
            context.get(
                "change_campaign"
            ) is True
            or operation in {
                "campaign",
                "change_campaign",
                "multi_stage_campaign",
                "cross_module_campaign",
            }
        ):
            return True

        normalized = controller._normalize(
            command
        )

        return any(
            phrase in normalized
            for phrase in (
                "kampania zmian",
                "wieloetapowa kampania",
                "wznów kampanię",
                "wznow kampanie",
                "change campaign",
                "resume campaign",
                "multi stage change",
            )
        )

    @staticmethod
    def _action(
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> str:
        explicit = str(
            context.get(
                "campaign_action",
                context.get(
                    "action",
                    "",
                ),
            )
        ).strip().casefold()

        mapping = {
            "list": "recent",
            "recent": "recent",
            "status": "status",
            "get": "status",
            "resume": "resume",
            "wznów": "resume",
            "wznow": "resume",
            "rollback": "rollback",
            "cofnij": "rollback",
            "start": "start",
            "run": "start",
        }

        if explicit in mapping:
            return mapping[explicit]

        normalized = controller._normalize(
            command
        )

        if any(
            phrase in normalized
            for phrase in (
                "wznów kampanię",
                "wznow kampanie",
                "resume campaign",
            )
        ):
            return "resume"

        if any(
            phrase in normalized
            for phrase in (
                "cofnij kampanię",
                "cofnij kampanie",
                "rollback campaign",
            )
        ):
            return "rollback"

        if any(
            phrase in normalized
            for phrase in (
                "status kampanii",
                "campaign status",
            )
        ):
            return "status"

        if any(
            phrase in normalized
            for phrase in (
                "ostatnie kampanie",
                "recent campaigns",
                "lista kampanii",
            )
        ):
            return "recent"

        return "start"

    @staticmethod
    def _id_required() -> dict[str, Any]:
        return {
            "success": False,
            "status": (
                "CAMPAIGN_ID_REQUIRED"
            ),
            "campaign_id": "",
            "campaign": {},
            "errors": [
                "Podaj campaign_id."
            ],
        }
