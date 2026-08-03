from __future__ import annotations

from typing import Any

from .autonomous_campaign_director import AutonomousCampaignDirector
from .multi_campaign_workflow import MultiCampaignWorkflow
from .portfolio_optimizer import PortfolioOptimizer


class SoftwareEngineerPortfolioRouter:
    """Routes start, resume, inspect and reprioritize portfolio commands."""

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self._is_portfolio(controller, command=command, context=context):
            return None

        workflow = getattr(controller, "multi_campaign_workflow", None)
        if workflow is None:
            campaign_workflow = getattr(controller, "change_campaign_workflow", None)
            workflow = MultiCampaignWorkflow(
                project_root=controller.project_root,
                campaign_workflow=campaign_workflow,
            )
            controller.multi_campaign_workflow = workflow

        action = self._action(controller, command=command, context=context)
        portfolio_id = str(context.get("portfolio_id", "")).strip()

        if action in {
            "optimize",
            "direct",
            "director_status",
            "director_recent",
        }:
            optimizer = getattr(controller, "portfolio_optimizer", None)
            if optimizer is None:
                optimizer = PortfolioOptimizer(
                    controller.project_root,
                    store=workflow.store,
                )
                controller.portfolio_optimizer = optimizer
            director = getattr(controller, "campaign_director", None)
            if director is None:
                director = AutonomousCampaignDirector(
                    controller.project_root,
                    workflow=workflow,
                    optimizer=optimizer,
                )
                controller.campaign_director = director

            if action == "director_recent":
                return director.recent(
                    limit=max(1, int(context.get("limit", 20)))
                )

            if action == "director_status":
                return director.status(
                    run_id=str(context.get("director_run_id", "")).strip(),
                    portfolio_id=portfolio_id,
                )

            if action == "optimize":
                if not portfolio_id:
                    return self._id_required()
                return director.optimize(
                    portfolio_id,
                    constraints=self._constraints(context),
                    apply=bool(context.get("apply_optimization", True)),
                )

            if workflow.get_portfolio(portfolio_id) is None:
                campaigns = context.get(
                    "portfolio_campaigns",
                    context.get("campaigns", []),
                )
                if not isinstance(campaigns, list) or len(campaigns) < 2:
                    return {
                        "success": False,
                        "status": "MULTI_CAMPAIGN_CAMPAIGNS_REQUIRED",
                        "portfolio_id": portfolio_id,
                        "portfolio": {},
                        "errors": [
                            "Podaj co najmniej dwie kampanie w "
                            "context['portfolio_campaigns']."
                        ],
                    }
                planned = workflow.run(
                    objective,
                    campaigns=campaigns,
                    portfolio_id=portfolio_id or None,
                    auto_execute=False,
                    auto_approve=bool(context.get("auto_approve", False)),
                    auto_rollback=bool(context.get("auto_rollback", True)),
                    final_validation=bool(context.get("final_validation", True)),
                    continue_on_failure=True,
                    rollback_completed_on_failure=False,
                    metadata=dict(context.get("portfolio_metadata", {}) or {}),
                )
                if not bool(planned.get("success", False)):
                    return planned
                portfolio_id = str(planned.get("portfolio_id", ""))

            policy = dict(context.get("director_policy", {}) or {})
            return director.direct(
                portfolio_id,
                constraints=self._constraints(context),
                auto_approve=context.get("auto_approve"),
                auto_rollback=context.get("auto_rollback"),
                final_validation=context.get("final_validation"),
                max_cycles=int(policy.get("max_cycles", context.get("max_cycles", 30))),
                max_retries_per_campaign=int(
                    policy.get(
                        "max_retries_per_campaign",
                        context.get("max_retries_per_campaign", 1),
                    )
                ),
                max_failures=int(
                    policy.get("max_failures", context.get("max_failures", 2))
                ),
                rollback_on_stop=bool(
                    policy.get("rollback_on_stop", context.get("rollback_on_stop", False))
                ),
            )

        if action == "recent":
            portfolios = workflow.recent_portfolios(
                limit=max(1, int(context.get("limit", 20)))
            )
            return {
                "success": True,
                "status": "MULTI_CAMPAIGN_RECENT",
                "operation": "multi_campaign",
                "portfolio_id": "",
                "portfolio": {},
                "portfolios": portfolios,
                "campaigns_count": 0,
                "completed_campaigns": 0,
                "errors": [],
                "report_path": str(workflow.store.path),
            }

        if action == "status":
            if not portfolio_id:
                return self._id_required()
            portfolio = workflow.get_portfolio(portfolio_id)
            if portfolio is None:
                return workflow._not_found(portfolio_id)
            return {
                "success": True,
                "status": str(portfolio.get("status", "UNKNOWN")),
                "operation": "multi_campaign",
                "portfolio_id": portfolio_id,
                "portfolio": portfolio,
                "campaigns_count": len(portfolio.get("campaigns", [])),
                "completed_campaigns": len(
                    portfolio.get("completed_campaign_ids", [])
                ),
                "failed_campaigns": len(portfolio.get("failed_campaign_ids", [])),
                "blocked_campaigns": len(portfolio.get("blocked_campaign_ids", [])),
                "errors": [],
                "report_path": str(workflow.store.path),
            }

        if action == "resume":
            if not portfolio_id:
                return self._id_required()
            return workflow.resume(
                portfolio_id,
                auto_approve=context.get("auto_approve"),
                auto_rollback=context.get("auto_rollback"),
                final_validation=context.get("final_validation"),
                continue_on_failure=context.get("continue_on_failure"),
                rollback_completed_on_failure=context.get(
                    "rollback_completed_on_failure"
                ),
                max_campaigns_per_run=context.get("max_campaigns_per_run"),
            )

        if action == "rollback":
            if not portfolio_id:
                return self._id_required()
            return workflow.rollback(portfolio_id)

        if action == "pause":
            if not portfolio_id:
                return self._id_required()
            return workflow.pause(portfolio_id)

        if action == "reprioritize":
            if not portfolio_id:
                return self._id_required()
            priorities = context.get("priorities", {})
            return workflow.reprioritize(
                portfolio_id,
                priorities if isinstance(priorities, dict) else {},
            )

        campaigns = context.get(
            "portfolio_campaigns",
            context.get("campaigns", []),
        )
        if not isinstance(campaigns, list) or len(campaigns) < 2:
            return {
                "success": False,
                "status": "MULTI_CAMPAIGN_CAMPAIGNS_REQUIRED",
                "portfolio_id": portfolio_id,
                "portfolio": {},
                "errors": [
                    "Podaj co najmniej dwie kampanie w "
                    "context['portfolio_campaigns']."
                ],
            }

        return workflow.run(
            objective,
            campaigns=campaigns,
            portfolio_id=portfolio_id or None,
            auto_execute=bool(context.get("auto_execute", True)),
            auto_approve=bool(context.get("auto_approve", False)),
            auto_rollback=bool(context.get("auto_rollback", True)),
            final_validation=bool(context.get("final_validation", True)),
            continue_on_failure=bool(context.get("continue_on_failure", False)),
            rollback_completed_on_failure=bool(
                context.get("rollback_completed_on_failure", True)
            ),
            max_campaigns_per_run=context.get("max_campaigns_per_run"),
            metadata=dict(context.get("portfolio_metadata", {}) or {}),
        )

    @staticmethod
    def _is_portfolio(
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> bool:
        operation = str(
            context.get("operation", context.get("mode", ""))
        ).strip().casefold()
        if context.get("multi_campaign") is True or operation in {
            "multi_campaign",
            "campaign_portfolio",
            "portfolio",
            "campaign_manager",
            "portfolio_optimizer",
            "campaign_director",
            "autonomous_campaign_director",
        }:
            return True
        normalized = controller._normalize(command)
        return any(
            phrase in normalized
            for phrase in (
                "portfolio kampanii",
                "wiele kampanii",
                "zarządzaj kampaniami",
                "zarzadzaj kampaniami",
                "multi campaign",
                "campaign portfolio",
                "optymalizuj portfolio",
                "portfolio optimizer",
                "dyrektor kampanii",
                "campaign director",
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
            context.get("portfolio_action", context.get("action", ""))
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
            "pause": "pause",
            "pauza": "pause",
            "reprioritize": "reprioritize",
            "priority": "reprioritize",
            "priorytety": "reprioritize",
            "optimize": "optimize",
            "optimizer": "optimize",
            "optymalizuj": "optimize",
            "direct": "direct",
            "director": "direct",
            "autonomous_director": "direct",
            "director_status": "director_status",
            "director_recent": "director_recent",
            "start": "start",
            "run": "start",
        }
        if explicit in mapping:
            return mapping[explicit]
        normalized = controller._normalize(command)
        phrases = (
            ("director_status", ("status dyrektora kampanii", "campaign director status")),
            ("director_recent", ("historia dyrektora kampanii", "recent director runs")),
            ("direct", ("uruchom dyrektora kampanii", "autonomiczny dyrektor kampanii", "campaign director")),
            ("optimize", ("optymalizuj portfolio", "portfolio optimizer", "optimize portfolio")),
            ("resume", ("wznów portfolio", "wznow portfolio", "resume portfolio")),
            ("rollback", ("cofnij portfolio", "rollback portfolio")),
            ("reprioritize", ("zmień priorytety", "zmien priorytety", "reprioritize")),
            ("pause", ("wstrzymaj portfolio", "pause portfolio")),
            ("status", ("status portfolio", "portfolio status")),
            ("recent", ("ostatnie portfolio", "lista portfolio", "recent portfolios")),
        )
        for action, values in phrases:
            if any(value in normalized for value in values):
                return action
        return "start"

    @staticmethod
    def _constraints(context: dict[str, Any]) -> dict[str, Any]:
        value = context.get(
            "optimization_constraints",
            context.get("constraints", {}),
        )
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _id_required() -> dict[str, Any]:
        return {
            "success": False,
            "status": "MULTI_CAMPAIGN_PORTFOLIO_ID_REQUIRED",
            "portfolio_id": "",
            "portfolio": {},
            "errors": ["Podaj portfolio_id."],
        }
