from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

from .cross_module_change_planner import CrossModuleChangePlanner
from .full_autonomy_feature_intent import FullAutonomyFeatureIntent
from .full_autonomy_models import FullAutonomyPlan
from .multi_campaign_planner import MultiCampaignPlanner


class FullAutonomyPlanner:
    """Turns one large objective into a safe campaign portfolio."""

    PHASE_NAMES = (
        "foundation",
        "implementation",
        "integration",
        "validation",
        "hardening",
        "delivery",
    )

    def __init__(
        self,
        project_root: str | Path,
        *,
        min_targets: int = 4,
        max_targets: int = 40,
        max_campaigns: int = 8,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.min_targets = max(4, int(min_targets))
        self.max_targets = min(100, max(self.min_targets, int(max_targets)))
        self.max_campaigns = min(12, max(2, int(max_campaigns)))
        self.portfolio_planner = MultiCampaignPlanner(
            self.project_root,
            max_campaigns=max(30, self.max_campaigns),
        )
        self.feature_intent = FullAutonomyFeatureIntent(
            self.project_root
        )

    def plan(
        self,
        objective: str,
        *,
        targets: Iterable[str] | None = None,
        campaigns: Iterable[dict[str, Any]] | None = None,
        replacements: dict[str, str] | None = None,
        goal_id: str | None = None,
        portfolio_id: str | None = None,
        acceptance_criteria: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FullAutonomyPlan:
        normalized_objective = " ".join(str(objective).split()).strip()
        if not normalized_objective:
            raise ValueError("Duży cel autonomii nie może być pusty.")
        if len(normalized_objective) > 4000:
            raise ValueError("Duży cel autonomii przekracza limit 4000 znaków.")

        safe_goal_id = self._safe_id(goal_id or f"goal-{uuid4().hex}")
        safe_portfolio_id = self._safe_id(
            portfolio_id or f"autonomy-portfolio-{uuid4().hex}"
        )
        provided_campaigns = [
            dict(item)
            for item in (campaigns or [])
            if isinstance(item, dict)
        ]

        feature_intent = None
        if not provided_campaigns and not targets and not replacements:
            feature_intent = self.feature_intent.detect(
                normalized_objective,
                allow_existing=bool(
                    (metadata or {}).get(
                        "allow_existing_feature",
                        False,
                    )
                ),
            )

        if provided_campaigns:
            target_files = self._campaign_targets(
                provided_campaigns
            )
            prepared_campaigns = provided_campaigns
            planning_source = "provided_campaigns"
        elif feature_intent is not None:
            target_files = list(
                feature_intent["target_files"]
            )
            prepared_campaigns = [
                dict(item)
                for item in feature_intent["campaigns"]
            ]
            replacements = dict(
                feature_intent["replacements"]
            )
            planning_source = "new_feature_intent"
        else:
            target_files = self._targets(
                normalized_objective,
                targets=targets,
                replacements=replacements,
            )
            prepared_campaigns = self._build_campaigns(
                normalized_objective,
                target_files,
                replacements=replacements,
            )
            planning_source = (
                "explicit_targets"
                if targets or replacements
                else "project_discovery"
            )

        if not provided_campaigns:
            prepared_campaigns = self._namespace_campaigns(
                prepared_campaigns,
                safe_portfolio_id,
            )

        portfolio = self.portfolio_planner.plan(
            normalized_objective,
            prepared_campaigns,
            portfolio_id=safe_portfolio_id,
            metadata={
                "full_autonomy": True,
                "goal_id": safe_goal_id,
                "planning_source": planning_source,
            },
        )
        target_files = list(
            dict.fromkeys(
                path
                for item in portfolio.campaigns
                for path in item.targets
            )
        )
        if len(target_files) < self.min_targets:
            raise ValueError(
                f"Pełna autonomia wymaga co najmniej {self.min_targets} "
                "bezpiecznych plików docelowych."
            )
        if len(target_files) > self.max_targets:
            raise ValueError(
                f"Pełna autonomia obsługuje maksymalnie {self.max_targets} plików."
            )

        subsystems = sorted(
            {
                CrossModuleChangePlanner._subsystem(path)
                for path in target_files
            }
        )
        if len(subsystems) < 2:
            raise ValueError(
                "Pełna autonomia wymaga co najmniej dwóch podsystemów."
            )

        criteria = self._criteria(acceptance_criteria)
        campaign_values = [
            item.to_dict()
            for item in portfolio.campaigns
        ]
        estimated_minutes = int(
            round(
                sum(
                    float(
                        item.metadata.get(
                            "estimated_minutes",
                            max(20, len(item.stages) * 20),
                        )
                        or 0
                    )
                    for item in portfolio.campaigns
                )
            )
        )
        estimated_risk = round(
            min(
                10.0,
                float(portfolio.metadata.get("estimated_risk", 0) or 0)
                + len(subsystems) * 0.15,
            ),
            2,
        )
        estimated_roi = round(
            sum(
                float(item.metadata.get("estimated_roi", 5.0) or 5.0)
                for item in portfolio.campaigns
            )
            / max(1, len(portfolio.campaigns)),
            2,
        )
        confidence = round(
            sum(
                float(item.metadata.get("confidence", 0.5) or 0.5)
                for item in portfolio.campaigns
            )
            / max(1, len(portfolio.campaigns)),
            3,
        )
        fingerprint = self._fingerprint(
            normalized_objective,
            target_files,
            campaign_values,
            criteria,
        )

        return FullAutonomyPlan(
            goal_id=safe_goal_id,
            portfolio_id=safe_portfolio_id,
            objective=normalized_objective,
            target_files=target_files,
            subsystems=subsystems,
            campaigns=campaign_values,
            execution_order=list(portfolio.execution_order),
            acceptance_criteria=criteria,
            fingerprint=fingerprint,
            estimated_roi=estimated_roi,
            estimated_risk=estimated_risk,
            estimated_minutes=estimated_minutes,
            confidence=confidence,
            metadata={
                **dict(metadata or {}),
                "planning_source": planning_source,
                "campaign_count": len(campaign_values),
                "target_count": len(target_files),
                "subsystem_count": len(subsystems),
                "portfolio_fingerprint": portfolio.fingerprint,
                "feature_intent": (
                    {
                        "feature_name": feature_intent["feature_name"],
                        "package_path": feature_intent["package_path"],
                        "blueprint": feature_intent["blueprint"],
                    }
                    if feature_intent is not None
                    else {}
                ),
            },
        )

    @staticmethod
    def _namespace_campaigns(
        campaigns: list[dict[str, Any]],
        portfolio_id: str,
    ) -> list[dict[str, Any]]:
        namespace = hashlib.sha256(
            str(portfolio_id).encode(
                "utf-8"
            )
        ).hexdigest()[:10]
        mapping: dict[str, str] = {}

        for index, item in enumerate(
            campaigns,
            start=1,
        ):
            original = str(
                item.get(
                    "campaign_id",
                    f"campaign-{index}",
                )
            ).strip()
            mapping[original] = (
                f"fa-{namespace}-{original}"
            )

        result: list[dict[str, Any]] = []

        for index, item in enumerate(
            campaigns,
            start=1,
        ):
            value = dict(item)
            original = str(
                value.get(
                    "campaign_id",
                    f"campaign-{index}",
                )
            ).strip()
            value["campaign_id"] = mapping[
                original
            ]
            value["depends_on"] = [
                mapping.get(
                    str(dependency),
                    str(dependency),
                )
                for dependency in value.get(
                    "depends_on",
                    [],
                )
            ]
            value["metadata"] = {
                **dict(
                    value.get(
                        "metadata",
                        {},
                    )
                    or {}
                ),
                "template_campaign_id": original,
                "portfolio_namespace": namespace,
            }
            result.append(value)

        return result

    def _targets(
        self,
        objective: str,
        *,
        targets: Iterable[str] | None,
        replacements: dict[str, str] | None,
    ) -> list[str]:
        values: list[str] = []
        if targets is not None:
            if isinstance(targets, (str, bytes)):
                targets = [str(targets)]
            values.extend(str(item) for item in targets)
        if isinstance(replacements, dict):
            values.extend(str(path) for path in replacements)

        if values:
            result = self._validated_targets(
                values,
                allow_new=bool(replacements),
            )
        else:
            result = self._discover_targets(objective)

        if len(result) < self.min_targets:
            raise ValueError(
                f"Nie znaleziono wymaganych {self.min_targets} plików celu. "
                "Podaj context['autonomy_targets']."
            )
        return result[: self.max_targets]

    def _validated_targets(
        self,
        values: Iterable[str],
        *,
        allow_new: bool = False,
    ) -> list[str]:
        result: list[str] = []
        for value in values:
            text = str(value).strip().replace("\\", "/")
            if not text:
                continue
            candidate = Path(text).expanduser()
            if not candidate.is_absolute():
                candidate = self.project_root / candidate
            unresolved = candidate
            candidate = candidate.resolve(strict=False)
            try:
                relative = candidate.relative_to(self.project_root)
            except ValueError as error:
                raise ValueError(
                    f"Plik pełnej autonomii jest poza projektem: {value}"
                ) from error
            if unresolved.exists() and unresolved.is_symlink():
                raise ValueError(
                    f"Plik pełnej autonomii nie może być symlinkiem: {value}"
                )
            if candidate.suffix.casefold() != ".py":
                raise ValueError(
                    f"Pełna autonomia obsługuje tylko pliki Python: {value}"
                )
            normalized = relative.as_posix()
            if self._protected(normalized):
                raise ValueError(
                    f"Chroniona ścieżka nie może być celem autonomii: {normalized}"
                )
            if candidate.exists() and not candidate.is_file():
                raise ValueError(
                    f"Cel pełnej autonomii nie jest plikiem: {normalized}"
                )
            if not candidate.exists() and not allow_new:
                raise ValueError(
                    f"Plik celu pełnej autonomii nie istnieje: {normalized}"
                )
            if normalized not in result:
                result.append(normalized)
        return result

    def _discover_targets(
        self,
        objective: str,
    ) -> list[str]:
        tokens = {
            token
            for token in re.findall(
                r"[a-zA-Z0-9_ąćęłńóśźż]+",
                objective.casefold(),
            )
            if len(token) >= 3
            and token not in {
                "oraz", "dla", "przez", "pełna", "pelna",
                "autonomia", "autonomicznie", "system",
                "projekt", "duży", "duzy", "zmiana", "zmiany",
            }
        }
        candidates: list[tuple[int, str]] = []
        roots = (
            self.project_root / "app",
            self.project_root / "tests",
        )
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.py"):
                if "__pycache__" in path.parts or path.is_symlink():
                    continue
                relative = path.relative_to(self.project_root).as_posix()
                if self._protected(relative):
                    continue
                searchable = relative.casefold().replace("/", " ")
                score = sum(5 for token in tokens if token in searchable)
                if relative.startswith("tests/test_"):
                    score += 1
                if relative.endswith("__init__.py"):
                    score -= 3
                candidates.append((score, relative))

        candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
        selected: list[str] = [
            relative
            for score, relative in candidates
            if score > 0
        ]
        fallback_patterns = (
            "app/ai/brain.py",
            "app/ai/software_engineer/autonomous_software_engineer.py",
            "app/autodev/developer_controller.py",
        )
        for relative in fallback_patterns:
            if (self.project_root / relative).is_file() and relative not in selected:
                selected.append(relative)
        for _, relative in candidates:
            if relative not in selected:
                selected.append(relative)
            if len(selected) >= max(self.min_targets, 12):
                break
        return self._validated_targets(selected[: max(self.min_targets, 12)])

    def _build_campaigns(
        self,
        objective: str,
        targets: list[str],
        *,
        replacements: dict[str, str] | None,
    ) -> list[dict[str, Any]]:
        safe_replacements = {
            path.replace("\\", "/"): str(content)
            for path, content in (replacements or {}).items()
            if path.replace("\\", "/") in targets
        }
        desired = min(
            self.max_campaigns,
            max(2, int(math.ceil(len(targets) / 4))),
        )
        groups = self._campaign_groups(targets, desired)
        campaigns: list[dict[str, Any]] = []
        previous_id = ""

        for index, group in enumerate(groups, start=1):
            phase = self.PHASE_NAMES[min(index - 1, len(self.PHASE_NAMES) - 1)]
            campaign_id = f"autonomy-{index:02d}-{phase}"
            first_stage = f"{campaign_id}-implementation"
            second_stage = f"{campaign_id}-verification"
            stage_replacements = {
                path: safe_replacements[path]
                for path in group
                if path in safe_replacements
            }
            stages = [
                {
                    "stage_id": first_stage,
                    "objective": (
                        f"{objective} — etap {phase}: implementacja "
                        "i spójność API."
                    ),
                    "targets": list(group),
                    "replacements": stage_replacements,
                    "allow_same_subsystem": True,
                    "metadata": {
                        "full_autonomy_phase": phase,
                        "phase_kind": "implementation",
                    },
                },
                {
                    "stage_id": second_stage,
                    "objective": (
                        f"{objective} — etap {phase}: integracja, testy "
                        "i zabezpieczenie regresji."
                    ),
                    "targets": list(group),
                    "depends_on": [first_stage],
                    "allow_same_subsystem": True,
                    "metadata": {
                        "full_autonomy_phase": phase,
                        "phase_kind": "verification",
                    },
                },
            ]
            campaigns.append(
                {
                    "campaign_id": campaign_id,
                    "objective": f"{objective} — kampania {phase}",
                    "priority": (
                        "CRITICAL" if index == 1
                        else "HIGH" if index <= 3
                        else "NORMAL"
                    ),
                    "depends_on": [previous_id] if previous_id else [],
                    "estimated_roi": max(5.0, 9.0 - index * 0.45),
                    "estimated_risk": min(9.0, 2.0 + len(group) * 0.55 + index * 0.25),
                    "estimated_minutes": max(30, len(group) * 20),
                    "confidence": max(0.5, 0.88 - index * 0.04),
                    "stages": stages,
                    "metadata": {
                        "full_autonomy": True,
                        "phase": phase,
                    },
                }
            )
            previous_id = campaign_id

        return campaigns

    def _campaign_groups(
        self,
        targets: list[str],
        desired: int,
    ) -> list[list[str]]:
        by_subsystem: dict[str, list[str]] = {}
        for path in targets:
            subsystem = CrossModuleChangePlanner._subsystem(path)
            by_subsystem.setdefault(subsystem, []).append(path)

        ordered = sorted(
            targets,
            key=lambda path: (
                len(by_subsystem[CrossModuleChangePlanner._subsystem(path)]),
                path,
            ),
        )
        groups: list[list[str]] = [[] for _ in range(desired)]
        for index, path in enumerate(ordered):
            groups[index % desired].append(path)

        integration_targets = list(targets)
        for index, group in enumerate(groups):
            while len(group) < 2:
                candidate = integration_targets[
                    (index + len(group)) % len(integration_targets)
                ]
                if candidate not in group:
                    group.append(candidate)
                else:
                    for value in integration_targets:
                        if value not in group:
                            group.append(value)
                            break
            subsystems = {
                CrossModuleChangePlanner._subsystem(path)
                for path in group
            }
            if len(subsystems) < 2:
                for candidate in integration_targets:
                    if (
                        CrossModuleChangePlanner._subsystem(candidate)
                        not in subsystems
                    ):
                        group.append(candidate)
                        break
        return [list(dict.fromkeys(group)) for group in groups]

    def _campaign_targets(
        self,
        campaigns: list[dict[str, Any]],
    ) -> list[str]:
        values: list[str] = []
        for campaign in campaigns:
            stages = campaign.get(
                "stages",
                campaign.get("campaign_stages", []),
            )
            if not isinstance(stages, list):
                continue
            for stage in stages:
                if not isinstance(stage, dict):
                    continue
                targets = stage.get(
                    "targets",
                    stage.get("target_paths", []),
                )
                if isinstance(targets, (str, bytes)):
                    targets = [targets]
                if isinstance(targets, (list, tuple, set)):
                    values.extend(str(item) for item in targets)
                replacements = stage.get("replacements", {})
                if isinstance(replacements, dict):
                    values.extend(str(item) for item in replacements)
        return self._validated_targets(
            values,
            allow_new=any(
                isinstance(stage.get("replacements"), dict)
                and bool(stage.get("replacements"))
                for campaign in campaigns
                for stage in (
                    campaign.get(
                        "stages",
                        campaign.get("campaign_stages", []),
                    )
                    if isinstance(
                        campaign.get(
                            "stages",
                            campaign.get("campaign_stages", []),
                        ),
                        list,
                    )
                    else []
                )
                if isinstance(stage, dict)
            ),
        )

    @staticmethod
    def _criteria(
        values: Iterable[str] | None,
    ) -> list[str]:
        criteria = [
            str(item).strip()
            for item in (values or [])
            if str(item).strip()
        ]
        defaults = (
            "Wszystkie zaplanowane pliki przechodzą walidację składni.",
            "Pełny zestaw testów projektu kończy się powodzeniem.",
            "Żaden plik spoza planu nie zostaje zmodyfikowany.",
            "Każda nieudana kampania ma bezpieczny retry albo rollback.",
            "Raport końcowy zawiera decyzje, wyniki i ścieżki raportów.",
        )
        for item in defaults:
            if item not in criteria:
                criteria.append(item)
        return criteria[:20]

    @staticmethod
    def _protected(path: str) -> bool:
        normalized = path.casefold().strip("/")
        return (
            normalized.startswith(("archive/", "ai_pliki/", ".git/", "data/"))
            or normalized.endswith((".env", ".pem", ".key"))
        )

    @staticmethod
    def _safe_id(value: Any) -> str:
        text = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "-",
            str(value).strip(),
        ).strip("-_")
        if not text:
            raise ValueError("Identyfikator pełnej autonomii jest pusty.")
        return text[:120]

    @staticmethod
    def _fingerprint(
        objective: str,
        targets: list[str],
        campaigns: list[dict[str, Any]],
        criteria: list[str],
    ) -> str:
        payload = {
            "objective": objective,
            "targets": targets,
            "campaigns": campaigns,
            "acceptance_criteria": criteria,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
