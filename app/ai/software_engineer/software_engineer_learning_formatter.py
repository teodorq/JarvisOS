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
    profile = _mapping(response.get("profile"))
    store = _mapping(response.get("store"))
    last_training = _mapping(
        response.get("last_training_run")
    )
    analysis = _mapping(response.get("analysis"))
    training_state = _mapping(response.get("training_state"))
    auto_training = _mapping(response.get("auto_training"))
    deployment = _mapping(response.get("deployment"))
    profile_versions = response.get("profile_versions", [])

    if not analysis:
        analysis = _mapping(
            last_training.get("analysis")
        )

    lines = [
        f"Uczenie autonomii: {status}",
    ]

    training_run_id = str(
        response.get(
            "training_run_id",
            last_training.get(
                "training_run_id",
                "",
            ),
        )
    ).strip()
    if training_run_id:
        lines.append(
            f"Ostatni Run ID uczenia: {training_run_id}"
        )

    episodes = _safe_int(
        store.get("episodes", 0)
    )
    training_runs = _safe_int(
        store.get("training_runs", 0)
    )
    observations = _safe_int(
        analysis.get(
            "observations",
            profile.get(
                "observations",
                store.get(
                    "profile_observations",
                    episodes,
                ),
            ),
        )
    )

    lines.extend(
        [
            f"Epizody: {episodes}",
            f"Przebiegi uczenia: {training_runs}",
            f"Obserwacje: {observations}",
        ]
    )

    if training_state:
        lines.append(
            "Automatyczny trening: "
            f"{'WŁĄCZONY' if training_state.get('auto_training_enabled', True) else 'WYŁĄCZONY'}"
        )
        lines.append(
            "Próg treningu: "
            f"{_safe_int(training_state.get('minimum_observations', 5))} epizodów, "
            f"co {_safe_int(training_state.get('minimum_new_episodes', 1))} nowych"
        )
        last_status = str(
            training_state.get("last_deployment_status", "")
        ).strip()
        if last_status:
            lines.append(f"Ostatnie wdrożenie: {last_status}")

    if auto_training:
        auto_status = str(auto_training.get("status", "")).strip()
        if auto_status:
            lines.append(f"Stan auto-treningu: {auto_status}")

    active_version = str(
        store.get(
            "active_profile_version_id",
            profile.get("profile_version_id", ""),
        )
    ).strip()
    if active_version:
        lines.append(f"Aktywna wersja profilu: {active_version}")

    if isinstance(profile_versions, list) and profile_versions:
        lines.append(f"Wersje profilu: {len(profile_versions)}")
        for item in profile_versions[:5]:
            if not isinstance(item, dict):
                continue
            version_id = str(item.get("version_id", "")).strip()
            version_status = str(
                item.get("deployment_status", "UNKNOWN")
            ).strip()
            confidence = _safe_float(
                _mapping(item.get("profile")).get("confidence", 0.0)
            )
            if version_id:
                lines.append(
                    f"- {version_id}: {version_status}, pewność {confidence:.1%}"
                )

    if deployment:
        deployment_status = str(deployment.get("status", "")).strip()
        if deployment_status:
            lines.append(f"Decyzja wdrożenia: {deployment_status}")

    if analysis:
        lines.extend(
            [
                (
                    "Skuteczność: "
                    f"{_safe_float(analysis.get('success_rate')):.1%}"
                ),
                (
                    "Rollbacki: "
                    f"{_safe_float(analysis.get('rollback_rate')):.1%}"
                ),
                (
                    "Przebiegi z retry: "
                    f"{_safe_float(analysis.get('retry_rate')):.1%}"
                ),
            ]
        )
    elif episodes:
        lines.append(
            "Metryki sukcesów, retry i rollbacków pojawią się "
            "po uruchomieniu uczenia na zapisanych epizodach."
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
                    f"{_safe_float(profile.get('confidence')):.1%}"
                ),
            ]
        )
        constraints = _mapping(
            profile.get("optimizer_constraints")
        )
        if constraints:
            lines.append(
                "Limity: "
                f"min score {constraints.get('min_score', 0)}, "
                f"max risk {constraints.get('max_risk', 10)}, "
                f"max kampanii {constraints.get('max_campaigns', 30)}"
            )

        recommendations = profile.get(
            "recommendations",
            [],
        )
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
    elif status == "AUTONOMOUS_LEARNING_PROFILE_STAGED":
        lines.append(
            "Profil zapisano jako kandydat, ale próg pewności nie pozwolił go aktywować."
        )
    elif status in {
        "AUTONOMOUS_LEARNING_PROFILE_APPLIED",
        "AUTONOMOUS_TRAINING_PROFILE_DEPLOYED",
        "AUTONOMOUS_PROFILE_DEPLOYED",
    }:
        lines.append("Nowy profil został bezpiecznie aktywowany.")
    elif status == "AUTONOMOUS_PROFILE_ROLLED_BACK":
        lines.append("Przywrócono poprzednią aktywną wersję profilu.")

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


def _mapping(
    value: Any,
) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_int(
    value: Any,
) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(
    value: Any,
) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
