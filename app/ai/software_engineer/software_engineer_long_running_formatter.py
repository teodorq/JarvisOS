from __future__ import annotations

from typing import Any


def format_long_running_autonomy_response(
    response: dict[str, Any],
) -> str:
    status = str(response.get("status", "LONG_RUNNING_UNKNOWN"))
    job = _mapping(response.get("job"))
    jobs = response.get("jobs", [])
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    counts = _mapping(response.get("counts"))
    events = response.get("events", [])

    lines = [f"Długotrwała autonomia: {status}"]

    job_id = str(
        response.get("job_id", job.get("job_id", ""))
    ).strip()
    if job_id:
        lines.append(f"Job ID: {job_id}")

    if job:
        lines.extend(_format_job_details(job))

    if isinstance(jobs, list):
        lines.append(f"Zadania: {len(jobs)}")
        for index, item in enumerate(jobs[:10], start=1):
            if not isinstance(item, dict):
                continue
            lines.append(_format_job_row(index, item))
        if len(jobs) > 10:
            lines.append(f"... oraz {len(jobs) - 10} kolejnych zadań")

    if counts:
        summary = ", ".join(
            f"{key}: {value}"
            for key, value in sorted(counts.items())
            if int(value or 0) > 0
        )
        if summary:
            lines.append(f"Stany: {summary}")

    if isinstance(events, list) and events:
        lines.append(f"Ostatnie zdarzenia: {min(len(events), 5)}")
        for item in events[:5]:
            if not isinstance(item, dict):
                continue
            event = str(item.get("event", "UNKNOWN"))
            event_job = str(item.get("job_id", "")).strip()
            created = str(item.get("created_at", "")).strip()
            suffix = f" | {event_job}" if event_job else ""
            if created:
                suffix += f" | {created}"
            lines.append(f"- {event}{suffix}")

    if runtime:
        enabled = bool(runtime.get("enabled"))
        paused = bool(runtime.get("paused"))
        thread_running = bool(runtime.get("thread_running", runtime.get("running")))
        if paused:
            supervisor = "WSTRZYMANY"
        elif enabled or thread_running:
            supervisor = "AKTYWNY"
        else:
            supervisor = "WYŁĄCZONY"
        lines.append(f"Nadzorca: {supervisor}")
        lines.append(
            f"Cykle: {runtime.get('cycles_completed', 0)}, "
            f"odzyskane zadania: {runtime.get('recovered_jobs', 0)}"
        )
        last_error = str(runtime.get("last_error", "")).strip()
        if last_error:
            lines.append(f"Błąd nadzorcy: {last_error}")

    if policy:
        lines.append(
            "Limity: "
            f"CPU {policy.get('max_cpu_percent', 85)}%, "
            f"RAM {policy.get('max_memory_percent', 90)}%, "
            f"min dysk {policy.get('min_disk_free_gb', 2)} GB, "
            f"równolegle {policy.get('max_parallel_jobs', 1)}"
        )

    recovered = response.get("recovered")
    if recovered is not None:
        lines.append(f"Odzyskane w tym cyklu: {recovered}")

    removed = response.get("removed")
    if removed is not None:
        lines.append(f"Usunięte zadania: {removed}")

    errors = response.get("errors", [])
    if isinstance(errors, list):
        for error in errors[:5]:
            lines.append(f"Błąd: {error}")

    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport: {report_path}")

    return "\n".join(lines)


def _format_job_details(job: dict[str, Any]) -> list[str]:
    lines = [
        f"Stan zadania: {job.get('state', 'UNKNOWN')}",
        f"Priorytet: {job.get('priority', 0)}",
        f"Próby: {job.get('attempts', 0)}/{job.get('max_attempts', 0)}",
    ]
    objective = str(job.get("objective", "")).strip()
    if objective:
        lines.append(f"Cel: {objective}")
    schedule = _mapping(job.get("schedule"))
    if schedule:
        lines.append(f"Harmonogram: {schedule.get('type', 'immediate')}")
    next_run = str(job.get("next_run_at", "")).strip()
    if next_run:
        lines.append(f"Następne uruchomienie: {next_run}")
    run_id = str(job.get("autonomy_run_id", "")).strip()
    if run_id:
        lines.append(f"Autonomy Run ID: {run_id}")
    for label, key in (
        ("Utworzono", "created_at"),
        ("Uruchomiono", "started_at"),
        ("Zakończono", "completed_at"),
        ("Heartbeat", "heartbeat_at"),
    ):
        value = str(job.get(key, "")).strip()
        if value:
            lines.append(f"{label}: {value}")
    result = _mapping(job.get("last_result"))
    if result:
        result_status = str(result.get("status", "")).strip()
        if result_status:
            lines.append(f"Ostatni wynik: {result_status}")
        progress = result.get("progress_percent")
        if progress is not None:
            lines.append(f"Postęp autonomii: {progress}%")
        phase = str(result.get("phase", "")).strip()
        if phase:
            lines.append(f"Faza wykonania: {phase}")
        lease_state = str(
            result.get("approval_lease_state", "")
        ).strip()
        if lease_state:
            lines.append(f"Jednorazowa zgoda: {lease_state}")
        diagnostic_category = str(
            result.get("diagnostic_category", "")
        ).strip()
        if diagnostic_category:
            lines.append(
                f"Kategoria diagnostyczna: {diagnostic_category}"
            )
        diagnostic_id = str(result.get("diagnostic_id", "")).strip()
        if diagnostic_id:
            lines.append(f"Diagnostic ID: {diagnostic_id}")
        if result.get("requires_approval"):
            lines.append("Wymaga potwierdzenia użytkownika: TAK")
    history = job.get("run_history", [])
    if isinstance(history, list) and history:
        lines.append(f"Historia wykonań: {len(history)}")
    error = str(job.get("last_error", "")).strip()
    if error:
        lines.append(f"Ostatni błąd: {error}")
    return lines


def _format_job_row(index: int, job: dict[str, Any]) -> str:
    job_id = str(job.get("job_id", "-")).strip() or "-"
    state = str(job.get("state", "UNKNOWN"))
    priority = job.get("priority", 0)
    attempts = f"{job.get('attempts', 0)}/{job.get('max_attempts', 0)}"
    next_run = str(job.get("next_run_at", "")).strip()
    suffix = f" | następne: {next_run}" if next_run else ""
    return (
        f"{index}. {job_id} | {state} | "
        f"P{priority} | próby {attempts}{suffix}"
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
