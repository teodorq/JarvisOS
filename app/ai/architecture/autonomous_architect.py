from __future__ import annotations

from pathlib import Path
from typing import Any

from .refactor_plan_engine import RefactorPlanEngine


class AutonomousArchitect:

    def __init__(
        self,
        project_root: str | Path,
        *,
        source_root: str = "app",
        evolution_controller: object | None = None,
        director_controller: object | None = None,
        task_queue: object | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.source_root = source_root
        self.evolution_controller = evolution_controller
        self.director_controller = director_controller
        self.task_queue = task_queue

        self.plan_engine = RefactorPlanEngine(
            project_root=self.project_root,
            source_root=source_root,
        )

    def analyze_and_plan(
        self,
        *,
        enqueue: bool = False,
        limit: int = 10,
    ) -> dict[str, Any]:
        report = self.plan_engine.build()
        blueprints = list(
            report.get("blueprints", [])
        )[: max(1, int(limit))]

        ranked = self._rank_blueprints(blueprints)
        result: dict[str, Any] = {
            "success": True,
            "status": "ANALYZED",
            "architecture_score": report.get(
                "architecture_score",
                100.0,
            ),
            "smell_score": report.get(
                "smell_score",
                100.0,
            ),
            "blueprints": ranked,
            "recommended_count": len(ranked),
        }

        result["evolution"] = self._send_to_evolution(
            ranked,
        )
        result["director"] = self._send_to_director(
            ranked,
        )

        if enqueue:
            result["autodev_queue"] = self.enqueue_blueprints(
                ranked,
            )

        return result

    def enqueue_blueprints(
        self,
        blueprints: list[dict[str, Any]],
    ) -> dict[str, Any]:
        queue = self.task_queue

        if queue is None:
            return {
                "success": False,
                "status": "QUEUE_UNAVAILABLE",
                "created": 0,
                "duplicates": 0,
            }

        creator = getattr(
            queue,
            "create_unique_task",
            None,
        )
        if not callable(creator):
            return {
                "success": False,
                "status": "QUEUE_INCOMPATIBLE",
                "created": 0,
                "duplicates": 0,
            }

        created = 0
        duplicates = 0
        task_ids: list[str] = []

        for blueprint in blueprints:
            title = str(
                blueprint.get(
                    "title",
                    "Autonomous architecture refactor",
                )
            )
            objective = str(
                blueprint.get(
                    "objective",
                    "Improve project architecture.",
                )
            )
            priority_name = str(
                blueprint.get(
                    "priority",
                    "medium",
                )
            ).lower()

            priority = self._resolve_priority(
                queue=queue,
                priority_name=priority_name,
            )

            task, was_created = creator(
                title=title,
                description=objective,
                source="autonomous_architect",
                priority=priority,
                payload={
                    "type": "architecture_refactor",
                    "blueprint": blueprint,
                    "roi": blueprint.get(
                        "estimated_roi",
                        0.0,
                    ),
                    "risk": blueprint.get(
                        "estimated_risk",
                        1.0,
                    ),
                    "architecture_score": (
                        blueprint.get(
                            "architecture_score"
                        )
                    ),
                },
                tags=[
                    "architecture",
                    "refactor",
                    "autonomous",
                ],
            )

            task_id = str(
                getattr(task, "task_id", "")
            )
            if task_id:
                task_ids.append(task_id)

            if was_created:
                created += 1
            else:
                duplicates += 1

        return {
            "success": True,
            "status": "QUEUED",
            "created": created,
            "duplicates": duplicates,
            "task_ids": task_ids,
        }

    def _send_to_evolution(
        self,
        blueprints: list[dict[str, Any]],
    ) -> dict[str, Any]:
        controller = self.evolution_controller

        if controller is None:
            return {
                "success": False,
                "status": "EVOLUTION_UNAVAILABLE",
            }

        runner = getattr(
            controller,
            "create_and_start",
            None,
        )
        if not callable(runner):
            return {
                "success": False,
                "status": "EVOLUTION_INCOMPATIBLE",
            }

        objective = (
            "Oceń i zaplanuj najkorzystniejszą "
            "przebudowę architektury JARVIS OS."
        )

        try:
            result = runner(
                objective=objective,
                mode="SAFE_AUTONOMOUS",
                max_iterations=3,
                context={
                    "source": "autonomous_architect",
                    "blueprints": blueprints,
                },
                metadata={
                    "component": "B50",
                    "kind": "architecture_refactor",
                },
            )
        except Exception as error:
            return {
                "success": False,
                "status": "EVOLUTION_FAILED",
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
            }

        return (
            result
            if isinstance(result, dict)
            else {
                "success": True,
                "status": "SUBMITTED",
                "result": result,
            }
        )

    def _send_to_director(
        self,
        blueprints: list[dict[str, Any]],
    ) -> dict[str, Any]:
        controller = self.director_controller

        if controller is None:
            return {
                "success": False,
                "status": "DIRECTOR_UNAVAILABLE",
            }

        planner = getattr(
            controller,
            "plan_project_autonomously",
            None,
        )
        if not callable(planner):
            return {
                "success": False,
                "status": "DIRECTOR_INCOMPATIBLE",
            }

        try:
            result = planner(
                objective=(
                    "Uwzględnij rekomendacje Autonomous Architect "
                    "w kolejnych celach rozwoju projektu."
                ),
                context={
                    "source": "autonomous_architect",
                    "architecture_blueprints": blueprints,
                },
                limit=max(1, len(blueprints)),
            )
        except Exception as error:
            return {
                "success": False,
                "status": "DIRECTOR_FAILED",
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
            }

        return (
            result
            if isinstance(result, dict)
            else {
                "success": True,
                "status": "SUBMITTED",
                "result": result,
            }
        )

    @staticmethod
    def _rank_blueprints(
        blueprints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []

        for blueprint in blueprints:
            item = dict(blueprint)
            roi = float(
                item.get("estimated_roi", 0.0)
            )
            risk = float(
                item.get("estimated_risk", 1.0)
            )
            priority = str(
                item.get("priority", "medium")
            ).lower()

            priority_bonus = {
                "critical": 0.25,
                "high": 0.15,
                "medium": 0.08,
                "low": 0.0,
            }.get(priority, 0.0)

            score = (
                roi * 0.70
                + (1.0 - risk) * 0.30
                + priority_bonus
            )

            item["architect_score"] = round(
                max(0.0, min(1.25, score)),
                4,
            )
            ranked.append(item)

        return sorted(
            ranked,
            key=lambda item: (
                -float(item["architect_score"]),
                float(
                    item.get(
                        "estimated_risk",
                        1.0,
                    )
                ),
                str(item.get("title", "")),
            ),
        )

    @staticmethod
    def _resolve_priority(
        queue: object,
        priority_name: str,
    ) -> object:
        module_name = queue.__class__.__module__

        try:
            module = __import__(
                module_name,
                fromlist=["TaskPriority"],
            )
            priority_type = getattr(
                module,
                "TaskPriority",
            )

            mapping = {
                "critical": "CRITICAL",
                "high": "HIGH",
                "medium": "NORMAL",
                "normal": "NORMAL",
                "low": "LOW",
            }
            return getattr(
                priority_type,
                mapping.get(
                    priority_name,
                    "NORMAL",
                ),
            )
        except (
            ImportError,
            AttributeError,
        ):
            return priority_name
