from __future__ import annotations

from .multi_campaign_models import ManagedCampaign, MultiCampaignPortfolio
from .multi_campaign_planner import MultiCampaignPlanner


class MultiCampaignScheduler:
    """Selects dependency-ready campaigns by priority."""

    FAILURE_STATUSES = {
        "FAILED",
        "ROLLED_BACK",
        "CANCELLED",
        "BLOCKED",
    }

    def ready_campaigns(
        self,
        portfolio: MultiCampaignPortfolio,
    ) -> list[ManagedCampaign]:
        completed = set(portfolio.completed_campaign_ids)
        order_index = {
            campaign_id: index
            for index, campaign_id in enumerate(portfolio.execution_order)
        }
        ready = [
            item
            for item in portfolio.campaigns
            if item.status in {"PENDING", "PAUSED"}
            and set(item.depends_on).issubset(completed)
        ]
        ready.sort(
            key=lambda item: (
                -item.priority_score,
                order_index.get(item.campaign_id, 10**9),
            )
        )
        return ready

    def next_campaign(
        self,
        portfolio: MultiCampaignPortfolio,
    ) -> ManagedCampaign | None:
        ready = self.ready_campaigns(portfolio)
        return ready[0] if ready else None

    def mark_blocked(
        self,
        portfolio: MultiCampaignPortfolio,
    ) -> list[str]:
        by_id = {
            item.campaign_id: item
            for item in portfolio.campaigns
        }
        blocked: list[str] = []
        for item in portfolio.campaigns:
            if item.status not in {"PENDING", "PAUSED"}:
                continue
            failed_dependencies = [
                dependency
                for dependency in item.depends_on
                if by_id[dependency].status in self.FAILURE_STATUSES
            ]
            if not failed_dependencies:
                continue
            item.status = "BLOCKED"
            item.errors.append(
                "Zablokowana przez nieudaną zależność: "
                + ", ".join(failed_dependencies)
            )
            blocked.append(item.campaign_id)
        return blocked

    def recalculate_order(
        self,
        portfolio: MultiCampaignPortfolio,
    ) -> list[str]:
        order = MultiCampaignPlanner.topological_priority_order(
            portfolio.campaigns
        )
        portfolio.execution_order = order
        return order
