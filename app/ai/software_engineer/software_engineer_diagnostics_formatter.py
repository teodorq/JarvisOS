from __future__ import annotations

from typing import Any


def format_autonomous_diagnostics_response(response: dict[str, Any]) -> str:
    status = str(response.get("status", "AUTONOMOUS_DIAGNOSTICS_UNKNOWN"))
    lines = [f"Diagnostyka autonomii: {status}"]
    diagnostic = _mapping(response.get("diagnostic"))
    diagnostics = response.get("diagnostics", [])
    repair = _mapping(response.get("repair"))
    repairs = response.get("repairs", [])
    summary = _mapping(response.get("summary"))

    if diagnostic:
        lines.extend(_diagnostic_lines(diagnostic))
    if isinstance(diagnostics, list) and diagnostics:
        lines.append(f"Raporty diagnostyczne: {len(diagnostics)}")
        for index, item in enumerate(diagnostics[:10], start=1):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"{index}. {item.get('diagnostic_id', '-')} | "
                f"{item.get('category', 'UNKNOWN')} | "
                f"{item.get('severity', 'WARNING')} | "
                f"{item.get('job_id', item.get('autonomy_run_id', '-'))}"
            )
    if repair:
        lines.append(f"Naprawa: {repair.get('status', 'UNKNOWN')}")
        if repair.get("repair_id"):
            lines.append(f"Repair ID: {repair.get('repair_id')}")
        for action in repair.get("actions", [])[:10]:
            lines.append(f"- {action}")
    if isinstance(repairs, list) and repairs:
        lines.append(f"Historia napraw: {len(repairs)}")
        for item in repairs[:10]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('repair_id', '-')} | "
                    f"{item.get('status', 'UNKNOWN')} | "
                    f"{item.get('job_id', '-')}"
                )
    if summary:
        lines.append(
            "Podsumowanie: "
            f"raporty {summary.get('records', 0)}, "
            f"naprawy {summary.get('repairs', 0)}, "
            f"możliwe naprawy {summary.get('repairable', 0)}"
        )
    for error in response.get("errors", [])[:10] if isinstance(response.get("errors"), list) else []:
        lines.append(f"Błąd: {error}")
    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport: {report_path}")
    return "\n".join(lines)


def _diagnostic_lines(value: dict[str, Any]) -> list[str]:
    lines = []
    if value.get("diagnostic_id"):
        lines.append(f"Diagnostic ID: {value.get('diagnostic_id')}")
    if value.get("job_id"):
        lines.append(f"Job ID: {value.get('job_id')}")
    if value.get("autonomy_run_id"):
        lines.append(f"Autonomy Run ID: {value.get('autonomy_run_id')}")
    lines.extend([
        f"Kategoria: {value.get('category', 'UNKNOWN')}",
        f"Waga: {value.get('severity', 'WARNING')}",
        f"Etap: {value.get('stage', 'UNKNOWN')}",
        f"Przyczyna: {value.get('root_cause', '')}",
        f"Możliwa bezpieczna naprawa: {'TAK' if value.get('repairable') else 'NIE'}",
    ])
    if value.get("requires_approval"):
        lines.append("Wymaga jawnego potwierdzenia użytkownika: TAK")
    errors = value.get("errors", [])
    if isinstance(errors, list) and errors:
        lines.append("Najważniejsze błędy:")
        for error in errors[:5]:
            lines.append(f"- {error}")
    actions = value.get("suggested_actions", [])
    if isinstance(actions, list) and actions:
        lines.append("Zalecane działania:")
        for action in actions[:5]:
            lines.append(f"- {action}")
    if value.get("stderr"):
        lines.append(f"stderr: {str(value.get('stderr'))[:1000]}")
    if value.get("traceback"):
        lines.append(f"Traceback: {str(value.get('traceback'))[:2000]}")
    return lines


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
