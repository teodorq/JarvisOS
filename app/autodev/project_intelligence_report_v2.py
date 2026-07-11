from __future__ import annotations

from typing import Any


class ProjectIntelligenceReportV2:
    def generate(
        self,
        *,
        scan: dict[str, Any],
        index: dict[str, Any],
        duplicates: dict[str, Any],
        dead_code: dict[str, Any],
        refactors: dict[str, Any],
    ) -> dict[str, Any]:
        summary = "\n".join(
            [
                "AUTODEV PROJECT INTELLIGENCE",
                f"Pliki Python: {index.get('files_count', 0)}",
                f"Linie kodu: {index.get('total_lines', 0)}",
                (
                    "Grupy duplikatów: "
                    f"{duplicates.get('duplicate_groups_count', 0)}"
                ),
                (
                    "Kandydaci martwego kodu: "
                    f"{dead_code.get('count', 0)}"
                ),
                (
                    "Kandydaci refaktoryzacji: "
                    f"{refactors.get('count', 0)}"
                ),
                (
                    "Błędy skanowania: "
                    f"{scan.get('errors_count', 0)}"
                ),
            ]
        )

        return {
            "success": True,
            "status": "PROJECT_INTELLIGENCE_REPORT_READY",
            "summary": summary,
            "scan": scan,
            "index": index,
            "duplicates": duplicates,
            "dead_code": dead_code,
            "refactors": refactors,
            "writes_code": False,
        }
