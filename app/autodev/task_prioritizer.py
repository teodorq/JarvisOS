from __future__ import annotations

from typing import Any

from app.autodev.problem_detector import (
    DetectedProblem,
)


class TaskPrioritizer:

    SEVERITY_SCORE = {
        "CRITICAL": 100.0,
        "HIGH": 75.0,
        "MEDIUM": 50.0,
        "LOW": 25.0,
    }

    def calculate_score(
        self,
        problem: DetectedProblem,
        context: dict[str, Any] | None = None,
    ) -> float:

        context = dict(
            context
            or {}
        )

        score = self.SEVERITY_SCORE.get(
            problem.severity.upper(),
            0.0,
        )

        score += float(
            problem.score
        )

        if context.get(
            "test_failure"
        ):
            score += 25.0

        if context.get(
            "startup_failure"
        ):
            score += 30.0

        if context.get(
            "security_related"
        ):
            score += 35.0

        if context.get(
            "user_blocking"
        ):
            score += 20.0

        if context.get(
            "recent_regression"
        ):
            score += 15.0

        effort = float(
            context.get(
                "estimated_effort",
                5.0,
            )
        )

        score -= min(
            max(
                effort,
                0.0,
            ),
            20.0,
        )

        return round(
            score,
            2,
        )

    def prioritize(
        self,
        problems: list[
            DetectedProblem
        ],
        context_by_module: dict[
            str,
            dict[str, Any]
        ] | None = None,
    ) -> list[
        DetectedProblem
    ]:

        contexts = context_by_module or {}

        return sorted(
            problems,
            key=lambda problem: self.calculate_score(
                problem,
                contexts.get(
                    problem.module,
                    {},
                ),
            ),
            reverse=True,
        )

    def build_task(
        self,
        problem: DetectedProblem,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        priority_score = self.calculate_score(
            problem,
            context,
        )

        return {
            "title": problem.title,
            "description": problem.description,
            "target": problem.module,
            "recommendation": problem.recommendation,
            "severity": problem.severity,
            "priority_score": priority_score,
            "source": "TaskPrioritizer",
            "metadata": {
                **dict(
                    problem.metadata
                ),
                "problem_score": problem.score,
            },
        }
