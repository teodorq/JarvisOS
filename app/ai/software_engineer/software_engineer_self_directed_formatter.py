from __future__ import annotations

from typing import Any


def format_self_directed_development_response(
    response: dict[str, Any],
) -> str:
    status = str(
        response.get("status", "SELF_DIRECTED_DEVELOPMENT_UNKNOWN")
    )
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    summary = _mapping(response.get("project_summary"))
    lines = [f"Samodzielny rozwój B56: {status}"]

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
            f"Nadzorca B56: {supervisor}",
            f"Faza: {runtime.get('phase', 'IDLE')}",
            f"Cykle B56: {runtime.get('cycles_completed', 0)}",
            (
                "Wyniki: "
                f"ukończone {runtime.get('completed_total', 0)}, "
                f"nieudane {runtime.get('failed_total', 0)}, "
                f"odroczone {runtime.get('deferred_total', 0)}, "
                f"kolejne błędy {runtime.get('consecutive_failures', 0)}"
            ),
            (
                "Budżet dzienny: "
                f"{runtime.get('dispatches_today', 0)}/"
                f"{policy.get('max_dispatches_per_day', 10)}"
            ),
        ))
        active_job = str(runtime.get("active_job_id", "")).strip()
        if active_job:
            lines.append(f"Aktywne zadanie: {active_job}")
        approval_job = str(
            runtime.get("waiting_approval_job_id", "")
        ).strip()
        if approval_job:
            lines.append(f"Czeka na akceptację: {approval_job}")
        cooldown = str(runtime.get("cooldown_until", "")).strip()
        if cooldown:
            lines.append(f"Cooldown do: {cooldown}")
        last_outcome = _mapping(runtime.get("last_outcome"))
        if last_outcome:
            lines.append(
                "Ostatni wynik zadania: "
                f"{last_outcome.get('status', 'UNKNOWN')} | "
                f"{last_outcome.get('job_id', '')}"
            )
        last_error = str(runtime.get("last_error", "")).strip()
        if last_error:
            lines.append(f"Błąd B56: {last_error}")

    if summary:
        lines.append(
            "Backlog B55: "
            f"{summary.get('total', 0)} łącznie, "
            f"{summary.get('pending', 0)} oczekuje, "
            f"{summary.get('active', 0)} aktywnych, "
            f"{summary.get('completed', 0)} ukończonych, "
            f"{summary.get('failed', 0)} nieudanych"
        )

    active = response.get("active", [])
    if isinstance(active, list) and active:
        lines.append(f"Aktywne możliwości: {len(active)}")
        for item in active[:5]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('status', 'UNKNOWN')} | "
                f"{item.get('job_id', '')} | {item.get('target', '')}"
            )

    history = response.get("history", [])
    if isinstance(history, list) and history:
        lines.append(f"Historia B56: {len(history)}")
        for item in history[:8]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('status', 'UNKNOWN')} | "
                f"{item.get('phase', '')} | {item.get('job_id', '')}"
            )

    reason = str(response.get("reason", "")).strip()
    if reason:
        lines.append(f"Powód: {reason}")

    if policy:
        lines.append(
            "Polityka B56: "
            f"cykl {policy.get('interval_seconds', 60)} s, "
            f"skan {policy.get('scan_interval_seconds', 300)} s, "
            f"aktywnych {policy.get('max_active_jobs', 1)}, "
            f"limit błędów {policy.get('max_consecutive_failures', 3)}, "
            f"auto-dispatch {'TAK' if policy.get('auto_dispatch') else 'NIE'}, "
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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
