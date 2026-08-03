from __future__ import annotations

from typing import Any


def format_autonomous_learning_response(
    response: dict[str, Any],
) -> str:
    status = str(
        response.get(
            "status",
            "AUTONOMOUS_LEARNING_UNKNOWN",
        )
    )
    profile = dict(
        response.get("profile", {})
        if isinstance(response.get("profile"), dict)
        else {}
    )
    store = dict(
        response.get("store", {})
        if isinstance(response.get("store"), dict)
        else {}
    )
    analysis = dict(
        response.get("analysis", {})
        if isinstance(response.get("analysis"), dict)
        else {}
    )
    lines = [
        f"Uczenie autonomii: {status}",
    ]

    training_run_id = str(
        response.get("training_run_id", "")
    ).strip()
    if training_run_id:
        lines.append(
            f"Run ID uczenia: {training_run_id}"
        )

    observations = int(
        analysis.get(
            "observations",
            profile.get(
                "observations",
                store.get("profile_observations", 0),
            ),
        )
        or 0
    )
    lines.append(
        f"Obserwacje: {observations}"
    )

    if analysis:
        lines.extend(
            [
                (
                    "Skuteczność: "
                    f"{float(analysis.get('success_rate', 0.0)):.1%}"
                ),
                (
                    "Rollbacki: "
                    f"{float(analysis.get('rollback_rate', 0.0)):.1%}"
                ),
                (
                    "Przebiegi z retry: "
                    f"{float(analysis.get('retry_rate', 0.0)):.1%}"
                ),
            ]
        )

    if profile:
        lines.extend(
            [
                (
                    "Profil aktywny: "
                    f"{'TAK' if profile.get('active') else 'NIE'}"
                ),
                (
                    "Pewność profilu: "
                    f"{float(profile.get('confidence', 0.0)):.1%}"
                ),
            ]
        )
        constraints = dict(
            profile.get("optimizer_constraints", {})
            if isinstance(profile.get("optimizer_constraints"), dict)
            else {}
        )
        if constraints:
            lines.append(
                "Limity: "
                f"min score {constraints.get('min_score', 0)}, "
                f"max risk {constraints.get('max_risk', 10)}, "
                f"max kampanii {constraints.get('max_campaigns', 30)}"
            )

        recommendations = profile.get("recommendations", [])
        if isinstance(recommendations, list):
            for item in recommendations[:5]:
                text = str(item).strip()
                if text:
                    lines.append(
                        f"- {text}"
                    )

    if status == "AUTONOMOUS_LEARNING_INSUFFICIENT_DATA":
        lines.append(
            "Profil pozostaje nieaktywny do zebrania większej historii."
        )

    report_path = str(
        response.get(
            "report_path",
            store.get("path", ""),
        )
    ).strip()
    if report_path:
        lines.append(
            f"Raport: {report_path}"
        )

    errors = response.get("errors", [])
    if isinstance(errors, list):
        for error in errors[:5]:
            lines.append(
                f"Błąd: {error}"
            )

    return "\n".join(lines)
