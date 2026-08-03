from __future__ import annotations

from typing import Any


def format_strategic_validation_response(response: dict[str, Any]) -> str:
    runtime = _mapping(response.get("runtime"))
    policy = _mapping(response.get("policy"))
    summary = _mapping(response.get("summary"))
    metrics = _mapping(response.get("metrics")) or _mapping(
        runtime.get("last_metrics")
    )
    lines = [
        f"Walidacja polityki strategicznej B61: "
        f"{response.get('status', 'UNKNOWN')}"
    ]
    lines.append(
        "Nadzorca B61: "
        + ("AKTYWNY" if runtime.get("enabled") else "WYŁĄCZONY")
    )
    lines.append(f"Faza: {runtime.get('phase', 'IDLE')}")
    lines.append(f"Cykle B61: {runtime.get('cycles_completed', 0)}")
    lines.append(
        "Eksperymenty: "
        f"{summary.get('experiments', 0)}, "
        f"zaliczone {summary.get('passed', 0)}, "
        f"promowane {summary.get('promoted', 0)}, "
        f"odrzucone {summary.get('rejected', 0)}, "
        f"wstrzymane {summary.get('held', 0)}"
    )
    decision = str(response.get("decision", runtime.get("last_decision", "")))
    if decision:
        lines.append(f"Decyzja walidacji: {decision}")
    reason = str(response.get("reason", "")).strip()
    if reason:
        lines.append(f"Uzasadnienie: {reason}")
    if metrics:
        lines.append(
            "Replay B61: "
            f"dowody {metrics.get('observations', 0)}, "
            f"użyteczność bazowa {metrics.get('baseline_utility', 0)}, "
            f"challenger {metrics.get('candidate_utility', 0)}, "
            f"zmiana {metrics.get('utility_improvement', 0)}"
        )
        lines.append(
            "Ryzyko replay: "
            f"wzrost błędów {metrics.get('failure_exposure_increase', 0)}, "
            f"wzrost odroczeń {metrics.get('deferred_exposure_increase', 0)}, "
            f"zgodność TOP-K {float(metrics.get('top_k_overlap', 0)) * 100:.1f}%"
        )
    checks = _mapping(response.get("checks"))
    if checks:
        failed = [key for key, value in checks.items() if value is False]
        lines.append(
            "Kontrole bezpieczeństwa: "
            + ("OK" if not failed else "NIE: " + ", ".join(failed))
        )
    experiment = _mapping(response.get("experiment")) or _mapping(
        response.get("latest_experiment")
    )
    if experiment:
        lines.append(
            "Eksperyment: "
            f"{experiment.get('experiment_id', '-')} | "
            f"{experiment.get('status', 'UNKNOWN')} | "
            f"wersja {experiment.get('revision_id', '-')}"
        )
    proposal = _mapping(response.get("proposal"))
    if proposal:
        lines.append(
            "Propozycja B60: "
            f"{proposal.get('revision_id', '-')} | "
            f"dowody {proposal.get('evidence_count', 0)} | "
            f"pewność {proposal.get('confidence', 0)}"
        )
    experiments = response.get("experiments", [])
    if isinstance(experiments, list) and experiments:
        lines.append(f"Ostatnie eksperymenty B61: {len(experiments)}")
        for item in experiments[:8]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('experiment_id', '-')} | "
                    f"{item.get('status', 'UNKNOWN')} | "
                    f"{item.get('decision', '')} | "
                    f"dowody {item.get('evidence_count', 0)}"
                )
    history = response.get("history", [])
    if isinstance(history, list) and history:
        lines.append(f"Historia B61: {len(history)}")
        for item in history[:8]:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('status', 'UNKNOWN')} | "
                    f"{item.get('decision', '')} | "
                    f"{item.get('revision_id', '')}"
                )
    b60_policy = _mapping(response.get("b60_policy"))
    if b60_policy:
        lines.append(
            "Bramka B60: auto-zastosowanie bez walidacji "
            f"{'TAK' if b60_policy.get('auto_apply_safe_changes') else 'NIE'}"
        )
    if policy:
        lines.append(
            "Polityka B61: "
            f"cykl {policy.get('validation_interval_seconds', 300)} s, "
            f"min dowodów {policy.get('min_observations', 3)}, "
            f"TOP-K {policy.get('top_k', 5)}, "
            f"auto-promocja {'TAK' if policy.get('auto_promote_validated') else 'NIE'}, "
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
