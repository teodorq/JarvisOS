from dataclasses import dataclass, field

from app.autodev.project_file import (
    ProjectFile
)


@dataclass
class ModuleAnalysis:

    path: str

    category: str = "unknown"

    score: float = 0.0

    quality: str = "UNKNOWN"

    risk: str = "LOW"

    line_count: int = 0

    class_count: int = 0

    function_count: int = 0

    import_count: int = 0

    dependency_count: int = 0

    findings: list[str] = field(
        default_factory=list
    )

    recommendations: list[str] = field(
        default_factory=list
    )

    def add_finding(
        self,
        finding: str
    ):

        if (
            finding
            and finding
            not in self.findings
        ):
            self.findings.append(
                finding
            )

    def add_recommendation(
        self,
        recommendation: str
    ):

        if (
            recommendation
            and recommendation
            not in self.recommendations
        ):
            self.recommendations.append(
                recommendation
            )

    def summary(
        self
    ) -> str:

        lines = [

            "MODULE ANALYSIS",

            "",

            f"Path: {self.path}",

            f"Category: {self.category}",

            f"Score: {self.score:.2f}",

            f"Quality: {self.quality}",

            f"Risk: {self.risk}",

            "",

            f"Lines: {self.line_count}",

            f"Classes: {self.class_count}",

            f"Functions: {self.function_count}",

            f"Imports: {self.import_count}",

            f"Dependencies: {self.dependency_count}"
        ]

        if self.findings:

            lines.append("")
            lines.append("Findings:")

            for item in self.findings:
                lines.append(
                    f"- {item}"
                )

        if self.recommendations:

            lines.append("")
            lines.append(
                "Recommendations:"
            )

            for item in (
                self.recommendations
            ):
                lines.append(
                    f"- {item}"
                )

        return "\n".join(
            lines
        )


class ModuleAnalyzer:

    """
    Ocenia jakość pojedynczego modułu.
    """

    def analyze(
        self,
        project_file: ProjectFile
    ) -> ModuleAnalysis:

        analysis = ModuleAnalysis(
            path=project_file.path,
            category=project_file.category
        )

        analysis.class_count = len(
            project_file.classes
        )

        analysis.function_count = len(
            project_file.functions
        )

        analysis.import_count = len(
            project_file.imports
        )

        if hasattr(
            project_file,
            "line_count"
        ):
            analysis.line_count = (
                project_file.line_count
            )

        analysis.dependency_count = (
            analysis.import_count
        )

        score = 100.0

        if analysis.line_count > 500:
            score -= 15
            analysis.add_finding(
                "Duży plik."
            )
            analysis.add_recommendation(
                "Rozważ podział modułu."
            )

        if analysis.function_count > 25:
            score -= 10
            analysis.add_finding(
                "Duża liczba funkcji."
            )
            analysis.add_recommendation(
                "Podziel odpowiedzialności."
            )

        if analysis.class_count > 10:
            score -= 10
            analysis.add_finding(
                "Duża liczba klas."
            )

        if analysis.import_count > 20:
            score -= 15
            analysis.add_finding(
                "Dużo importów."
            )
            analysis.add_recommendation(
                "Zmniejsz zależności."
            )

        analysis.score = max(
            score,
            0.0
        )

        if analysis.score >= 90:
            analysis.quality = "EXCELLENT"

        elif analysis.score >= 75:
            analysis.quality = "GOOD"

        elif analysis.score >= 60:
            analysis.quality = "MEDIUM"

        else:
            analysis.quality = "LOW"

        if analysis.score < 50:
            analysis.risk = "HIGH"

        elif analysis.score < 70:
            analysis.risk = "MEDIUM"

        else:
            analysis.risk = "LOW"

        return analysis

    def analyze_many(
        self,
        project_files: list[ProjectFile]
    ) -> list[ModuleAnalysis]:

        analyses = []

        for project_file in project_files:

            analyses.append(
                self.analyze(
                    project_file
                )
            )

        analyses.sort(
            key=lambda item:
                item.score
        )

        return analyses