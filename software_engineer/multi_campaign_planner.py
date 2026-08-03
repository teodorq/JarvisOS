from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

from .change_campaign_planner import ChangeCampaignPlanner
from .multi_campaign_models import ManagedCampaign, MultiCampaignPortfolio


class MultiCampaignPlanner:
    """Builds a safe priority-aware portfolio of change campaigns."""

    PRIORITIES = {
        "CRITICAL": 100,
        "HIGH": 75,
        "NORMAL": 50,
        "LOW": 25,
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        min_campaigns: int = 2,
        max_campaigns: int = 30,
        max_total_stages: int = 200,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.min_campaigns = max(2, int(min_campaigns))
        self.max_campaigns = max(self.min_campaigns, int(max_campaigns))
        self.max_total_stages = max(4, int(max_total_stages))
        self.campaign_planner = ChangeCampaignPlanner(self.project_root)

    def plan(
        self,
        objective: str,
        campaigns: Iterable[dict[str, Any]],
        *,
        portfolio_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MultiCampaignPortfolio:
        normalized_objective = str(objective).strip()
        if not normalized_objective:
            raise ValueError("Cel portfolio kampanii nie może być pusty.")

        raw_campaigns = list(campaigns or [])
        if not self.min_campaigns <= len(raw_campaigns) <= self.max_campaigns:
            raise ValueError(
                f"Portfolio musi zawierać od {self.min_campaigns} "
                f"do {self.max_campaigns} kampanii."
            )

        prepared: list[ManagedCampaign] = []
        campaign_ids: set[str] = set()
        total_stages = 0

        for index, raw in enumerate(raw_campaigns, start=1):
            if not isinstance(raw, dict):
                raise TypeError("Każda kampania portfolio musi być słownikiem.")
            item = self._campaign(raw, index=index)
            if item.campaign_id in campaign_ids:
                raise ValueError(f"Powtórzony identyfikator kampanii: {item.campaign_id}")
            campaign_ids.add(item.campaign_id)
            prepared.append(item)
            total_stages += len(item.stages)

        if total_stages > self.max_total_stages:
            raise ValueError(
                "Portfolio przekracza limit "
                f"{self.max_total_stages} etapów."
            )

        self._validate_dependencies(prepared)
        self._validate_file_conflicts(prepared)
        order = self.topological_priority_order(prepared)
        normalized_id = self._safe_id(portfolio_id or f"portfolio-{uuid4().hex}")
        target_count = len({path for item in prepared for path in item.targets})
        dependency_count = sum(len(item.depends_on) for item in prepared)

        portfolio = MultiCampaignPortfolio(
            portfolio_id=normalized_id,
            objective=normalized_objective,
            campaigns=prepared,
            execution_order=order,
            fingerprint=self._fingerprint(normalized_objective, prepared, order),
            metadata={
                **dict(metadata or {}),
                "campaign_count": len(prepared),
                "stage_count": total_stages,
                "target_count": target_count,
                "dependency_count": dependency_count,
                "priority_distribution": {
                    name: sum(1 for item in prepared if item.priority == name)
                    for name in self.PRIORITIES
                },
                "estimated_risk": self._risk(prepared, target_count),
            },
        )
        return portfolio

    def _campaign(self, raw: dict[str, Any], *, index: int) -> ManagedCampaign:
        campaign_id = self._safe_id(
            raw.get("campaign_id", raw.get("id", f"campaign-{index:02d}"))
        )
        objective = str(raw.get("objective", raw.get("title", ""))).strip()
        if not objective:
            raise ValueError(f"Kampania {campaign_id} nie ma celu.")

        stages = raw.get("stages", raw.get("campaign_stages", []))
        if not isinstance(stages, list):
            raise TypeError(f"Etapy kampanii {campaign_id} muszą być listą.")

        plan = self.campaign_planner.plan(
            objective,
            stages,
            campaign_id=campaign_id,
            metadata=dict(raw.get("campaign_metadata", {}) or {}),
        )
        priority, score = self.normalize_priority(raw.get("priority", "NORMAL"))
        options = {
            key: raw[key]
            for key in (
                "auto_approve",
                "auto_rollback",
                "final_validation",
                "max_stages_per_run",
            )
            if key in raw
        }
        targets = list(
            dict.fromkeys(
                path
                for stage in plan.stages
                for path in stage.targets
            )
        )
        raw_metadata = dict(raw.get("metadata", {}) or {})
        estimated_roi = self._number(
            raw.get("estimated_roi", raw_metadata.get("estimated_roi", 5.0)),
            default=5.0,
            minimum=0.0,
            maximum=10.0,
        )
        estimated_risk = self._number(
            raw.get(
                "estimated_risk",
                raw_metadata.get(
                    "estimated_risk",
                    plan.metadata.get("estimated_risk", 0),
                ),
            ),
            default=float(plan.metadata.get("estimated_risk", 0) or 0),
            minimum=0.0,
            maximum=10.0,
        )
        estimated_minutes = self._number(
            raw.get(
                "estimated_minutes",
                raw_metadata.get("estimated_minutes", max(10, len(plan.stages) * 20)),
            ),
            default=max(10, len(plan.stages) * 20),
            minimum=1.0,
            maximum=1440.0,
        )
        confidence = self._number(
            raw.get("confidence", raw_metadata.get("confidence", 0.5)),
            default=0.5,
            minimum=0.0,
            maximum=1.0,
        )
        return ManagedCampaign(
            campaign_id=campaign_id,
            objective=objective,
            stages=[stage.to_dict() for stage in plan.stages],
            targets=targets,
            priority=priority,
            priority_score=score,
            depends_on=self._string_list(raw.get("depends_on", [])),
            metadata={
                **raw_metadata,
                "options": options,
                "campaign_fingerprint": plan.fingerprint,
                "estimated_roi": estimated_roi,
                "estimated_risk": estimated_risk,
                "estimated_minutes": estimated_minutes,
                "confidence": confidence,
                "base_priority_score": score,
            },
        )

    def _validate_dependencies(self, campaigns: list[ManagedCampaign]) -> None:
        ids = {item.campaign_id for item in campaigns}
        for item in campaigns:
            unknown = [value for value in item.depends_on if value not in ids]
            if unknown:
                raise ValueError(
                    f"Kampania {item.campaign_id} ma nieznane zależności: "
                    + ", ".join(unknown)
                )
            if item.campaign_id in item.depends_on:
                raise ValueError("Kampania nie może zależeć sama od siebie.")
        self.topological_priority_order(campaigns)

    def _validate_file_conflicts(self, campaigns: list[ManagedCampaign]) -> None:
        for index, left in enumerate(campaigns):
            for right in campaigns[index + 1:]:
                shared = sorted(set(left.targets) & set(right.targets))
                if not shared:
                    continue
                ordered = self._depends_transitively(
                    left.campaign_id,
                    right.campaign_id,
                    campaigns,
                ) or self._depends_transitively(
                    right.campaign_id,
                    left.campaign_id,
                    campaigns,
                )
                if not ordered:
                    raise ValueError(
                        "Kampanie modyfikują te same pliki bez zależności: "
                        f"{left.campaign_id}, {right.campaign_id}: "
                        + ", ".join(shared)
                    )

    @classmethod
    def topological_priority_order(
        cls,
        campaigns: list[ManagedCampaign],
    ) -> list[str]:
        original = {item.campaign_id: index for index, item in enumerate(campaigns)}
        dependencies = {
            item.campaign_id: set(item.depends_on)
            for item in campaigns
        }
        by_id = {item.campaign_id: item for item in campaigns}
        result: list[str] = []

        while dependencies:
            ready = [campaign_id for campaign_id, values in dependencies.items() if not values]
            ready.sort(
                key=lambda campaign_id: (
                    -by_id[campaign_id].priority_score,
                    original[campaign_id],
                )
            )
            if not ready:
                raise ValueError("Wykryto cykl zależności między kampaniami.")
            for campaign_id in ready:
                result.append(campaign_id)
                dependencies.pop(campaign_id)
            ready_set = set(ready)
            for values in dependencies.values():
                values.difference_update(ready_set)
        return result

    @classmethod
    def normalize_priority(cls, value: Any) -> tuple[str, int]:
        if isinstance(value, bool):
            value = "NORMAL"
        if isinstance(value, (int, float)):
            score = max(0, min(100, int(value)))
            if score >= 90:
                return "CRITICAL", score
            if score >= 65:
                return "HIGH", score
            if score >= 35:
                return "NORMAL", score
            return "LOW", score
        text = str(value).strip().upper()
        aliases = {
            "KRYTYCZNY": "CRITICAL",
            "WYSOKI": "HIGH",
            "NORMALNY": "NORMAL",
            "NISKI": "LOW",
        }
        text = aliases.get(text, text)
        if text not in cls.PRIORITIES:
            raise ValueError(
                "Nieprawidłowy priorytet kampanii. Dozwolone: "
                + ", ".join(cls.PRIORITIES)
            )
        return text, cls.PRIORITIES[text]

    @staticmethod
    def _depends_transitively(
        campaign_id: str,
        dependency_id: str,
        campaigns: list[ManagedCampaign],
    ) -> bool:
        by_id = {item.campaign_id: item for item in campaigns}
        pending = list(by_id[campaign_id].depends_on)
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == dependency_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(by_id[current].depends_on)
        return False

    @staticmethod
    def _number(
        value: Any,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = float(default)
        return max(minimum, min(maximum, number))

    @staticmethod
    def _safe_id(value: Any) -> str:
        text = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value).strip()).strip("-_")
        if not text:
            raise ValueError("Identyfikator portfolio lub kampanii jest pusty.")
        return text[:100]

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, (str, bytes)):
            value = [value]
        return list(
            dict.fromkeys(
                str(item).strip()
                for item in value
                if str(item).strip()
            )
        ) if isinstance(value, (list, tuple, set)) else []

    @staticmethod
    def _fingerprint(
        objective: str,
        campaigns: list[ManagedCampaign],
        order: list[str],
    ) -> str:
        payload = {
            "objective": objective,
            "order": order,
            "campaigns": [
                {
                    "campaign_id": item.campaign_id,
                    "objective": item.objective,
                    "priority_score": item.priority_score,
                    "depends_on": item.depends_on,
                    "stages": item.stages,
                }
                for item in campaigns
            ],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _risk(campaigns: list[ManagedCampaign], target_count: int) -> float:
        score = (
            len(campaigns) * 0.9
            + target_count * 0.18
            + sum(len(item.depends_on) * 0.35 for item in campaigns)
            + sum(float(item.metadata.get("estimated_risk", 0) or 0) * 0.12 for item in campaigns)
        )
        return round(min(10.0, score), 2)
