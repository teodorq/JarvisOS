from __future__ import annotations

from typing import Any


def format_strategic_policy_response(response: dict[str, Any]) -> str:
    status = str(response.get("status", "UNKNOWN"))
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    summary = _mapping(response.get("summary"))
    metrics = _mapping(response.get("metrics")) or _mapping(runtime.get("last_metrics"))
    lines = [f"Samouczenie strategiczne B60: {status}"]
    lines.append(
        "Nadzorca B60: "
        + ("AKTYWNY" if runtime.get("enabled") else "WYŁĄCZONY")
    )
    lines.append(f"Faza: {runtime.get('phase', 'IDLE')}")
    lines.append(f"Cykle B60: {runtime.get('cycles_completed', 0)}")
    lines.append(
        "Wersje polityki: "
        f"{summary.get('revisions', 0)}, "
        f"aktywne {summary.get('active', 0)}, "
        f"proponowane {summary.get('proposed', 0)}, "
        f"cofnięte {summary.get('rolled_back', 0)}"
    )
    if metrics:
        lines.append(
            "Dowody B58: "
            f"{metrics.get('observations', 0)} obserwacji, "
            f"{metrics.get('completed', 0)} ukończone, "
            f"{metrics.get('deferred', 0)} odroczone, "
            f"{metrics.get('failed', 0)} błędy"
        )
        lines.append(
            "Wskaźniki: "
            f"sukces {float(metrics.get('success_rate', 0.0)) * 100:.1f}%, "
            f"odroczenia {float(metrics.get('deferred_rate', 0.0)) * 100:.1f}%, "
            f"błędy {float(metrics.get('failure_rate', 0.0)) * 100:.1f}%"
        )
    decision = str(response.get("decision", runtime.get("last_decision", "")))
    if decision:
        lines.append(f"Decyzja uczenia: {decision}")
    reason = str(response.get("reason", "")).strip()
    if reason:
        lines.append(f"Uzasadnienie: {reason}")
    changes = _mapping(response.get("changes"))
    if changes:
        lines.append("Bezpieczne zmiany polityki B59:")
        for key, value in changes.items():
            lines.append(f"- {key}: {value}")
    active = _mapping(response.get("active_revision"))
    proposal = _mapping(response.get("proposal"))
    revision = _mapping(response.get("revision"))
    if active:
        lines.append(
            "Aktywna wersja: "
            f"{active.get('revision_id', '-')} | "
            f"pewność {active.get('confidence', 0)}"
        )
    if proposal:
        lines.append(
            "Propozycja: "
            f"{proposal.get('revision_id', '-')} | "
            f"dowody {proposal.get('evidence_count', 0)} | "
            f"pewność {proposal.get('confidence', 0)}"
        )
    if revision:
        lines.append(
            "Wersja wyniku: "
            f"{revision.get('revision_id', '-')} | "
            f"{revision.get('status', '')}"
        )
    revisions = response.get("revisions", [])
    if isinstance(revisions, list) and revisions:
        lines.append(f"Ostatnie wersje B60: {len(revisions)}")
        for item in revisions[:8]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('revision_id', '-')} | "
                    f"{item.get('status', 'UNKNOWN')} | "
                    f"dowody {item.get('evidence_count', 0)} | "
                    f"pewność {item.get('confidence', 0)}"
                )
    history = response.get("history", [])
    if isinstance(history, list) and history:
        lines.append(f"Historia B60: {len(history)}")
        for item in history[:8]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('status', 'UNKNOWN')} | "
                    f"{item.get('decision', '')} | "
                    f"{item.get('revision_id', '')}"
                )
    current = _mapping(response.get("current_portfolio_policy"))
    if current:
        lines.append(
            "Aktualna polityka B59: "
            f"min wynik {current.get('min_adaptive_score', 5.0)}, "
            f"kara błędu {current.get('failure_penalty', 8.0)}, "
            f"kara odroczenia {current.get('deferred_penalty', 1.5)}, "
            f"eksploracja {current.get('exploration_bonus', 6.0)}, "
            f"cooldown {current.get('cooldown_seconds', 900.0)} s"
        )
    if policy:
        lines.append(
            "Polityka B60: "
            f"cykl {policy.get('learning_interval_seconds', 300)} s, "
            f"okno {policy.get('observation_window', 200)}, "
            f"min dowodów {policy.get('min_observations', 3)}, "
            f"min pewność {policy.get('min_confidence', 0.45)}, "
            f"auto-zastosowanie {'TAK' if policy.get('auto_apply_safe_changes') else 'NIE'}, "
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
