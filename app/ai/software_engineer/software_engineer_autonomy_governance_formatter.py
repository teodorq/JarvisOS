from __future__ import annotations

from typing import Any

from .software_engineer_autonomy_operations_formatter import (
    format_autonomy_operations_response,
)


def format_autonomy_governance_response(response: dict[str, Any]) -> str:
    stage = str(response.get("stage", "B62-B70"))
    if stage in {f"B{value}" for value in range(71, 96)} or stage == "B89-B95":
        return format_autonomy_operations_response(response)
    display_stage = str(response.get("suite_span", stage))
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    summary = _mapping(response.get("summary"))
    lines = [
        f"Autonomia JARVIS {display_stage}: {response.get('status', 'UNKNOWN')}"
    ]
    lines.append(f"Faza: {runtime.get('phase', 'IDLE')}")
    lines.append(f"Cykle: {runtime.get('cycles_completed', 0)}")
    if stage == "B68":
        lines.append(
            "Nadzorca 24/7: "
            + ("AKTYWNY" if runtime.get("running") else "WYŁĄCZONY")
        )
        lines.append(
            f"Budżet dzienny: {runtime.get('cycles_used_today', 0)}/"
            f"{policy.get('max_daily_cycles', 24)}"
        )
        execution = _mapping(response.get("execution_summary"))
        if execution:
            lines.append(
                "Wykonania B58: "
                f"aktywne {execution.get('active', 0)}, "
                f"ukończone {execution.get('completed', 0)}, "
                f"oczekuje na zgodę {execution.get('waiting_approval', 0)}"
            )
    elif stage == "B62":
        deployment = _mapping(response.get("deployment"))
        if deployment:
            lines.append(
                "Wdrożenie: "
                f"{deployment.get('deployment_id', '-')} | "
                f"{deployment.get('status', 'UNKNOWN')} | "
                f"wersja {deployment.get('revision_id', '-') }"
            )
        metrics = _mapping(response.get("metrics"))
        if metrics:
            lines.append(
                "Canary: "
                f"dowody {metrics.get('observations', 0)}, "
                f"błędy {float(metrics.get('failure_rate', 0))*100:.1f}%, "
                f"odroczenia {float(metrics.get('deferred_rate', 0))*100:.1f}%"
            )
    elif stage == "B63":
        lines.append(
            f"Zarządzanie celami: przeskanowano {response.get('scanned', 0)}, "
            f"działania {len(response.get('actions', []) or [])}"
        )
    elif stage == "B64":
        metrics = _mapping(response.get("metrics"))
        if metrics:
            lines.append(
                "Zasoby: "
                f"CPU {metrics.get('cpu_percent', 0):.1f}%, "
                f"RAM {metrics.get('ram_percent', 0):.1f}%, "
                f"wolny dysk {metrics.get('free_disk_gb', 0):.1f} GB"
            )
        lines.append(
            f"Dzierżawy: {runtime.get('active_leases', 0)}/"
            f"{policy.get('max_active_leases', 1)}"
        )
    elif stage == "B65":
        lines.append(
            f"Hipotezy przyczynowe: {summary.get('records', 0)}, "
            f"nowe {len(response.get('hypotheses', []) or [])}"
        )
        lines.append("Zakres twierdzeń: korelacja, nie dowód przyczynowości.")
    elif stage == "B66":
        release = _mapping(response.get("release"))
        if release:
            lines.append(
                "Wydanie: "
                f"{release.get('release_id', '-')} | "
                f"{release.get('status', 'UNKNOWN')} | "
                f"pliki {release.get('file_count', 0)}"
            )
        lines.append("Publikacja i rollback wymagają jawnego potwierdzenia.")
    elif stage == "B67":
        findings = response.get("findings", [])
        if isinstance(findings, list):
            lines.append(f"Znaleziska konserwacji: {len(findings)}")
            for item in findings[:8]:
                if isinstance(item, dict):
                    lines.append(
                        f"- {item.get('severity', 'LOW')} | "
                        f"{item.get('category', 'UNKNOWN')} | "
                        f"{item.get('path', '')}"
                    )
    elif stage == "B69":
        counts = _mapping(response.get("incident_counts"))
        incidents = response.get("incidents", [])
        if not counts and isinstance(incidents, list):
            counts = {
                "open": sum(
                    1 for item in incidents
                    if isinstance(item, dict)
                    and str(item.get("status", "")).upper() == "OPEN"
                ),
                "contained": sum(
                    1 for item in incidents
                    if isinstance(item, dict)
                    and str(item.get("status", "")).upper() == "CONTAINED"
                ),
                "resolved": sum(
                    1 for item in incidents
                    if isinstance(item, dict)
                    and str(item.get("status", "")).upper() == "RESOLVED"
                ),
            }
        lines.append(
            "Incydenty: "
            f"otwarte {counts.get('open', 0)}, "
            f"ograniczone {counts.get('contained', 0)}, "
            f"zamknięte {counts.get('resolved', 0)}"
        )
        if isinstance(incidents, list):
            for item in incidents[:8]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"- {item.get('severity', 'LOW')} | "
                    f"{item.get('status', 'UNKNOWN')} | "
                    f"{item.get('category', 'UNKNOWN')} | "
                    f"{item.get('stage_name', '')}"
                )
        lines.append(
            "Ograniczenie krytyczne zatrzymuje B68 i odzyskuje dzierżawy B64."
        )
    elif stage == "B70":
        counts = _mapping(response.get("plan_counts"))
        plans = response.get("plans", [])
        plan = _mapping(response.get("plan"))
        if not plan and isinstance(plans, list) and plans:
            plan = _mapping(plans[0])
        lines.append(
            "Plany odzyskiwania: "
            f"gotowe {counts.get('preview_ready', 0)}, "
            f"ukończone {counts.get('completed', 0)}, "
            f"zablokowane {counts.get('blocked', 0)}, "
            f"niezweryfikowane {counts.get('verification_failed', 0)}"
        )
        if plan:
            lines.append(
                "Ostatni plan: "
                f"{plan.get('recovery_id', '-')} | "
                f"{plan.get('status', 'UNKNOWN')} | "
                f"{plan.get('category', 'UNKNOWN')}"
            )
            steps = plan.get("steps", [])
            if isinstance(steps, list) and steps:
                lines.append("Runbook: " + " → ".join(str(item) for item in steps[:8]))
        lines.append(
            "B70 tylko planuje automatycznie; wykonanie wymaga jawnego potwierdzenia."
        )
    else:
        stages = _mapping(response.get("stage_summaries"))
        if stages:
            lines.append("Etapy B62-B69:")
            for key in sorted(stages):
                item = _mapping(stages[key])
                lines.append(
                    f"- {key}: {item.get('phase', 'IDLE')} | "
                    f"cykle {item.get('cycles_completed', 0)} | "
                    f"rekordy {item.get('records', 0)}"
                )
    decision = str(response.get("decision", runtime.get("last_decision", "")))
    if decision:
        lines.append(f"Decyzja: {decision}")
    reason = str(response.get("reason", "")).strip()
    if reason:
        lines.append(f"Uzasadnienie: {reason}")
    for error in response.get("errors", [])[:5]:
        lines.append(f"Błąd: {error}")
    if policy:
        lines.append("Bezpieczeństwo: auto-approve NIE, maks. 1 aktywne wykonanie.")
    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport: {report_path}")
    return "\n".join(lines)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
