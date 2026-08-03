from __future__ import annotations

from typing import Any


def format_full_autonomy_response(
    response: dict[str, Any],
) -> str:
    status = str(response.get("status", "UNKNOWN"))
    run = dict(response.get("autonomy_run", {}) or {})
    plan = dict(response.get("plan", {}) or run.get("plan", {}) or {})
    report = dict(response.get("final_report", {}) or run.get("final_report", {}) or {})
    director = dict(response.get("director_run", {}) or {})
    validation = dict(response.get("final_validation", {}) or {})
    rollback = dict(response.get("rollback", {}) or {})
    execution = dict(response.get("execution", {}) or run.get("execution", {}) or {})
    lines = [
        f"Pełna autonomia: {status}",
    ]
    run_id = str(response.get("autonomy_run_id", run.get("run_id", "")))
    if run_id:
        lines.append(f"Run ID: {run_id}")
    objective = str(run.get("objective", report.get("objective", "")))
    if objective:
        lines.append(f"Cel: {objective}")
    campaigns = plan.get("campaigns", [])
    targets = plan.get("target_files", [])
    if isinstance(campaigns, list):
        lines.append(f"Kampanie: {len(campaigns)}")
    if isinstance(targets, list):
        lines.append(f"Pliki celu: {len(targets)}")
    if execution:
        lines.append(
            "Postęp: "
            f"{execution.get('progress_percent', 0)}% "
            f"({execution.get('campaigns_completed', 0)}/"
            f"{execution.get('campaigns_total', 0)} kampanii, "
            f"{execution.get('stages_completed', 0)}/"
            f"{execution.get('stages_total', 0)} etapów)"
        )
        current_campaign = str(
            execution.get(
                "current_campaign_id",
                "",
            )
        )
        current_stage = str(
            execution.get(
                "current_stage_id",
                "",
            )
        )
        if current_campaign:
            lines.append(
                f"Bieżąca kampania: {current_campaign}"
            )
        if current_stage:
            lines.append(
                f"Bieżący etap: {current_stage}"
            )
        changed_files = execution.get(
            "changed_files",
            [],
        )
        if isinstance(changed_files, list):
            lines.append(
                f"Zmienione pliki: {len(changed_files)}"
            )
    if director:
        lines.append(
            "Dyrektor: "
            f"{director.get('cycles', 0)} cykli, "
            f"{director.get('retries', 0)} retry"
        )
    if validation:
        lines.append(
            "Walidacja końcowa: "
            + (
                "OK"
                if validation.get("success", False)
                else "BŁĄD"
            )
        )
    if rollback:
        lines.append(
            "Rollback: "
            + (
                "OK"
                if rollback.get("success", False)
                else "BŁĄD"
            )
        )
    errors = response.get("errors", [])
    if isinstance(errors, list) and errors:
        lines.append(
            "Błędy: "
            + "; ".join(str(item) for item in errors[-5:])
        )
    report_path = str(response.get("report_path", ""))
    if report_path:
        lines.append(f"Raport: {report_path}")
    return "\n".join(lines)
