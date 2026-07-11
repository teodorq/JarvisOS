from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.autodev.module_analysis import ModuleAnalysis


@dataclass(slots=True)
class DetectedProblem:

    module: str
    severity: str
    title: str
    description: str
    recommendation: str
    score: float = 0.0
    metadata: dict = field(
        default_factory=dict
    )

    def to_dict(self) -> dict:
        return asdict(
            self
        )

    def summary(self) -> str:
        return "\n".join(
            [
                "DETECTED PROBLEM",
                f"Module: {self.module}",
                f"Severity: {self.severity}",
                f"Title: {self.title}",
                f"Description: {self.description}",
                (
                    "Recommendation: "
                    f"{self.recommendation}"
                ),
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

    def detect(
        self,
        analysis: ModuleAnalysis,
    ) -> list[DetectedProblem]:

        problems: list[
            DetectedProblem
        ] = []

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
                            "category": analysis.category,
                            "quality": analysis.quality,
                            "risk": analysis.risk,
                            "analysis_score": analysis.score,
                        },
                    )
                )

        return problems

    def detect_many(
        self,
        analyses: list[
            ModuleAnalysis
        ],
    ) -> list[
        DetectedProblem
    ]:

        detected: list[
            DetectedProblem
        ] = []

        seen: set[
            tuple[str, str]
        ] = set()

        for analysis in analyses:
            for problem in self.detect(
                analysis
            ):
                key = (
                    problem.module,
                    problem.title,
                )

                if key in seen:
                    continue

                seen.add(
                    key
                )

                detected.append(
                    problem
                )

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
        analyses: list[
            ModuleAnalysis
        ],
    ) -> str:

        problems = self.detect_many(
            analyses
        )

        lines = [
            "PROBLEM DETECTOR",
            "",
            f"Detected: {len(problems)}",
            "",
        ]

        if not problems:
            lines.append(
                "Nie wykryto problemów."
            )

            return "\n".join(
                lines
            )

        for problem in problems:
            lines.append(
                f"[{problem.severity}] "
                f"{problem.module}"
            )
            lines.append(
                f"  {problem.title}"
            )
            lines.append(
                f"  Score: {problem.score:.2f}"
            )

        return "\n".join(
            lines
        )
