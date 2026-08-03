from __future__ import annotations

import re
from typing import Any

from .full_autonomy_workflow import FullAutonomyWorkflow


class SoftwareEngineerFullAutonomyRouter:
    """Routes one-large-goal end-to-end autonomy commands."""

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self._is_full_autonomy(
            controller,
            command=command,
            context=context,
        ):
            return None

        workflow = getattr(
            controller,
            "full_autonomy_workflow",
            None,
        )
        if workflow is None:
            workflow = FullAutonomyWorkflow(
                controller.project_root
            )
            controller.full_autonomy_workflow = workflow

        action = self._action(
            controller,
            command=command,
            context=context,
        )
        run_id = self._run_id(
            command=command,
            context=context,
        )

        if action == "recent":
            return workflow.recent(
                limit=max(1, int(context.get("limit", 20)))
            )
        if action in {
            "status",
            "resume",
            "execute",
            "pause",
            "rollback",
        } and not run_id:
            return self._id_required()
        if action == "status":
            return workflow.status(run_id)
        if action == "execute":
            return workflow.execute(
                run_id,
                context=context,
            )
        if action == "resume":
            return workflow.resume(
                run_id,
                context=context,
            )
        if action == "pause":
            return workflow.pause(run_id)
        if action == "rollback":
            return workflow.rollback(run_id)

        values = dict(context)
        if action == "plan":
            values["plan_only"] = True
            values["auto_execute"] = False
        return workflow.run(
            objective,
            context=values,
        )

    @staticmethod
    def _is_full_autonomy(
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> bool:
        operation = str(
            context.get(
                "operation",
                context.get("mode", ""),
            )
        ).strip().casefold()
        if context.get("full_autonomy") is True or operation in {
            "full_autonomy",
            "large_goal_autonomy",
            "end_to_end_autonomy",
            "autonomous_goal",
        }:
            return True
        normalized = controller._normalize(command)
        return any(
            phrase in normalized
            for phrase in (
                "pełna autonomia",
                "pełną autonomię",
                "pełnej autonomii",
                "pelna autonomia",
                "pelna autonomie",
                "pelnej autonomii",
                "pełny test autonomii",
                "pelny test autonomii",
                "duży cel autonomicznie",
                "duzy cel autonomicznie",
                "full autonomy",
                "end to end autonomy",
                "one large goal",
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
                "full_autonomy_action",
                context.get("action", ""),
            )
        ).strip().casefold()
        mapping = {
            "start": "start",
            "run": "start",
            "execute": "execute",
            "wykonaj": "execute",
            "start_existing": "execute",
            "pause": "pause",
            "pauza": "pause",
            "zatrzymaj": "pause",
            "progress": "status",
            "postęp": "status",
            "postep": "status",
            "plan": "plan",
            "preview": "plan",
            "status": "status",
            "get": "status",
            "resume": "resume",
            "wznów": "resume",
            "wznow": "resume",
            "rollback": "rollback",
            "cofnij": "rollback",
            "recent": "recent",
            "list": "recent",
        }
        if explicit in mapping:
            return mapping[explicit]
        normalized = controller._normalize(command)
        phrases = (
            ("recent", ("historia pełnej autonomii", "recent autonomy runs")),
            (
                "status",
                (
                    "status pełnej autonomii",
                    "postęp pełnej autonomii",
                    "postep pelnej autonomii",
                    "full autonomy status",
                ),
            ),
            (
                "execute",
                (
                    "wykonaj zaplanowaną pełną autonomię",
                    "wykonaj zaplanowana pelna autonomie",
                    "uruchom zaplanowaną pełną autonomię",
                    "execute planned full autonomy",
                ),
            ),
            (
                "pause",
                (
                    "wstrzymaj pełną autonomię",
                    "zatrzymaj pełną autonomię",
                    "pause full autonomy",
                ),
            ),
            ("resume", ("wznów pełną autonomię", "resume full autonomy")),
            ("rollback", ("cofnij pełną autonomię", "rollback full autonomy")),
            ("plan", ("zaplanuj pełną autonomię", "plan full autonomy")),
        )
        for action, values in phrases:
            if any(value in normalized for value in values):
                return action
        return "start"

    @staticmethod
    def _run_id(
        *,
        command: str,
        context: dict[str, Any],
    ) -> str:
        explicit = str(
            context.get(
                "autonomy_run_id",
                context.get("run_id", ""),
            )
        ).strip()
        if explicit:
            return explicit

        match = re.search(
            r"\bautonomy-[A-Za-z0-9_-]+\b",
            str(command),
            flags=re.IGNORECASE,
        )
        return (
            match.group(0)
            if match is not None
            else ""
        )

    @staticmethod
    def _id_required() -> dict[str, Any]:
        return {
            "success": False,
            "status": "FULL_AUTONOMY_RUN_ID_REQUIRED",
            "operation": "full_autonomy",
            "autonomy_run_id": "",
            "autonomy_run": {},
            "errors": ["Podaj autonomy_run_id."],
        }
