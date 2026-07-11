from __future__ import annotations

from typing import Any


class AutoDevProjectHealth:
    def evaluate(
        self,
        *,
        snapshot: dict[str, Any],
        dependency_errors: int = 0,
        failed_tests: int = 0,
    ) -> dict[str, Any]:
        python_files = int(
            snapshot.get(
                "python_files_count",
                0,
            )
            or 0
        )

        total_lines = int(
            snapshot.get(
                "total_lines",
                0,
            )
            or 0
        )

        scan_errors = len(
            snapshot.get(
                "errors",
                [],
            )
            or []
        )

        score = 100.0
        score -= min(scan_errors * 5.0, 25.0)
        score -= min(int(dependency_errors) * 3.0, 20.0)
        score -= min(int(failed_tests) * 10.0, 40.0)

        if python_files == 0:
            score -= 20.0

        if total_lines == 0:
            score -= 10.0

        score = max(0.0, round(score, 2))

        level = (
            "EXCELLENT"
            if score >= 90
            else (
                "GOOD"
                if score >= 75
                else (
                    "WARNING"
                    if score >= 50
                    else "CRITICAL"
                )
            )
        )

        return {
            "success": True,
            "status": "PROJECT_HEALTH_READY",
            "health_score": score,
            "health_level": level,
            "python_files": python_files,
            "total_lines": total_lines,
            "scan_errors": scan_errors,
            "dependency_errors": int(dependency_errors),
            "failed_tests": int(failed_tests),
        }
