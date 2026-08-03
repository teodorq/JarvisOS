from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .change_campaign_models import (
    ChangeCampaign,
)


class ChangeCampaignStore:
    """Atomic bounded campaign state and checkpoint storage."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_records: int = 50,
    ) -> None:
        self.paths = ProjectPaths.from_value(
            project_root
        )
        self.max_records = max(
            10,
            int(max_records),
        )
        self.path = (
            self.paths.autodev_data
            / "change_campaigns.json"
        )
        self._store = JsonStore(
            self.path,
            lambda: {
                "version": 1,
                "updated_at": "",
                "campaigns": {},
                "order": [],
            },
        )

    def save(
        self,
        campaign: ChangeCampaign,
    ) -> dict[str, Any]:
        campaign.touch()
        payload = self._payload(
            self._store.load()
        )
        campaigns = payload[
            "campaigns"
        ]
        order = payload["order"]
        campaign_id = (
            campaign.campaign_id
        )
        stored = campaign.to_dict()
        campaigns[
            campaign_id
        ] = stored

        if campaign_id in order:
            order.remove(
                campaign_id
            )

        order.append(campaign_id)

        while len(order) > self.max_records:
            removed = order.pop(0)
            campaigns.pop(
                removed,
                None,
            )

        payload["updated_at"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )
        self._store.save(payload)

        return dict(stored)

    def get(
        self,
        campaign_id: str,
    ) -> ChangeCampaign | None:
        payload = self._payload(
            self._store.load()
        )
        value = payload[
            "campaigns"
        ].get(
            str(campaign_id).strip()
        )

        if not isinstance(
            value,
            dict,
        ):
            return None

        return ChangeCampaign.from_dict(
            value
        )

    def list_recent(
        self,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        payload = self._payload(
            self._store.load()
        )
        safe_limit = min(
            self.max_records,
            max(
                1,
                int(limit),
            ),
        )
        selected = payload[
            "order"
        ][-safe_limit:]

        return [
            dict(
                payload[
                    "campaigns"
                ][campaign_id]
            )
            for campaign_id in reversed(
                selected
            )
            if isinstance(
                payload[
                    "campaigns"
                ].get(
                    campaign_id
                ),
                dict,
            )
        ]

    @staticmethod
    def _payload(
        value: Any,
    ) -> dict[str, Any]:
        payload = (
            dict(value)
            if isinstance(
                value,
                dict,
            )
            else {}
        )
        campaigns = payload.get(
            "campaigns",
            {},
        )
        order = payload.get(
            "order",
            [],
        )

        if not isinstance(
            campaigns,
            dict,
        ):
            campaigns = {}

        if not isinstance(
            order,
            list,
        ):
            order = []

        normalized_campaigns = {
            str(key): dict(item)
            for key, item
            in campaigns.items()
            if isinstance(
                item,
                dict,
            )
        }
        normalized_order = [
            str(campaign_id)
            for campaign_id in order
            if str(campaign_id)
            in normalized_campaigns
        ]

        for campaign_id in normalized_campaigns:
            if campaign_id not in normalized_order:
                normalized_order.append(
                    campaign_id
                )

        return {
            "version": 1,
            "updated_at": str(
                payload.get(
                    "updated_at",
                    "",
                )
            ),
            "campaigns": (
                normalized_campaigns
            ),
            "order": normalized_order,
        }
