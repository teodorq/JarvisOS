from app.ai.commands.base_command import BaseCommand


class AutoDevCommand(BaseCommand):

    def parse(self, command: str):

        if command in [
            "zbuduj graf projektu",
            "zbuduj graf zależności",
            "zbuduj graf zaleznosci",
            "graf projektu"
        ]:
            return self._action("BUILD_DEPENDENCY_GRAPH")

        if command.startswith("wpływ modułu "):
            target = command.replace(
                "wpływ modułu",
                "",
                1
            ).strip()

            return self._action(
                "ANALYZE_MODULE_IMPACT",
                target=target
            )

        if command.startswith("wplyw modulu "):
            target = command.replace(
                "wplyw modulu",
                "",
                1
            ).strip()

            return self._action(
                "ANALYZE_MODULE_IMPACT",
                target=target
            )

        if command.startswith("wpływ "):
            target = command.replace(
                "wpływ",
                "",
                1
            ).strip()

            return self._action(
                "ANALYZE_SYMBOL_IMPACT",
                target=target
            )

        if command.startswith("wplyw "):
            target = command.replace(
                "wplyw",
                "",
                1
            ).strip()

            return self._action(
                "ANALYZE_SYMBOL_IMPACT",
                target=target
            )

        if command.startswith("plan zmiany "):
            target = command.replace(
                "plan zmiany",
                "",
                1
            ).strip()

            return self._action(
                "PLAN_SYMBOL_CHANGE",
                target=target
            )

        if command.startswith("przygotuj zmianę "):
            target = command.replace(
                "przygotuj zmianę",
                "",
                1
            ).strip()

            return self._action(
                "PREPARE_DEVELOPER_TASK",
                target=target,
                text=f"Przygotować zmianę symbolu {target}"
            )

        if command.startswith("przygotuj zmiane "):
            target = command.replace(
                "przygotuj zmiane",
                "",
                1
            ).strip()

            return self._action(
                "PREPARE_DEVELOPER_TASK",
                target=target,
                text=f"Przygotować zmianę symbolu {target}"
            )

        if command.startswith("zadanie deweloperskie "):
            raw = command.replace(
                "zadanie deweloperskie",
                "",
                1
            ).strip()

            target, goal_text = self._split_target_and_goal(raw)

            return self._action(
                "PREPARE_DEVELOPER_TASK",
                target=target,
                text=goal_text
            )

        return None

    def _split_target_and_goal(self, raw: str):
        if ":" in raw:
            target, goal_text = raw.split(":", 1)

            return (
                target.strip(),
                goal_text.strip()
            )

        return (
            raw.strip(),
            f"Przygotować zmianę symbolu {raw.strip()}"
        )

    def _action(
        self,
        action_type,
        target="",
        text="",
        url="",
        query=""
    ):
        return {
            "action_type": action_type,
            "target": target,
            "text": text,
            "url": url,
            "query": query
        }