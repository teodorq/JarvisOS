from __future__ import annotations

from typing import Any

from app.autodev.change_impact import ChangeImpactAnalyzer
from app.autodev.dependency_graph import DependencyGraph
from app.autodev.developer_loop import DeveloperLoop


class DeveloperAgent:

    def __init__(self) -> None:
        self.graph = DependencyGraph()
        self.impact = ChangeImpactAnalyzer()
        self.loop = DeveloperLoop()

    def build_dependency_graph(self) -> str:
        self.graph.build()
        return self.graph.summary_text()

    def analyze_symbol_impact(
        self,
        symbol_name: str,
    ):
        return self.impact.analyze_symbol(
            symbol_name
        )

    def analyze_module_impact(
        self,
        module_name: str,
    ):
        return self.impact.analyze_module(
            module_name
        )

    def plan_symbol_change(
        self,
        symbol_name: str,
    ) -> str:

        if not self.graph.files:
            self.graph.build()

        impact = self.graph.impact_for_symbol(
            symbol_name
        )

        files = impact.get("files", [])
        references_count = impact.get(
            "references_count",
            0,
        )

        lines = [
            "AUTODEV CHANGE PLAN",
            f"Cel: zmiana symbolu {symbol_name}",
            f"Pliki zależne: {len(files)}",
            f"Referencje: {references_count}",
            "",
            "Plan:",
            "1. Utworzyć backup zmienianych plików.",
            f"2. Zmodyfikować symbol: {symbol_name}.",
            "3. Sprawdzić pliki zależne.",
            "4. Uruchomić test importów.",
            "5. Uruchomić kontrolę składni.",
            "6. Cofnąć zmiany, jeśli test nie przejdzie.",
        ]

        if files:
            lines.append("")
            lines.append("Pliki do sprawdzenia:")

            for path in files[:30]:
                lines.append(f"- {path}")

        return "\n".join(lines)

    def prepare_developer_task(
        self,
        goal_text: str,
        target: str,
    ) -> str:

        return self.loop.prepare(
            goal_text=goal_text,
            target=target,
        )

    def prepare_planned_task(
        self,
        task: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(task, dict):
            raise TypeError(
                "Planowane zadanie musi być słownikiem."
            )

        task_id = str(
            task.get("task_id", "")
        ).strip()

        title = str(
            task.get("title", "")
        ).strip()

        description = str(
            task.get("description", "")
        ).strip()

        recommendation = str(
            task.get("recommendation", "")
        ).strip()

        target = str(
            task.get("target", "")
        ).strip()

        goal = description or title

        if recommendation:
            goal = (
                f"{goal} Zalecenie: {recommendation}"
            ).strip()

        if not goal:
            raise ValueError(
                "Planowane zadanie nie posiada celu."
            )

        if not target:
            raise ValueError(
                "Planowane zadanie nie posiada targetu."
            )

        report = self.prepare_developer_task(
            goal_text=goal,
            target=target,
        )

        return {
            "success": True,
            "status": "PLAN_PREPARED",
            "task_id": task_id,
            "goal": goal,
            "target": target,
            "priority_score": task.get(
                "priority_score",
                0.0,
            ),
            "severity": task.get(
                "severity",
                "MEDIUM",
            ),
            "report": report,
        }
