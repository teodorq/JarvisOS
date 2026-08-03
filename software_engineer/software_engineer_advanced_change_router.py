from __future__ import annotations

import re
from typing import Any

from .software_engineer_campaign_router import (
    SoftwareEngineerCampaignRouter,
)
from .software_engineer_learning_router import (
    SoftwareEngineerLearningRouter,
)


_CAMPAIGN_ROUTER = SoftwareEngineerCampaignRouter()
_LEARNING_ROUTER = SoftwareEngineerLearningRouter()


class SoftwareEngineerAdvancedChangeRouter:
    """Routes cross-module and existing multi-file refactor requests."""

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        learning = _LEARNING_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )

        if learning is not None:
            return learning

        campaign = _CAMPAIGN_ROUTER.try_handle(
            controller,
            command=command,
            objective=objective,
            context=context,
        )

        if campaign is not None:
            return campaign

        if self._is_cross_module(
            controller,
            command=command,
            context=context,
        ):
            return self._handle_cross_module(
                controller,
                command=command,
                objective=objective,
                context=context,
            )

        if self._is_refactor(
            controller,
            command=command,
            context=context,
        ):
            return self._handle_refactor(
                controller,
                command=command,
                objective=objective,
                context=context,
            )

        return None

    @staticmethod
    def _operation(
        context: dict[str, Any],
    ) -> str:
        return str(
            context.get(
                "operation",
                context.get("mode", ""),
            )
        ).strip().casefold()

    def _is_cross_module(
        self,
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> bool:
        operation = self._operation(context)

        if (
            context.get("cross_module") is True
            or operation in {
                "cross_module",
                "cross_module_change",
                "multi_module_change",
            }
        ):
            return True

        normalized = controller._normalize(command)

        return any(
            phrase in normalized
            for phrase in (
                "zmiana między modułami",
                "zmianę między modułami",
                "zmiane miedzy modulami",
                "zmiana miedzy modulami",
                "zmień moduły autonomicznie",
                "zmien moduly autonomicznie",
                "cross module change",
                "cross-module change",
            )
        )

    def _is_refactor(
        self,
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> bool:
        operation = self._operation(context)

        if (
            context.get("refactor_existing") is True
            or operation in {
                "refactor",
                "multi_file_refactor",
            }
        ):
            return True

        normalized = controller._normalize(command)

        return any(
            phrase in normalized
            for phrase in (
                "zrefaktoryzuj",
                "zmodyfikuj wieloplikowo",
                "multi file refactor",
                "refactor multi file",
            )
        )

    def _handle_cross_module(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        replacements = self._replacements(context)
        targets = self._targets(
            command,
            context,
        )

        if replacements is None and len(targets) < 2:
            return {
                "success": False,
                "status": "CROSS_MODULE_TARGETS_REQUIRED",
                "objective": objective,
                "errors": [
                    "Podaj co najmniej dwa pliki z różnych "
                    "podsystemów w context['targets'] albo "
                    "pełne zawartości w context['replacements'].",
                ],
            }

        return controller.cross_module_workflow.run(
            objective,
            replacements=replacements,
            targets=targets,
            proposal_metadata=dict(
                context.get(
                    "proposal_metadata",
                    {},
                )
                or {}
            ),
            auto_execute=bool(
                context.get("auto_execute", True)
            ),
            auto_approve=bool(
                context.get("auto_approve", False)
            ),
            auto_rollback=bool(
                context.get("auto_rollback", True)
            ),
            allow_public_symbol_removal=bool(
                context.get(
                    "allow_public_symbol_removal",
                    False,
                )
            ),
            allow_same_subsystem=bool(
                context.get(
                    "allow_same_subsystem",
                    False,
                )
            ),
            required_subsystems=self._required_subsystems(
                context
            ),
        )

    def _handle_refactor(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        replacements = self._replacements(context)
        targets = self._targets(command, context)

        if replacements is None and len(targets) < 2:
            return {
                "success": False,
                "status": "REFACTOR_TARGETS_REQUIRED",
                "objective": objective,
                "errors": [
                    "Podaj co najmniej dwa pliki Python "
                    "w context['targets'] albo pełne "
                    "zawartości w context['replacements'].",
                ],
            }

        return controller.multi_file_refactor_workflow.run(
            objective,
            replacements=replacements,
            targets=targets,
            proposal_metadata=dict(
                context.get(
                    "proposal_metadata",
                    {},
                )
                or {}
            ),
            auto_execute=bool(
                context.get("auto_execute", True)
            ),
            auto_approve=bool(
                context.get("auto_approve", False)
            ),
            auto_rollback=bool(
                context.get("auto_rollback", True)
            ),
            allow_public_symbol_removal=bool(
                context.get(
                    "allow_public_symbol_removal",
                    False,
                )
            ),
        )

    @staticmethod
    def _replacements(
        context: dict[str, Any],
    ) -> dict[str, str] | None:
        values = context.get("replacements")

        if not isinstance(values, dict) or len(values) < 2:
            return None

        return {
            str(path): str(content)
            for path, content in values.items()
        }

    @staticmethod
    def _targets(
        command: str,
        context: dict[str, Any],
    ) -> list[str]:
        raw = context.get(
            "targets",
            context.get("target_paths", []),
        )

        if isinstance(raw, (str, bytes)):
            raw = [raw]

        targets = [
            str(value)
            for value in (
                raw
                if isinstance(
                    raw,
                    (list, tuple, set),
                )
                else []
            )
            if str(value).strip()
        ]

        if len(targets) < 2:
            targets = list(
                dict.fromkeys(
                    re.findall(
                        r"[A-Za-z0-9_./\\-]+\.py",
                        str(command),
                    )
                )
            )

        return targets

    @staticmethod
    def _required_subsystems(
        context: dict[str, Any],
    ) -> list[str]:
        values = context.get(
            "required_subsystems",
            [],
        )

        if isinstance(values, (str, bytes)):
            values = [values]

        return [
            str(value)
            for value in values
            if str(value).strip()
        ]
