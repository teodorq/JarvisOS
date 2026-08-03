from __future__ import annotations

from typing import Any


def format_strategic_portfolio_response(
    response: dict[str, Any],
) -> str:
    status = str(response.get("status", "STRATEGIC_PORTFOLIO_UNKNOWN"))
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    summary = _mapping(response.get("summary"))
    roadmap = _mapping(response.get("roadmap_summary"))
    executions = _mapping(response.get("execution_summary"))
    lines = [f"Adaptacja strategiczna B59: {status}"]

    if runtime:
        if bool(runtime.get("paused", False)):
            supervisor = "WSTRZYMANY"
        elif bool(runtime.get("running", False)):
            supervisor = "AKTYWNY"
        elif bool(runtime.get("enabled", False)):
            supervisor = "GOTOWY"
        else:
            supervisor = "WYŁĄCZONY"
        lines.extend((
            f"Nadzorca B59: {supervisor}",
            f"Faza: {runtime.get('phase', 'IDLE')}",
            f"Cykle B59: {runtime.get('cycles_completed', 0)}",
        ))
        selected_goal = str(runtime.get("selected_goal_id", "")).strip()
        if selected_goal:
            lines.append(f"Adaptacyjnie wybrany cel: {selected_goal}")
        last_outcome = str(runtime.get("last_outcome", "")).strip()
        if last_outcome:
            lines.append(
                "Ostatni wynik B58: "
                f"{last_outcome} | {runtime.get('last_execution_id', '')}"
            )
        last_error = str(runtime.get("last_error", "")).strip()
        if last_error:
            lines.append(f"Błąd B59: {last_error}")

    if summary:
        lines.append(
            "Portfolio B59: "
            f"{summary.get('total', 0)} celów, "
            f"{summary.get('ready', 0)} gotowych, "
            f"{summary.get('active', 0)} aktywnych, "
            f"{summary.get('waiting_approval', 0)} czeka na zgodę, "
            f"{summary.get('cooldown', 0)} w cooldown, "
            f"{summary.get('blocked', 0)} zablokowanych, "
            f"{summary.get('completed', 0)} ukończonych"
        )

    if roadmap:
        lines.append(
            "Roadmapa B57: "
            f"{roadmap.get('total', 0)} celów, "
            f"{roadmap.get('pending', 0)} oczekuje, "
            f"{roadmap.get('active', 0)} aktywnych"
        )

    if executions:
        lines.append(
            "Wyniki B58: "
            f"{executions.get('total', 0)} wykonań, "
            f"{executions.get('completed', 0)} ukończonych, "
            f"{executions.get('deferred', 0)} odroczonych, "
            f"{executions.get('failed', 0)} nieudanych"
        )

    selected = _mapping(response.get("selected"))
    portfolio_entry = _mapping(response.get("portfolio_entry"))
    if selected:
        lines.append(
            "Wybrany cel B57: "
            f"{selected.get('goal_id', '-')} | "
            f"{selected.get('subsystem', '')}"
        )
    if portfolio_entry:
        lines.append(
            "Wynik adaptacyjny: "
            f"{portfolio_entry.get('adaptive_priority_score', 0)} "
            f"(bazowy {portfolio_entry.get('base_priority_score', 0)})"
        )

    recommendation = _mapping(response.get("recommendation"))
    if recommendation:
        lines.append(
            "Następne zadanie B55: "
            f"{recommendation.get('opportunity_id', '-')} | "
            f"{recommendation.get('target', '')}"
        )

    entries = response.get("entries", [])
    if isinstance(entries, list) and entries:
        lines.append(f"Cele portfolio: {len(entries)}")
        for index, item in enumerate(entries[:10], start=1):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"{index}. {item.get('goal_id', '-')} | "
                f"{item.get('status', 'UNKNOWN')} | "
                f"adaptacyjny {item.get('adaptive_priority_score', 0)} | "
                f"B58: {item.get('completed_count', 0)} OK, "
                f"{item.get('deferred_count', 0)} odroczone, "
                f"{item.get('failed_count', 0)} błędy | "
                f"{item.get('subsystem', '')}"
            )
        if len(entries) > 10:
            lines.append(f"... oraz {len(entries) - 10} kolejnych")

    history = response.get("history", [])
    if isinstance(history, list) and history:
        lines.append(f"Historia B59: {len(history)}")
        for item in history[:8]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('status', 'UNKNOWN')} | "
                    f"{item.get('goal_id', '')} | "
                    f"{item.get('outcome', '')}"
                )

    if policy:
        lines.append(
            "Polityka B59: "
            f"balansowanie {policy.get('rebalance_interval_seconds', 300)} s, "
            "aktywnych celów 1, "
            f"próg błędów {policy.get('failure_cooldown_threshold', 2)}, "
            f"próg odroczeń {policy.get('deferred_cooldown_threshold', 3)}, "
            f"cooldown {policy.get('cooldown_seconds', 900)} s, "
            f"integracja B57 {'TAK' if policy.get('integrate_with_b57') else 'NIE'}, "
            f"integracja B58 {'TAK' if policy.get('integrate_with_b58') else 'NIE'}, "
            "auto-approve NIE"
        )

    for error in response.get("errors", [])[:5]:
        lines.append(f"Błąd: {error}")
    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport: {report_path}")
    return "\n".join(lines)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
