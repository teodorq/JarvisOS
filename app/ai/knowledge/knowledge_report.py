from __future__ import annotations

from collections import Counter

from .models import KnowledgeReport


class KnowledgeReportFormatter:
    def format_text(self, report: KnowledgeReport) -> str:
        counts = Counter(issue.category for issue in report.issues)
        lines = [
            "JARVIS OS - AUTONOMOUS KNOWLEDGE REPORT",
            f"Python files: {report.python_files}",
            f"Scanned files: {report.scanned_files}",
            f"Issues: {report.issue_count}",
            "",
            "Issue summary:",
        ]
        if counts:
            lines.extend(f"- {category}: {count}" for category, count in sorted(counts.items()))
        else:
            lines.append("- no issues detected")

        lines.extend(["", "Recommended tasks:"])
        if report.tasks:
            for index, task in enumerate(report.tasks, start=1):
                lines.append(
                    f"{index}. [{task.priority}] {task.title} "
                    f"(ROI={task.roi:.2f}, risk={task.risk:.2f})"
                )
        else:
            lines.append("- no tasks generated")
        return "\n".join(lines)
