from __future__ import annotations

from typing import Any


def format_project_intelligence_response(
    response: dict[str, Any],
) -> str:
    status = str(
        response.get(
            "status",
            "PROJECT_INTELLIGENCE_UNKNOWN",
        )
    )
    lines = [f"Inteligencja projektu: {status}"]
    summary = _mapping(response.get("summary"))
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    selected = _mapping(response.get("selected"))
    opportunities = response.get("opportunities", [])
    cycles = response.get("cycles", [])

    if summary:
        lines.append(
            "Backlog: "
            f"{summary.get('total', 0)} łącznie, "
            f"{summary.get('pending', 0)} oczekuje, "
            f"{summary.get('active', 0)} aktywnych, "
            f"{summary.get('completed', 0)} zakończonych, "
            f"{summary.get('failed', 0)} nieudanych"
        )

    if selected:
        lines.extend(_format_opportunity(selected, prefix="Najlepsze zadanie"))

    if isinstance(opportunities, list):
        lines.append(f"Zadania rozwoju: {len(opportunities)}")
        for index, item in enumerate(opportunities[:10], start=1):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"{index}. {item.get('opportunity_id', '-')} | "
                f"{item.get('status', 'UNKNOWN')} | "
                f"wynik {item.get('final_score', 0)} | "
                f"ryzyko {item.get('risk_score', 0)} | "
                f"{item.get('target', '')}"
            )
        if len(opportunities) > 10:
            lines.append(f"... oraz {len(opportunities) - 10} kolejnych")

    if isinstance(cycles, list) and cycles:
        lines.append(f"Historia cykli: {len(cycles)}")
        for item in cycles[:5]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('status', 'UNKNOWN')} | "
                f"skan {item.get('scanned', 0)} | "
                f"utworzono {item.get('created', 0)} | "
                f"job {item.get('dispatched_job_id', '')}"
            )

    if runtime:
        if bool(runtime.get("paused", False)):
            supervisor = "WSTRZYMANY"
        elif bool(runtime.get("enabled", False)) or bool(runtime.get("running", False)):
            supervisor = "AKTYWNY"
        else:
            supervisor = "WYŁĄCZONY"
        lines.append(f"Nadzorca B55: {supervisor}")
        lines.append(
            f"Cykle B55: {runtime.get('cycles_completed', 0)}"
        )
        last_scan = str(runtime.get("last_scan_at", "")).strip()
        if last_scan:
            lines.append(f"Ostatni skan: {last_scan}")
        last_dispatch = str(runtime.get("last_dispatch_at", "")).strip()
        if last_dispatch:
            lines.append(f"Ostatnie uruchomienie zadania: {last_dispatch}")
        last_error = str(runtime.get("last_error", "")).strip()
        if last_error:
            lines.append(f"Błąd B55: {last_error}")

    if policy:
        lines.append(
            "Polityka: "
            f"min score {policy.get('min_score', 25)}, "
            f"max risk {policy.get('max_risk', 65)}, "
            f"aktywnych {policy.get('max_active_jobs', 1)}, "
            f"auto-dispatch {'TAK' if policy.get('auto_dispatch') else 'NIE'}, "
            "auto-approve NIE"
        )

    job_id = str(response.get("job_id", "")).strip()
    if job_id:
        lines.append(f"Long-Running Job ID: {job_id}")

    errors = response.get("errors", [])
    if isinstance(errors, list):
        for error in errors[:5]:
            lines.append(f"Błąd: {error}")

    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport: {report_path}")
    return "\n".join(lines)


def _format_opportunity(
    item: dict[str, Any],
    *,
    prefix: str,
) -> list[str]:
    lines = [
        f"{prefix}: {item.get('opportunity_id', '-')}",
        f"Stan: {item.get('status', 'UNKNOWN')}",
        f"Tytuł: {item.get('title', '')}",
        f"Cel: {item.get('target', '')}",
        (
            "Ocena: "
            f"{item.get('final_score', 0)}, "
            f"ryzyko {item.get('risk_score', 0)}, "
            f"pewność {round(float(item.get('confidence', 0) or 0) * 100, 1)}%"
        ),
    ]
    job_id = str(item.get("job_id", "")).strip()
    if job_id:
        lines.append(f"Job ID: {job_id}")
    error = str(item.get("last_error", "")).strip()
    if error:
        lines.append(f"Ostatni błąd: {error}")
    return lines


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
