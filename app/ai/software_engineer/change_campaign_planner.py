from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

from .change_campaign_models import (
    ChangeCampaign,
    ChangeCampaignStage,
)
from .cross_module_change_planner import (
    CrossModuleChangePlanner,
)


class ChangeCampaignPlanner:
    """Builds a safe dependency-ordered multi-stage change campaign."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        min_stages: int = 2,
        max_stages: int = 20,
        max_files: int = 100,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.min_stages = max(
            2,
            int(min_stages),
        )
        self.max_stages = max(
            self.min_stages,
            int(max_stages),
        )
        self.max_files = max(
            4,
            int(max_files),
        )

    def plan(
        self,
        objective: str,
        stages: Iterable[
            dict[str, Any]
        ],
        *,
        campaign_id: str | None = None,
        metadata: dict[
            str,
            Any,
        ] | None = None,
    ) -> ChangeCampaign:
        normalized_objective = str(
            objective
        ).strip()

        if not normalized_objective:
            raise ValueError(
                "Cel kampanii nie może być pusty."
            )

        raw_stages = list(
            stages or []
        )

        if not (
            self.min_stages
            <= len(raw_stages)
            <= self.max_stages
        ):
            raise ValueError(
                "Kampania musi zawierać od "
                f"{self.min_stages} do "
                f"{self.max_stages} etapów."
            )

        prepared: list[
            ChangeCampaignStage
        ] = []
        stage_ids: set[str] = set()
        total_files: set[str] = set()

        for index, raw in enumerate(
            raw_stages,
            start=1,
        ):
            if not isinstance(
                raw,
                dict,
            ):
                raise TypeError(
                    "Każdy etap kampanii musi "
                    "być słownikiem."
                )

            stage = self._stage(
                raw,
                index=index,
            )

            if stage.stage_id in stage_ids:
                raise ValueError(
                    "Powtórzony identyfikator etapu: "
                    f"{stage.stage_id}"
                )

            stage_ids.add(
                stage.stage_id
            )
            prepared.append(stage)
            total_files.update(
                stage.targets
            )

        if len(total_files) > self.max_files:
            raise ValueError(
                "Kampania przekracza limit "
                f"{self.max_files} unikalnych plików."
            )

        for stage in prepared:
            unknown = [
                dependency
                for dependency
                in stage.depends_on
                if dependency not in stage_ids
            ]

            if unknown:
                raise ValueError(
                    f"Etap {stage.stage_id} ma "
                    "nieznane zależności: "
                    + ", ".join(unknown)
                )

            if stage.stage_id in stage.depends_on:
                raise ValueError(
                    "Etap nie może zależeć "
                    "od samego siebie: "
                    f"{stage.stage_id}"
                )

        order = self._topological_order(
            prepared
        )
        campaign_identifier = (
            self._safe_campaign_id(
                campaign_id
            )
            if campaign_id
            else f"campaign-{uuid4().hex}"
        )
        fingerprint = self._fingerprint(
            normalized_objective,
            prepared,
            order,
        )
        subsystems = sorted(
            {
                CrossModuleChangePlanner._subsystem(
                    path
                )
                for path in total_files
            }
        )

        return ChangeCampaign(
            campaign_id=campaign_identifier,
            objective=normalized_objective,
            stages=prepared,
            execution_order=order,
            fingerprint=fingerprint,
            metadata={
                **dict(metadata or {}),
                "operation": "change_campaign",
                "stage_count": len(prepared),
                "file_count": len(total_files),
                "subsystems": subsystems,
                "estimated_risk": self._risk(
                    prepared,
                    len(total_files),
                    len(subsystems),
                ),
            },
        )

    def _stage(
        self,
        raw: dict[str, Any],
        *,
        index: int,
    ) -> ChangeCampaignStage:
        stage_id = self._safe_stage_id(
            raw.get(
                "stage_id",
                raw.get(
                    "id",
                    f"stage-{index:02d}",
                ),
            )
        )
        objective = str(
            raw.get(
                "objective",
                raw.get(
                    "title",
                    "",
                ),
            )
        ).strip()

        if not objective:
            raise ValueError(
                f"Etap {stage_id} nie ma celu."
            )

        replacements_raw = raw.get(
            "replacements",
            {},
        )
        replacements = (
            {
                self._relative_path(
                    path
                ): str(content)
                for path, content
                in replacements_raw.items()
            }
            if isinstance(
                replacements_raw,
                dict,
            )
            else {}
        )
        targets_raw = raw.get(
            "targets",
            raw.get(
                "target_paths",
                [],
            ),
        )

        if isinstance(
            targets_raw,
            (str, bytes),
        ):
            targets_raw = [
                targets_raw
            ]

        targets = [
            self._relative_path(
                value
            )
            for value in (
                targets_raw
                if isinstance(
                    targets_raw,
                    (
                        list,
                        tuple,
                        set,
                    ),
                )
                else []
            )
        ]

        for path in replacements:
            if path not in targets:
                targets.append(path)

        targets = list(
            dict.fromkeys(targets)
        )

        if len(targets) < 2:
            raise ValueError(
                f"Etap {stage_id} musi obejmować "
                "co najmniej dwa pliki."
            )

        depends_on = self._string_list(
            raw.get(
                "depends_on",
                raw.get(
                    "dependencies",
                    [],
                ),
            )
        )
        required_subsystems = (
            self._string_list(
                raw.get(
                    "required_subsystems",
                    [],
                )
            )
        )
        allow_same_subsystem = bool(
            raw.get(
                "allow_same_subsystem",
                False,
            )
        )
        actual_subsystems = {
            CrossModuleChangePlanner._subsystem(
                path
            )
            for path in targets
        }

        if (
            len(actual_subsystems) < 2
            and not allow_same_subsystem
        ):
            raise ValueError(
                f"Etap {stage_id} nie obejmuje "
                "co najmniej dwóch podsystemów."
            )

        missing_required = [
            subsystem
            for subsystem
            in required_subsystems
            if subsystem not in actual_subsystems
        ]

        if missing_required:
            raise ValueError(
                f"Etap {stage_id} nie obejmuje "
                "wymaganych podsystemów: "
                + ", ".join(
                    missing_required
                )
            )

        return ChangeCampaignStage(
            stage_id=stage_id,
            objective=objective,
            targets=targets,
            replacements=replacements,
            depends_on=depends_on,
            required_subsystems=(
                required_subsystems
            ),
            allow_same_subsystem=(
                allow_same_subsystem
            ),
            allow_public_symbol_removal=bool(
                raw.get(
                    "allow_public_symbol_removal",
                    False,
                )
            ),
            auto_approve=bool(
                raw.get(
                    "auto_approve",
                    False,
                )
            ),
            metadata=dict(
                raw.get(
                    "metadata",
                    {},
                )
                or {}
            ),
        )

    def _relative_path(
        self,
        value: Any,
    ) -> str:
        text = str(
            value
        ).strip().replace(
            "\\",
            "/",
        )

        if not text:
            raise ValueError(
                "Ścieżka pliku nie może być pusta."
            )

        candidate = Path(
            text
        ).expanduser()

        if not candidate.is_absolute():
            candidate = (
                self.project_root
                / candidate
            )

        unresolved = candidate
        candidate = candidate.resolve(
            strict=False
        )

        try:
            relative = candidate.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ValueError(
                "Plik kampanii znajduje się "
                "poza projektem: "
                f"{value}"
            ) from error

        if (
            unresolved.exists()
            and unresolved.is_symlink()
        ):
            raise ValueError(
                "Kampania nie może modyfikować "
                f"symlinka: {value}"
            )

        if candidate.suffix.casefold() != ".py":
            raise ValueError(
                "Kampania może modyfikować tylko "
                f"pliki Python: {value}"
            )

        return relative.as_posix()

    @staticmethod
    def _safe_stage_id(
        value: Any,
    ) -> str:
        text = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "-",
            str(value).strip(),
        ).strip("-_")

        if not text:
            raise ValueError(
                "Identyfikator etapu jest pusty."
            )

        return text[:80]

    @staticmethod
    def _safe_campaign_id(
        value: Any,
    ) -> str:
        text = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "-",
            str(value).strip(),
        ).strip("-_")

        if not text:
            raise ValueError(
                "Identyfikator kampanii jest pusty."
            )

        return text[:100]

    @staticmethod
    def _string_list(
        value: Any,
    ) -> list[str]:
        if isinstance(
            value,
            (str, bytes),
        ):
            value = [value]

        return list(
            dict.fromkeys(
                str(item).strip()
                for item in (
                    value
                    if isinstance(
                        value,
                        (
                            list,
                            tuple,
                            set,
                        ),
                    )
                    else []
                )
                if str(item).strip()
            )
        )

    @staticmethod
    def _topological_order(
        stages: list[
            ChangeCampaignStage
        ],
    ) -> list[str]:
        order_index = {
            stage.stage_id: index
            for index, stage
            in enumerate(stages)
        }
        dependencies = {
            stage.stage_id: set(
                stage.depends_on
            )
            for stage in stages
        }
        result: list[str] = []

        while dependencies:
            ready = sorted(
                (
                    stage_id
                    for stage_id, values
                    in dependencies.items()
                    if not values
                ),
                key=order_index.__getitem__,
            )

            if not ready:
                raise ValueError(
                    "Wykryto cykl zależności "
                    "między etapami kampanii."
                )

            for stage_id in ready:
                result.append(stage_id)
                dependencies.pop(
                    stage_id
                )

            ready_set = set(ready)

            for values in dependencies.values():
                values.difference_update(
                    ready_set
                )

        return result

    @staticmethod
    def _fingerprint(
        objective: str,
        stages: list[
            ChangeCampaignStage
        ],
        order: list[str],
    ) -> str:
        payload = {
            "objective": objective,
            "order": order,
            "stages": [
                {
                    "stage_id": stage.stage_id,
                    "objective": stage.objective,
                    "targets": stage.targets,
                    "replacements": (
                        stage.replacements
                    ),
                    "depends_on": (
                        stage.depends_on
                    ),
                }
                for stage in stages
            ],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        return hashlib.sha256(
            encoded
        ).hexdigest()

    @staticmethod
    def _risk(
        stages: list[
            ChangeCampaignStage
        ],
        file_count: int,
        subsystem_count: int,
    ) -> float:
        score = (
            len(stages) * 0.7
            + file_count * 0.28
            + subsystem_count * 0.65
            + sum(
                0.8
                for stage in stages
                if stage.allow_public_symbol_removal
            )
        )

        return round(
            min(
                10.0,
                score,
            ),
            2,
        )
