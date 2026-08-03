from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from dataclasses import asdict, dataclass, field
from typing import Any

from app.autodev.module_analysis import ModuleAnalysis
from app.autodev.project_scanner import ProjectScanner
from app.autodev.module_analysis import ModuleAnalyzer


@dataclass(slots=True)
class SelfReviewFinding:
    path: str
    score: float
    quality: str
    risk: str
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SelfReviewEngine:
    """
    Wykonuje bezpieczny przegląd jakości całego projektu.

    Moduł:
    - nie zapisuje żadnych zmian,
    - nie wykonuje patchy,
    - nie uruchamia kodu projektu,
    - jedynie analizuje pliki Python.
    """

    def __init__(
        self,
        project_root: str = default_project_root(),
        max_findings: int = 100,
    ) -> None:
        self.project_root = project_root
        self.max_findings = max(1, int(max_findings))
        self.scanner = ProjectScanner(project_root)
        self.analyzer = ModuleAnalyzer()
        self.last_result: dict[str, Any] | None = None

    def run(
        self,
    ) -> dict[str, Any]:

        scan_report = self.scanner.scan_with_report()
        project_index = scan_report["index"]

        analyses = self.analyzer.analyze_many(
            project_index.files
        )

        findings = [
            self._to_finding(analysis)
            for analysis in analyses
            if (
                analysis.findings
                or analysis.recommendations
                or analysis.score < 90
            )
        ][: self.max_findings]

        average_score = (
            round(
                sum(
                    analysis.score
                    for analysis in analyses
                ) / len(analyses),
                2,
            )
            if analyses
            else 0.0
        )

        lowest = (
            min(
                analyses,
                key=lambda item: item.score,
            )
            if analyses
            else None
        )

        result = {
            "success": True,
            "status": "SELF_REVIEW_COMPLETED",
            "project_root": self.project_root,
            "files_scanned": scan_report["files_count"],
            "scan_errors": list(scan_report["errors"]),
            "analyses_count": len(analyses),
            "findings_count": len(findings),
            "average_score": average_score,
            "lowest_score": (
                lowest.score
                if lowest is not None
                else None
            ),
            "lowest_score_path": (
                lowest.path
                if lowest is not None
                else ""
            ),
            "findings": [
                finding.to_dict()
                for finding in findings
            ],
        }

        self.last_result = dict(result)
        return result

    def _to_finding(
        self,
        analysis: ModuleAnalysis,
    ) -> SelfReviewFinding:

        return SelfReviewFinding(
            path=analysis.path,
            score=analysis.score,
            quality=analysis.quality,
            risk=analysis.risk,
            findings=list(analysis.findings),
            recommendations=list(
                analysis.recommendations
            ),
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": self.project_root,
            "max_findings": self.max_findings,
            "last_result": self.last_result,
        }
