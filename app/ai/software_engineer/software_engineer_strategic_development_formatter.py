from __future__ import annotations

from typing import Any


def format_strategic_development_response(
    response: dict[str, Any],
) -> str:
    status = str(
        response.get("status", "STRATEGIC_DEVELOPMENT_UNKNOWN")
    )
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    summary = _mapping(response.get("summary"))
    project_summary = _mapping(response.get("project_summary"))
    selected = _mapping(response.get("selected"))
    recommendation = _mapping(response.get("recommendation"))
    lines = [f"Rozwój strategiczny B57: {status}"]

    if runtime:
        if bool(runtime.get("paused", False)):
            supervisor = "WSTRZYMANY"
        elif bool(runtime.get("enabled", False)) or bool(
            runtime.get("running", False)
        ):
            supervisor = "AKTYWNY"
        else:
            supervisor = "WYŁĄCZONY"
        lines.extend((
            f"Nadzorca B57: {supervisor}",
            f"Faza: {runtime.get('phase', 'IDLE')}",
            f"Cykle B57: {runtime.get('cycles_completed', 0)}",
        ))
        active_goal_id = str(runtime.get("active_goal_id", "")).strip()
        if active_goal_id:
            lines.append(f"Aktywny cel: {active_goal_id}")
        recommendation_id = str(
            runtime.get("last_recommendation_id", "")
        ).strip()
        if recommendation_id:
            lines.append(f"Rekomendowane zadanie: {recommendation_id}")
        last_error = str(runtime.get("last_error", "")).strip()
        if last_error:
            lines.append(f"Błąd B57: {last_error}")

    if summary:
        lines.append(
            "Roadmapa B57: "
            f"{summary.get('total', 0)} celów, "
            f"{summary.get('pending', 0)} oczekuje, "
            f"{summary.get('active', 0)} aktywnych, "
            f"{summary.get('completed', 0)} ukończonych, "
            f"{summary.get('partial', 0)} częściowych, "
            f"{summary.get('blocked', 0)} zablokowanych"
        )

    if project_summary:
        lines.append(
            "Backlog B55: "
            f"{project_summary.get('total', 0)} łącznie, "
            f"{project_summary.get('pending', 0)} oczekuje, "
            f"{project_summary.get('active', 0)} aktywnych"
        )

    if selected:
        lines.extend(_goal_lines(selected, prefix="Wybrany cel"))

    if recommendation:
        lines.append(
            "Następne zadanie celu: "
            f"{recommendation.get('opportunity_id', '-')} | "
            f"wynik {recommendation.get('final_score', 0)} | "
            f"ryzyko {recommendation.get('risk_score', 0)} | "
            f"{recommendation.get('target', '')}"
        )

    goals = response.get("goals", [])
    if isinstance(goals, list) and goals:
        lines.append(f"Cele roadmapy: {len(goals)}")
        for index, item in enumerate(goals[:10], start=1):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"{index}. {item.get('goal_id', '-')} | "
                f"{item.get('status', 'UNKNOWN')} | "
                f"wynik {item.get('priority_score', 0)} | "
                f"{item.get('pending_count', 0)}/{item.get('total_count', 0)} "
                f"oczekuje | {item.get('subsystem', '')}"
            )
        if len(goals) > 10:
            lines.append(f"... oraz {len(goals) - 10} kolejnych")

    history = response.get("history", [])
    if isinstance(history, list) and history:
        lines.append(f"Historia B57: {len(history)}")
        for item in history[:8]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('status', 'UNKNOWN')} | "
                f"{item.get('goal_id', '')} | "
                f"{item.get('opportunity_id', '')}"
            )

    if policy:
        lines.append(
            "Polityka B57: "
            f"odświeżanie {policy.get('refresh_interval_seconds', 300)} s, "
            f"aktywnych celów 1, "
            f"min wynik {policy.get('min_goal_score', 15)}, "
            f"max ryzyko {policy.get('max_goal_risk', 65)}, "
            f"integracja B56 {'TAK' if policy.get('integrate_with_b56') else 'NIE'}, "
            "auto-approve NIE"
        )

    errors = response.get("errors", [])
    if isinstance(errors, list):
        for error in errors[:5]:
            lines.append(f"Błąd: {error}")
    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport: {report_path}")
    return "\n".join(lines)


def _goal_lines(goal: dict[str, Any], *, prefix: str) -> list[str]:
    return [
        f"{prefix}: {goal.get('goal_id', '-')}",
        f"Cel: {goal.get('title', '')}",
        f"Podsystem: {goal.get('subsystem', '')}",
        f"Kategoria: {goal.get('issue_type', '')}",
        (
            "Postęp celu: "
            f"ukończone {goal.get('completed_count', 0)}, "
            f"aktywne {goal.get('active_count', 0)}, "
            f"oczekuje {goal.get('pending_count', 0)}, "
            f"nieudane {goal.get('failed_count', 0)}"
        ),
    ]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
