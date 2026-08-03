from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.autodev.module_analysis import ModuleAnalysis
from app.autodev.project_intelligence_rules import (
    ProjectIntelligenceRuleEngine,
)


@dataclass(slots=True)
class DetectedProblem:
    module: str
    severity: str
    title: str
    description: str
    recommendation: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        return "\n".join(
            [
                "DETECTED PROBLEM",
                f"Module: {self.module}",
                f"Severity: {self.severity}",
                f"Title: {self.title}",
                f"Description: {self.description}",
                f"Recommendation: {self.recommendation}",
                f"Score: {self.score:.2f}",
            ]
        )


class ProblemDetector:
    SEVERITY_ORDER = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    def __init__(
        self,
        rule_engine: ProjectIntelligenceRuleEngine | None = None,
    ) -> None:
        self.rule_engine = (
            rule_engine or ProjectIntelligenceRuleEngine()
        )

    def detect(
        self,
        analysis: ModuleAnalysis,
    ) -> list[DetectedProblem]:

        problems = []

        rules = (
            (
                analysis.line_count > 500,
                "HIGH",
                "Zbyt duży plik",
                "Moduł zawiera bardzo dużo kodu.",
                "Podziel moduł na mniejsze części.",
                9.0,
            ),
            (
                analysis.function_count > 25,
                "MEDIUM",
                "Dużo funkcji",
                "Moduł posiada wiele funkcji.",
                "Rozdziel odpowiedzialności.",
                7.0,
            ),
            (
                analysis.class_count > 10,
                "MEDIUM",
                "Dużo klas",
                "W module znajduje się wiele klas.",
                "Wydziel część klas do osobnych modułów.",
                6.5,
            ),
            (
                analysis.import_count > 20,
                "HIGH",
                "Zbyt wiele importów",
                "Moduł ma dużo zależności.",
                "Zmniejsz liczbę zależności.",
                8.5,
            ),
            (
                analysis.dependency_count > 20,
                "HIGH",
                "Silne sprzężenie",
                "Moduł jest mocno powiązany z innymi.",
                "Ogranicz zależności między modułami.",
                8.8,
            ),
            (
                analysis.score < 60,
                "CRITICAL",
                "Niska jakość modułu",
                "Ogólna ocena jakości jest niska.",
                "Zaplanuj pełną refaktoryzację.",
                10.0,
            ),
        )

        for (
            condition,
            severity,
            title,
            description,
            recommendation,
            score,
        ) in rules:
            if condition:
                problems.append(
                    DetectedProblem(
                        module=analysis.path,
                        severity=severity,
                        title=title,
                        description=description,
                        recommendation=recommendation,
                        score=score,
                        metadata={
                            "source": "module_analysis",
                            "category": analysis.category,
                            "quality": analysis.quality,
                            "risk": analysis.risk,
                            "analysis_score": analysis.score,
                        },
                    )
                )

        for finding in self.rule_engine.detect(analysis):
            problems.append(
                DetectedProblem(
                    module=finding.module,
                    severity=finding.severity,
                    title=finding.title,
                    description=finding.description,
                    recommendation=finding.recommendation,
                    score=finding.score,
                    metadata={
                        "source": "project_intelligence",
                        "category": analysis.category,
                        "quality": analysis.quality,
                        "risk": analysis.risk,
                        "analysis_score": analysis.score,
                        **dict(finding.metadata),
                    },
                )
            )

        return problems

    def detect_many(
        self,
        analyses: list[ModuleAnalysis],
    ) -> list[DetectedProblem]:

        detected = []
        seen = set()

        for analysis in analyses:
            for problem in self.detect(analysis):
                key = (
                    problem.module,
                    problem.title,
                    str(problem.metadata.get("line", "")),
                )
                if key in seen:
                    continue

                seen.add(key)
                detected.append(problem)

        detected.sort(
            key=lambda item: (
                item.score,
                self.SEVERITY_ORDER.get(
                    item.severity,
                    0,
                ),
            ),
            reverse=True,
        )

        return detected

    def report(
        self,
        analyses: list[ModuleAnalysis],
    ) -> str:

        problems = self.detect_many(analyses)

        lines = [
            "PROBLEM DETECTOR",
            "",
            f"Detected: {len(problems)}",
            "",
        ]

        if not problems:
            lines.append("Nie wykryto problemów.")
            return "\n".join(lines)

        for problem in problems:
            lines.append(
                f"[{problem.severity}] {problem.module}"
            )
            lines.append(f"  {problem.title}")
            lines.append(f"  Score: {problem.score:.2f}")

        return "\n".join(lines)
