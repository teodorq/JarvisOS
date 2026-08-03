from __future__ import annotations

from .implementation_execution_service import ImplementationExecutionService

from app.core.project_paths import default_project_root

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.autodev.developer_request import DeveloperRequest


@dataclass(frozen=True)
class ImplementationExecutionPolicy:
    auto_approve: bool = False
    auto_rollback: bool = True
    allow_code_generation: bool = True
    allowed_categories: tuple[str, ...] = (
        "implementation",
        "integration",
        "refactor",
        "bugfix",
        "maintenance",
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_IMPLEMENTATION_EXECUTION_SERVICE = ImplementationExecutionService()


class ImplementationExecutor:
    """Safely hands a scheduled code task to the AutoDev pipeline."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        developer_controller: object | None = None,
        developer_agent: object | None = None,
        policy: ImplementationExecutionPolicy | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
            or default_project_root()
        ).expanduser().resolve(
            strict=False
        )
        self._developer_controller = developer_controller
        self._developer_agent = developer_agent
        self.policy = (
            policy
            or ImplementationExecutionPolicy()
        )

    def execute(self, scheduled_task: dict[str, Any] | object, *, auto_approve: bool | None=None, auto_rollback: bool | None=None) -> dict[str, Any]:
        return _IMPLEMENTATION_EXECUTION_SERVICE.execute(self, scheduled_task, auto_approve=auto_approve, auto_rollback=auto_rollback)


    @property
    def developer_controller(self) -> object:
        if self._developer_controller is None:
            from app.autodev.developer_controller import (
                DeveloperController,
            )

            self._developer_controller = (
                DeveloperController(
                    project_root=str(
                        self.project_root
                    )
                )
            )

        return self._developer_controller

    @property
    def developer_agent(self) -> object:
        if self._developer_agent is None:
            from app.autodev.developer_agent import (
                DeveloperAgent,
            )

            self._developer_agent = (
                DeveloperAgent(
                    project_root=str(
                        self.project_root
                    )
                )
            )

        return self._developer_agent

    def _generate_proposal(
        self,
        *,
        target: str,
        goal: str,
        normalized: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        task_data = {
            **payload,
            "task_id": normalized.get(
                "task_id",
                payload.get("task_id", ""),
            ),
            "title": normalized.get(
                "title",
                payload.get("title", ""),
            ),
            "description": goal,
            "target": target,
            "metadata": {
                **dict(
                    payload.get(
                        "metadata",
                        {},
                    )
                    or {}
                ),
                "acceptance_criteria": list(
                    payload.get(
                        "acceptance_criteria",
                        [],
                    )
                    or []
                ),
            },
        }

        try:
            proposal = (
                self.developer_agent
                .generate_code_proposal(
                    target=target,
                    goal=goal,
                    task=task_data,
                )
            )
        except Exception as error:
            return {
                "used": True,
                "success": False,
                "strategy": "DEVELOPER_AGENT",
                "proposed_content": "",
                "errors": [
                    (
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
            }

        proposal = (
            dict(proposal)
            if isinstance(proposal, dict)
            else {}
        )

        return {
            "used": True,
            "success": bool(
                proposal.get(
                    "success",
                    False,
                )
            ),
            "strategy": str(
                proposal.get(
                    "strategy",
                    "DEVELOPER_AGENT",
                )
            ),
            "proposed_content": str(
                proposal.get(
                    "proposed_content",
                    "",
                )
            ),
            "warnings": list(
                proposal.get(
                    "warnings",
                    [],
                )
                or []
            ),
            "errors": list(
                proposal.get(
                    "errors",
                    [],
                )
                or []
            ),
        }

    def _category_allowed(
        self,
        category: str,
    ) -> bool:
        normalized = category or "implementation"

        return normalized in {
            item.lower()
            for item in self.policy.allowed_categories
        }

    def _validate_target(
        self,
        file_path: Path,
    ) -> str:
        resolved = file_path.resolve(
            strict=False
        )

        try:
            relative = resolved.relative_to(
                self.project_root
            )
        except ValueError:
            return (
                "Plik docelowy znajduje się poza "
                "projektem JARVIS OS."
            )

        normalized = str(
            relative
        ).replace(
            "\\",
            "/",
        ).casefold()

        protected = (
            ".git/",
            ".venv/",
            "archive/",
            "backups/",
            "data/backups/",
            "ai_pliki/",
        )

        if any(
            normalized.startswith(item)
            for item in protected
        ):
            return (
                "Plik docelowy znajduje się "
                "w chronionym obszarze projektu."
            )

        if resolved.suffix.casefold() != ".py":
            return (
                "Autonomiczne tworzenie plików "
                "obsługuje obecnie wyłącznie Python."
            )

        if (
            resolved.exists()
            and not resolved.is_file()
        ):
            return (
                "Ścieżka docelowa nie jest plikiem."
            )

        return ""

    @staticmethod
    def _prepare_new_file(
        file_path: Path,
    ) -> str:
        try:
            file_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            file_path.write_text(
                "",
                encoding="utf-8",
            )
            return ""
        except Exception as error:
            return (
                f"{type(error).__name__}: "
                f"{error}"
            )

    @staticmethod
    def _cleanup_new_file(
        file_path: Path,
        created_new_file: bool,
    ) -> None:
        if not created_new_file:
            return

        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            raise RuntimeError("AutoDev: przechwycony wyjątek")

    def _target_path(
        self,
        normalized: dict[str, Any],
        payload: dict[str, Any],
    ) -> str:
        metadata = dict(
            payload.get(
                "metadata",
                {},
            )
            or {}
        )

        candidates = (
            payload.get("path"),
            payload.get("target"),
            payload.get("target_path"),
            payload.get("file_path"),
            normalized.get("path"),
            normalized.get("target"),
            normalized.get("target_path"),
            normalized.get("file_path"),
            metadata.get("path"),
            metadata.get("target"),
            metadata.get("target_path"),
            metadata.get("file_path"),
        )

        for candidate in candidates:
            value = str(
                candidate or ""
            ).strip()

            if value:
                return str(
                    self._resolve_path(
                        value
                    )
                )

        return ""

    def _resolve_path(
        self,
        value: str,
    ) -> Path:
        path = Path(value).expanduser()

        if not path.is_absolute():
            path = self.project_root / path

        return path.resolve(
            strict=False
        )

    @staticmethod
    def _goal(
        normalized: dict[str, Any],
        payload: dict[str, Any],
    ) -> str:
        return str(
            payload.get(
                "description",
                normalized.get(
                    "description",
                    normalized.get(
                        "title",
                        payload.get(
                            "objective",
                            "Wykonaj zadanie implementacyjne.",
                        ),
                    ),
                ),
            )
        ).strip()

    @staticmethod
    def _proposed_content(
        normalized: dict[str, Any],
        payload: dict[str, Any],
    ) -> str:
        metadata = dict(
            payload.get(
                "metadata",
                {},
            )
            or {}
        )

        candidates = (
            payload.get("proposed_content"),
            payload.get("new_content"),
            normalized.get("proposed_content"),
            normalized.get("new_content"),
            metadata.get("proposed_content"),
            metadata.get("new_content"),
        )

        for candidate in candidates:
            if candidate is None:
                continue

            value = str(candidate)

            if value:
                return value

        return ""

    @staticmethod
    def _payload(
        normalized: dict[str, Any],
    ) -> dict[str, Any]:
        payload = normalized.get(
            "payload",
            {},
        )

        return (
            dict(payload)
            if isinstance(payload, dict)
            else {}
        )

    @staticmethod
    def _normalize_task(
        scheduled_task: dict[str, Any] | object,
    ) -> dict[str, Any]:
        if isinstance(
            scheduled_task,
            dict,
        ):
            return dict(
                scheduled_task
            )

        to_dict = getattr(
            scheduled_task,
            "to_dict",
            None,
        )

        if callable(to_dict):
            value = to_dict()

            if isinstance(value, dict):
                return dict(value)

        return {}

    @staticmethod
    def _request_metadata(
        *,
        normalized: dict[str, Any],
        payload: dict[str, Any],
        generation: dict[str, Any],
    ) -> dict[str, str]:
        return {
            "source": "implementation_executor",
            "task_id": str(
                normalized.get(
                    "task_id",
                    payload.get("task_id", ""),
                )
            ),
            "category": str(
                normalized.get(
                    "category",
                    payload.get("category", ""),
                )
            ),
            "generation_strategy": str(
                generation.get(
                    "strategy",
                    "",
                )
            ),
        }

    @staticmethod
    def _workflow_dict(
        workflow_result: object,
    ) -> dict[str, Any]:
        if isinstance(
            workflow_result,
            dict,
        ):
            return dict(
                workflow_result
            )

        as_dict = getattr(
            workflow_result,
            "as_dict",
            None,
        )

        if callable(as_dict):
            value = as_dict()

            if isinstance(value, dict):
                return dict(value)

        return {
            "success": bool(
                getattr(
                    workflow_result,
                    "success",
                    False,
                )
            ),
            "status": str(
                getattr(
                    workflow_result,
                    "status",
                    "",
                )
            ),
            "message": str(
                getattr(
                    workflow_result,
                    "message",
                    "",
                )
            ),
        }

    @staticmethod
    def _status(
        workflow_status: str,
    ) -> str:
        mapping = {
            "waiting_for_approval": "PREVIEW_READY",
            "approved": "APPROVED",
            "completed": "COMPLETED",
            "failed_and_rolled_back": (
                "FAILED_AND_ROLLED_BACK"
            ),
            "failed": "FAILED",
        }

        return mapping.get(
            workflow_status,
            workflow_status.upper()
            or "UNKNOWN",
        )

    @staticmethod
    def _failure(
        *,
        status: str,
        error: str,
        task: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "task_id": str(
                (task or {}).get(
                    "task_id",
                    "",
                )
            ),
            "errors": [
                str(error)
            ],
            **dict(extra or {}),
        }
