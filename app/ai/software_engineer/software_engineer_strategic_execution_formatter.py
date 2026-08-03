from __future__ import annotations

from typing import Any


def format_strategic_execution_response(
    response: dict[str, Any],
) -> str:
    status = str(response.get("status", "STRATEGIC_EXECUTION_UNKNOWN"))
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    summary = _mapping(response.get("summary"))
    roadmap = _mapping(response.get("roadmap_summary"))
    lines = [f"Wykonanie strategiczne B58: {status}"]

    if runtime:
        if bool(runtime.get("paused", False)):
            supervisor = "WSTRZYMANY"
        elif bool(runtime.get("enabled", True)):
            supervisor = "GOTOWY"
        else:
            supervisor = "WYŁĄCZONY"
        lines.extend((
            f"Nadzorca B58: {supervisor}",
            f"Faza: {runtime.get('phase', 'IDLE')}",
            f"Cykle B58: {runtime.get('cycles_completed', 0)}",
        ))
        active_job = str(runtime.get("active_job_id", "")).strip()
        active_goal = str(runtime.get("active_goal_id", "")).strip()
        if active_goal:
            lines.append(f"Aktywny cel B57: {active_goal}")
        if active_job:
            lines.append(f"Aktywne zadanie B53/B54: {active_job}")
        last_outcome = _mapping(runtime.get("last_outcome"))
        if last_outcome:
            lines.append(
                "Ostatni wynik: "
                f"{last_outcome.get('status', 'UNKNOWN')} | "
                f"{last_outcome.get('job_id', '')}"
            )
        last_error = str(runtime.get("last_error", "")).strip()
        if last_error:
            lines.append(f"Błąd B58: {last_error}")

    if summary:
        lines.append(
            "Wykonania B58: "
            f"{summary.get('total', 0)} łącznie, "
            f"{summary.get('active', 0)} aktywnych, "
            f"{summary.get('completed', 0)} ukończonych, "
            f"{summary.get('deferred', 0)} odroczonych, "
            f"{summary.get('failed', 0)} nieudanych, "
            f"{summary.get('waiting_approval', 0)} czeka na zgodę"
        )

    if roadmap:
        lines.append(
            "Roadmapa B57: "
            f"{roadmap.get('total', 0)} celów, "
            f"{roadmap.get('pending', 0)} oczekuje, "
            f"{roadmap.get('active', 0)} aktywnych"
        )

    execution = _mapping(response.get("execution"))
    if execution:
        lines.extend(_execution_lines(execution, prefix="Wykonanie"))

    active = response.get("active", [])
    if isinstance(active, list) and active:
        lines.append(f"Aktywne wykonania: {len(active)}")
        for item in active[:5]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('execution_id', '-')} | "
                    f"{item.get('status', 'UNKNOWN')} | "
                    f"{item.get('job_id', '')}"
                )

    executions = response.get("executions", [])
    if isinstance(executions, list) and executions:
        lines.append(f"Ostatnie wykonania: {len(executions)}")
        for item in executions[:10]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('status', 'UNKNOWN')} | "
                    f"{item.get('goal_id', '')} | "
                    f"{item.get('job_id', '')}"
                )

    history = response.get("history", [])
    if isinstance(history, list) and history:
        lines.append(f"Historia B58: {len(history)}")
        for item in history[:8]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('status', 'UNKNOWN')} | "
                    f"{item.get('outcome', '')} | "
                    f"{item.get('job_id', '')}"
                )

    if policy:
        lines.append(
            "Polityka B58: "
            "aktywnych wykonań 1, "
            f"integracja B57 {'TAK' if policy.get('integrate_with_b57') else 'NIE'}, "
            f"integracja B56 {'TAK' if policy.get('integrate_with_b56') else 'NIE'}, "
            "auto-approve NIE"
        )

    for error in response.get("errors", [])[:5]:
        lines.append(f"Błąd: {error}")
    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport: {report_path}")
    return "\n".join(lines)


def _execution_lines(
    execution: dict[str, Any],
    *,
    prefix: str,
) -> list[str]:
    return [
        f"{prefix}: {execution.get('execution_id', '-')}",
        f"Cel B57: {execution.get('goal_id', '')}",
        f"Zadanie B55: {execution.get('opportunity_id', '')}",
        f"Job B53/B54: {execution.get('job_id', '')}",
        f"Stan: {execution.get('status', 'UNKNOWN')}",
        f"Cel pliku: {execution.get('target', '')}",
    ]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
