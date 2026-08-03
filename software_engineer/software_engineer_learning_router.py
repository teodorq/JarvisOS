from __future__ import annotations

import re
from typing import Any

from .autonomous_learning_engine import AutonomousLearningEngine


class SoftwareEngineerLearningRouter:
    """Routes autonomous learning commands and context operations."""

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self._is_learning(
            controller,
            command=command,
            context=context,
        ):
            return None

        engine = getattr(
            controller,
            "autonomous_learning_engine",
            None,
        )
        if engine is None:
            engine = AutonomousLearningEngine(
                controller.project_root
            )

        action = self._action(
            controller,
            command=command,
            context=context,
        )

        if action == "status":
            return engine.status()

        if action == "profile":
            return engine.profile()

        if action == "history":
            return engine.history(
                limit=self._bounded_int(
                    context.get("limit", 20),
                    minimum=1,
                    maximum=200,
                )
            )

        if action == "explain":
            return engine.explain(
                signature=str(
                    context.get("signature", "")
                ).strip(),
                subsystem=str(
                    context.get(
                        "subsystem",
                        self._extract_subsystem(command),
                    )
                ).strip(),
            )

        apply = bool(
            context.get(
                "apply_learning",
                action == "apply",
            )
        )
        return engine.learn(
            limit=self._bounded_int(
                context.get("limit", 500),
                minimum=1,
                maximum=5000,
            ),
            apply=apply,
        )

    def _is_learning(
        self,
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

        if (
            context.get("autonomous_learning") is True
            or operation in {
                "autonomous_learning",
                "autonomy_learning",
                "learning_engine",
                "history_learning",
            }
        ):
            return True

        normalized = controller._normalize(command)
        return any(
            phrase in normalized
            for phrase in (
                "uczenie autonomii",
                "uczenia autonomii",
                "naucz jarvisa",
                "naucz jarvis-a",
                "naucz się z historii",
                "naucz sie z historii",
                "ucz się z historii",
                "ucz sie z historii",
                "historia autonomii",
                "profil uczenia",
                "status uczenia",
                "zastosuj naukę",
                "zastosuj nauke",
                "autonomous learning",
                "learn from autonomy history",
                "learning profile",
            )
        )

    def _action(
        self,
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> str:
        explicit = str(
            context.get(
                "learning_action",
                context.get("action", ""),
            )
        ).strip().casefold()
        aliases = {
            "train": "learn",
            "analyse": "learn",
            "analyze": "learn",
            "apply_profile": "apply",
            "show_profile": "profile",
            "recent": "history",
        }
        explicit = aliases.get(explicit, explicit)
        if explicit in {
            "learn",
            "apply",
            "status",
            "profile",
            "history",
            "explain",
        }:
            return explicit

        normalized = controller._normalize(command)

        if any(
            phrase in normalized
            for phrase in (
                "status uczenia",
                "status nauki",
                "learning status",
            )
        ):
            return "status"

        if any(
            phrase in normalized
            for phrase in (
                "profil uczenia",
                "profil nauki",
                "learning profile",
            )
        ):
            return "profile"

        if any(
            phrase in normalized
            for phrase in (
                "historia uczenia",
                "historia nauki",
                "ostatnie uczenie",
                "learning history",
            )
        ):
            return "history"

        if any(
            phrase in normalized
            for phrase in (
                "wyjaśnij naukę",
                "wyjasnij nauke",
                "wyjaśnij decyzję uczenia",
                "explain learning",
            )
        ):
            return "explain"

        if any(
            phrase in normalized
            for phrase in (
                "zastosuj naukę",
                "zastosuj nauke",
                "aktywuj profil uczenia",
                "apply learning",
                "apply learning profile",
            )
        ):
            return "apply"

        return "learn"

    @staticmethod
    def _extract_subsystem(command: str) -> str:
        match = re.search(
            r"(?:podsystem(?:u|ie)?|subsystem)\s+([A-Za-z0-9_.-]+)",
            str(command),
            flags=re.IGNORECASE,
        )
        return match.group(1) if match else ""

    @staticmethod
    def _bounded_int(
        value: Any,
        *,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = minimum
        return max(minimum, min(maximum, number))
