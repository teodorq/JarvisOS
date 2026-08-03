from __future__ import annotations

from collections import defaultdict


class CouplingAnalyzer:

    def analyze(
        self,
        graph: dict[str, set[str]],
    ) -> dict[str, dict[str, float | int]]:
        incoming: dict[str, set[str]] = defaultdict(set)

        for module, dependencies in graph.items():
            for dependency in dependencies:
                incoming[dependency].add(module)

        result: dict[str, dict[str, float | int]] = {}

        for module in graph:
            afferent = len(incoming[module])
            efferent = len(graph.get(module, set()))
            total = afferent + efferent

            instability = (
                efferent / total
                if total
                else 0.0
            )

            score = max(
                0.0,
                100.0 - (total * 8.0),
            )

            result[module] = {
                "afferent": afferent,
                "efferent": efferent,
                "total": total,
                "instability": round(instability, 3),
                "score": round(score, 2),
            }

        return result

    def high_coupling_modules(
        self,
        metrics: dict[str, dict[str, float | int]],
        threshold: int = 8,
    ) -> dict[str, int]:
        return {
            module: int(values["total"])
            for module, values in metrics.items()
            if int(values["total"]) > threshold
        }
