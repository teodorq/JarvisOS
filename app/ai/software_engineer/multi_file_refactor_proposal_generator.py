from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from app.autodev.developer_agent import (
    DeveloperAgent,
)
from app.autodev.execution_policy import (
    ExecutionPolicy,
    ProjectBoundaryPolicy,
)


class MultiFileRefactorProposalGenerator:
    """Generates reviewed full-file proposals without writing to disk."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        developer_agent: DeveloperAgent | None = None,
        max_files: int = 12,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.developer_agent = (
            developer_agent
            or DeveloperAgent(
                project_root=str(
                    self.project_root
                )
            )
        )
        self.max_files = max(
            2,
            int(max_files),
        )
        self.boundary = ProjectBoundaryPolicy(
            ExecutionPolicy(
                project_root=self.project_root,
                allowed_extensions=(
                    ".py",
                ),
            )
        )

    def generate(
        self,
        objective: str,
        targets: Iterable[str | Path],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        objective = " ".join(
            str(objective).split()
        ).strip()

        if not objective:
            return {
                "success": False,
                "status": (
                    "REFACTOR_OBJECTIVE_REQUIRED"
                ),
                "replacements": {},
                "proposals": [],
                "errors": [
                    "Cel refaktoryzacji nie może być pusty.",
                ],
            }

        try:
            resolved_targets = self._targets(
                targets
            )
        except Exception as error:
            return {
                "success": False,
                "status": (
                    "REFACTOR_TARGETS_INVALID"
                ),
                "replacements": {},
                "proposals": [],
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
            }

        replacements: dict[str, str] = {}
        proposals: list[dict[str, Any]] = []
        errors: list[str] = []
        common_metadata = dict(
            metadata or {}
        )

        for target in resolved_targets:
            relative = target.relative_to(
                self.project_root
            ).as_posix()
            task = {
                "task_id": (
                    "multi-file-refactor:"
                    + relative
                ),
                "title": (
                    "Refaktoryzuj "
                    + relative
                ),
                "description": objective,
                "target": relative,
                "metadata": {
                    **common_metadata,
                    "operation": "refactor",
                    "multi_file": True,
                    "preserve_public_api": True,
                },
            }

            try:
                proposal = (
                    self.developer_agent
                    .generate_code_proposal(
                        target=relative,
                        goal=objective,
                        task=task,
                    )
                )
            except Exception as error:
                proposal = {
                    "success": False,
                    "target": relative,
                    "proposed_content": "",
                    "strategy": "",
                    "errors": [
                        f"{type(error).__name__}: {error}",
                    ],
                }

            proposal = dict(
                proposal
                if isinstance(
                    proposal,
                    dict,
                )
                else {}
            )
            content = str(
                proposal.get(
                    "proposed_content",
                    "",
                )
            )
            proposal_errors = [
                str(item)
                for item in proposal.get(
                    "errors",
                    [],
                )
                or []
                if str(item).strip()
            ]
            proposal_record = {
                "path": relative,
                "success": bool(
                    proposal.get(
                        "success",
                        False,
                    )
                ),
                "strategy": str(
                    proposal.get(
                        "strategy",
                        "",
                    )
                ),
                "errors": proposal_errors,
                "metadata": dict(
                    proposal.get(
                        "metadata",
                        {},
                    )
                    or {}
                ),
            }
            proposals.append(
                proposal_record
            )

            if (
                not proposal_record[
                    "success"
                ]
                or not content.strip()
            ):
                errors.extend(
                    [
                        (
                            f"{relative}: {item}"
                        )
                        for item
                        in (
                            proposal_errors
                            or [
                                "Nie wygenerowano "
                                "pełnej zawartości pliku.",
                            ]
                        )
                    ]
                )
                continue

            if not content.endswith(
                "\n"
            ):
                content += "\n"

            replacements[
                relative
            ] = content

        if errors:
            return {
                "success": False,
                "status": (
                    "REFACTOR_PROPOSAL_FAILED"
                ),
                "replacements": {},
                "proposals": proposals,
                "errors": self._unique(
                    errors
                ),
            }

        return {
            "success": True,
            "status": (
                "REFACTOR_PROPOSALS_READY"
            ),
            "replacements": replacements,
            "proposals": proposals,
            "errors": [],
        }

    def _targets(
        self,
        values: Iterable[str | Path],
    ) -> list[Path]:
        if isinstance(
            values,
            (
                str,
                bytes,
            ),
        ):
            raise TypeError(
                "targets musi być kolekcją ścieżek."
            )

        resolved: list[Path] = []

        for value in values:
            target = self.boundary.resolve_target(
                value,
                require_file=True,
                allow_missing=False,
            )

            if target not in resolved:
                resolved.append(
                    target
                )

        if (
            len(resolved) < 2
            or len(resolved) > self.max_files
        ):
            raise ValueError(
                "Autonomiczna refaktoryzacja wymaga od 2 do "
                f"{self.max_files} plików."
            )

        return sorted(
            resolved,
            key=lambda item: item.relative_to(
                self.project_root
            ).as_posix(),
        )

    @staticmethod
    def _unique(
        values: Iterable[str],
    ) -> list[str]:
        result: list[str] = []

        for value in values:
            text = str(
                value
            ).strip()

            if text and text not in result:
                result.append(
                    text
                )

        return result
