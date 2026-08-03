from __future__ import annotations


class ArchitectureRecommender:

    def build(
        self,
        coupling_metrics: dict[str, dict[str, float | int]],
        cohesion_metrics: dict[str, dict[str, float | int]],
        high_coupling_threshold: int = 8,
        low_cohesion_threshold: float = 0.35,
    ) -> list[dict[str, object]]:
        recommendations: list[dict[str, object]] = []

        for module, values in coupling_metrics.items():
            total = int(values["total"])
            if total <= high_coupling_threshold:
                continue

            recommendations.append(
                {
                    "type": "reduce_coupling",
                    "target": module,
                    "priority": "high",
                    "reason": (
                        f"Moduł ma {total} zależności "
                        "przychodzących i wychodzących."
                    ),
                }
            )

        for class_name, values in cohesion_metrics.items():
            cohesion = float(values["cohesion"])
            if cohesion >= low_cohesion_threshold:
                continue

            recommendations.append(
                {
                    "type": "improve_cohesion",
                    "target": class_name,
                    "priority": "medium",
                    "reason": (
                        f"Spójność klasy wynosi {cohesion:.3f}."
                    ),
                }
            )

        return sorted(
            recommendations,
            key=lambda item: (
                0 if item["priority"] == "high" else 1,
                str(item["target"]),
            ),
        )
