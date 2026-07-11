from __future__ import annotations

from typing import Any

from app.autodev.module_analysis import ModuleAnalyzer
from app.autodev.project_dead_code_detector import (
    ProjectDeadCodeDetector,
)
from app.autodev.project_duplicate_detector import (
    ProjectDuplicateDetector,
)
from app.autodev.project_intelligence_index import (
    ProjectIntelligenceIndex,
)
from app.autodev.project_intelligence_report_v2 import (
    ProjectIntelligenceReportV2,
)
from app.autodev.project_refactor_selector import (
    ProjectRefactorSelector,
)
from app.autodev.project_scanner import ProjectScanner


class ProjectIntelligenceInspector:
    """
    Łączy istniejący ProjectScanner i ModuleAnalyzer
    z analizą duplikatów, kandydatów martwego kodu
    oraz wyborem celów refaktoryzacji.
    """

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
    ) -> None:
        self.scanner = ProjectScanner(
            project_root=project_root
        )
        self.module_analyzer = ModuleAnalyzer()
        self.duplicate_detector = ProjectDuplicateDetector()
        self.dead_code_detector = ProjectDeadCodeDetector()
        self.refactor_selector = ProjectRefactorSelector()
        self.reporter = ProjectIntelligenceReportV2()
        self.last_result: dict[str, Any] | None = None

    def inspect(self) -> dict[str, Any]:
        scan_report = self.scanner.scan_with_report()
        project_index = scan_report["index"]
        project_files = list(project_index.files)

        analyses = self.module_analyzer.analyze_many(
            project_files
        )

        intelligence_index = (
            ProjectIntelligenceIndex.build(
                project_files,
                analyses,
            ).to_dict()
        )

        duplicates = self.duplicate_detector.detect(
            [
                item.path
                for item in project_files
            ]
        )

        dead_code = self.dead_code_detector.detect(
            project_files
        )

        refactors = self.refactor_selector.select(
            analyses
        )

        serializable_scan = {
            key: value
            for key, value in scan_report.items()
            if key != "index"
        }

        report = self.reporter.generate(
            scan=serializable_scan,
            index=intelligence_index,
            duplicates=duplicates,
            dead_code=dead_code,
            refactors=refactors,
        )

        result = {
            "success": True,
            "status": "PROJECT_INTELLIGENCE_READY",
            "report": report,
            "next_tasks": list(
                refactors.get(
                    "candidates",
                    [],
                )
            ),
            "approved": False,
            "writes_code": False,
        }

        self.last_result = dict(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
            "scanner_errors": list(
                self.scanner.errors
            ),
        }
