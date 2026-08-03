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

        if action == "versions":
            return engine.versions(
                limit=self._bounded_int(
                    context.get("limit", 20),
                    minimum=1,
                    maximum=200,
                )
            )

        if action == "rollback_profile":
            return engine.rollback_profile()

        if action == "activate_profile":
            return engine.activate_profile(
                str(
                    context.get(
                        "profile_version_id",
                        self._extract_version_id(command),
                    )
                ).strip(),
                force=bool(context.get("force", False)),
            )

        if action in {"auto_on", "auto_off", "configure_auto"}:
            return engine.configure_auto_training(
                enabled=(
                    True
                    if action == "auto_on"
                    else False
                    if action == "auto_off"
                    else context.get("auto_training_enabled")
                ),
                minimum_observations=context.get(
                    "minimum_observations"
                ),
                minimum_new_episodes=context.get(
                    "minimum_new_episodes"
                ),
                minimum_confidence=context.get(
                    "minimum_confidence"
                ),
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
                "uczenie autonomiczne",
                "uczenia autonomicznego",
                "status uczenia autonomicznego",
                "historia uczenia autonomicznego",
                "profil uczenia autonomicznego",
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
                "wersje profilu uczenia",
                "historia wersji profilu",
                "cofnij profil uczenia",
                "aktywuj profil uczenia",
                "automatyczny trening",
                "automatyczne uczenie",
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
            "profile_versions": "versions",
            "versions": "versions",
            "rollback": "rollback_profile",
            "rollback_profile": "rollback_profile",
            "activate": "activate_profile",
            "activate_profile": "activate_profile",
            "enable_auto": "auto_on",
            "disable_auto": "auto_off",
            "configure_auto": "configure_auto",
        }
        explicit = aliases.get(explicit, explicit)
        if explicit in {
            "learn",
            "apply",
            "status",
            "profile",
            "history",
            "explain",
            "versions",
            "rollback_profile",
            "activate_profile",
            "auto_on",
            "auto_off",
            "configure_auto",
        }:
            return explicit

        normalized = controller._normalize(command)

        if any(
            phrase in normalized
            for phrase in (
                "wersje profilu uczenia",
                "historia wersji profilu",
                "profile versions",
            )
        ):
            return "versions"

        if any(
            phrase in normalized
            for phrase in (
                "cofnij profil uczenia",
                "przywróć poprzedni profil",
                "przywroc poprzedni profil",
                "rollback learning profile",
            )
        ):
            return "rollback_profile"

        if any(
            phrase in normalized
            for phrase in (
                "aktywuj wersję profilu",
                "aktywuj wersje profilu",
                "activate profile version",
            )
        ):
            return "activate_profile"

        if any(
            phrase in normalized
            for phrase in (
                "włącz automatyczny trening",
                "wlacz automatyczny trening",
                "włącz automatyczne uczenie",
                "enable automatic training",
            )
        ):
            return "auto_on"

        if any(
            phrase in normalized
            for phrase in (
                "wyłącz automatyczny trening",
                "wylacz automatyczny trening",
                "wyłącz automatyczne uczenie",
                "disable automatic training",
            )
        ):
            return "auto_off"

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
                "wersje profilu uczenia",
                "historia wersji profilu",
                "profile versions",
            )
        ):
            return "versions"

        if any(
            phrase in normalized
            for phrase in (
                "cofnij profil uczenia",
                "przywróć poprzedni profil",
                "przywroc poprzedni profil",
                "rollback learning profile",
            )
        ):
            return "rollback_profile"

        if any(
            phrase in normalized
            for phrase in (
                "aktywuj wersję profilu",
                "aktywuj wersje profilu",
                "activate profile version",
            )
        ):
            return "activate_profile"

        if any(
            phrase in normalized
            for phrase in (
                "włącz automatyczny trening",
                "wlacz automatyczny trening",
                "włącz automatyczne uczenie",
                "enable automatic training",
            )
        ):
            return "auto_on"

        if any(
            phrase in normalized
            for phrase in (
                "wyłącz automatyczny trening",
                "wylacz automatyczny trening",
                "wyłącz automatyczne uczenie",
                "disable automatic training",
            )
        ):
            return "auto_off"

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
    def _extract_version_id(command: str) -> str:
        match = re.search(
            r"(profile-[a-fA-F0-9]{8,64})",
            str(command),
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
