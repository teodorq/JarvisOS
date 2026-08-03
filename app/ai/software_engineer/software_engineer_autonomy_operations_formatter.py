from __future__ import annotations

from typing import Any

from .business_commercial_formatter import format_business_commercial_response


def format_autonomy_operations_response(response: dict[str, Any]) -> str:
    stage = str(response.get("stage", "B71"))
    if stage in {f"B{value}" for value in range(89, 96)} or stage == "B89-B95":
        return format_business_commercial_response(response)
    runtime = _mapping(response.get("runtime"))
    lines = [f"Autonomia JARVIS {stage}: {response.get('status', 'UNKNOWN')}"]
    lines.append(f"Faza: {runtime.get('phase', 'IDLE')}")
    lines.append(f"Cykle: {runtime.get('cycles_completed', 0)}")

    if stage == "B71":
        counts = _mapping(response.get("execution_counts"))
        lines.append(
            "Wykonania odzyskiwania: "
            f"ukończone {counts.get('completed', 0)}, "
            f"nieudane {counts.get('failed', 0)}, "
            f"wycofane {counts.get('rolled_back', 0)}"
        )
        execution = _mapping(response.get("execution"))
        if execution:
            lines.append(
                f"Ostatnie wykonanie: {execution.get('execution_id', '-')} | "
                f"{execution.get('status', 'UNKNOWN')} | "
                f"{execution.get('category', 'UNKNOWN')}"
            )
        lines.append("Wykonanie B71 zawsze wymaga jawnego potwierdzenia.")
    elif stage == "B72":
        lessons = response.get("lessons", [])
        blocked = response.get("blocked_categories", [])
        lines.append(f"Lekcje napraw: {len(lessons) if isinstance(lessons, list) else 0}")
        lines.append(
            "Zablokowane kategorie: "
            + (
                ", ".join(str(item) for item in blocked[:8])
                if isinstance(blocked, list) and blocked else "0"
            )
        )
    elif stage == "B73":
        snapshot = _mapping(response.get("snapshot"))
        lines.append(
            f"Aktywne nadzorcy: {len(snapshot.get('running_stages', []) or [])}"
        )
        lines.append(f"Aktywne dzierżawy B64: {snapshot.get('active_leases', 0)}")
        lines.append(f"Otwarte incydenty B69: {snapshot.get('open_incidents', 0)}")
        lines.append(
            f"Gotowe plany B70: {snapshot.get('ready_recovery_plans', 0)}"
        )
        stages = _mapping(response.get("stage_summaries"))
        if stages:
            lines.append("Etapy B62-B79:")
            for key in sorted(stages):
                item = _mapping(stages[key])
                lines.append(
                    f"- {key}: {item.get('phase', 'IDLE')} | "
                    f"cykle {item.get('cycles_completed', 0)}"
                )
    elif stage == "B74":
        events = response.get("events", [])
        lines.append(
            f"Zdarzenia watchdoga: {len(events) if isinstance(events, list) else 0}"
        )
        if isinstance(events, list):
            for item in events[:8]:
                if isinstance(item, dict):
                    lines.append(
                        f"- {item.get('stage_name', '-')} | "
                        f"{item.get('category', 'UNKNOWN')} | "
                        f"{item.get('action', 'OBSERVED')}"
                    )
    elif stage == "B75":
        counts = _mapping(response.get("deployment_counts"))
        lines.append(
            "Wdrożenia: "
            f"preview {counts.get('preview_ready', 0)}, "
            f"canary {counts.get('canary', 0)}, "
            f"promowane {counts.get('promoted', 0)}, "
            f"rollback {counts.get('rolled_back', 0)}"
        )
        lines.append("Promocja i rollback wymagają jawnego potwierdzenia.")
    elif stage == "B76":
        counts = _mapping(response.get("release_counts"))
        lines.append(
            "Release train: "
            f"gotowe {counts.get('ready_for_stable_mark', 0)}, "
            f"stabilne {counts.get('stable', 0)}, "
            f"zastąpione {counts.get('superseded', 0)}"
        )
    elif stage == "B77":
        memories = response.get("memories", [])
        lines.append(
            f"Pamięć rozwoju: {len(memories) if isinstance(memories, list) else 0}"
        )
        lines.append(
            f"Lekcje sukcesu: {response.get('successful_lessons', 0)}, "
            f"lekcje błędów: {response.get('failure_lessons', 0)}"
        )
    elif stage == "B78":
        findings = response.get("findings", [])
        lines.append(
            f"Znaleziska bezpieczeństwa: "
            f"{len(findings) if isinstance(findings, list) else 0}"
        )
        if isinstance(findings, list):
            for item in findings[:8]:
                if isinstance(item, dict):
                    lines.append(
                        f"- {item.get('severity', 'INFO')} | "
                        f"{item.get('category', 'UNKNOWN')} | "
                        f"{item.get('path', '')}"
                    )
    elif stage == "B79":
        counts = _mapping(response.get("cycle_counts"))
        lines.append(
            "Cykle produkcyjne: "
            f"ukończone {counts.get('completed', 0)}, "
            f"degraded {counts.get('degraded', 0)}"
        )
        lines.append("B79 nie zatwierdza ani nie wykonuje zmian kodu automatycznie.")
    elif stage == "B84":
        counts = _mapping(response.get("decision_counts"))
        lines.append(
            f"Zdarzenia audytu: {response.get('event_count', 0)} | "
            f"zezwolenia {counts.get('ALLOW', 0)} | odmowy {counts.get('DENY', 0)}"
        )
        exports = response.get("exports", [])
        lines.append(f"Eksporty audytu: {len(exports) if isinstance(exports, list) else 0}")
    elif stage == "B85":
        latest = _mapping(response.get("latest_checkpoint"))
        lines.append(f"Checkpointy: {response.get('checkpoint_count', 0)}")
        if latest:
            lines.append(
                f"Ostatni: {latest.get('checkpoint_id', '-')} | "
                f"{latest.get('verification', 'UNKNOWN')} | pliki {latest.get('file_count', 0)}"
            )
        restore = str(response.get("restore_cmd", "")).strip()
        if restore:
            lines.append(f"Restore offline: {restore}")
    elif stage == "B86":
        lines.append(
            f"Pakiety aktualizacji: {response.get('package_count', 0)} | "
            f"poprawne {response.get('valid_package_count', 0)}"
        )
        staged = _mapping(response.get("staged_update"))
        if staged:
            lines.append(
                f"Staging: {staged.get('version', 'UNKNOWN')} | "
                f"pliki {staged.get('file_count', 0)}"
            )
        installer = str(response.get("installer_cmd", "")).strip()
        if installer:
            lines.append(f"Installer offline: {installer}")
    elif stage == "B84-B86":
        audit = _mapping(response.get("audit"))
        recovery = _mapping(response.get("disaster_recovery"))
        updates = _mapping(response.get("updates"))
        lines.append(
            f"Audyt: {audit.get('event_count', 0)} zdarzeń | "
            f"checkpointy {recovery.get('checkpoint_count', 0)} | "
            f"pakiety aktualizacji {updates.get('valid_package_count', 0)} poprawnych"
        )
    elif stage == "B87":
        first_run = _mapping(response.get("first_run"))
        lines.append(
            f"Instalator: {'GOTOWY' if response.get('installation_ready') else 'WYMAGA UWAGI'} | "
            f"wersja {response.get('version', '-')}"
        )
        lines.append(
            f"Pierwsze uruchomienie: {'GOTOWE' if first_run.get('completed') else 'NIE'} | "
            f"pakiety {response.get('package_count', 0)}"
        )
        package = str(response.get("latest_setup_package") or "").strip()
        if package:
            lines.append(f"Ostatni instalator: {package}")
    elif stage == "B88":
        gates = _mapping(response.get("gates"))
        passed = sum(1 for value in gates.values() if value)
        lines.append(
            f"Release Candidate: {response.get('version', '-')} | "
            f"bramki {passed}/{len(gates)}"
        )
        validation = _mapping(response.get("validation"))
        lines.append(f"Macierz testów: {validation.get('status', 'PENDING')}")
        for name, value in gates.items():
            lines.append(f"- {name}: {'OK' if value else 'WYMAGA UWAGI'}")
        release = str(response.get("latest_release") or "").strip()
        if release:
            lines.append(f"Ostatni RC1: {release}")
    elif stage == "B87-B88":
        installation = _mapping(response.get("installation"))
        release = _mapping(response.get("release_candidate"))
        gates = _mapping(release.get("gates"))
        passed = sum(1 for value in gates.values() if value)
        lines.append(
            f"B87 instalator: {'GOTOWY' if installation.get('installation_ready') else 'UWAGA'} | "
            f"B88 bramki {passed}/{len(gates)}"
        )
    elif stage == "B81":
        profiles = response.get("profiles", [])
        lines.append(
            f"Profile organizacji: {response.get('profile_count', len(profiles) if isinstance(profiles, list) else 0)}"
        )
        lines.append(
            f"Aktywny profil: {response.get('active_profile_id', '-')}"
        )
        if isinstance(profiles, list):
            for item in profiles[:8]:
                if isinstance(item, dict):
                    marker = "*" if item.get("profile_id") == response.get("active_profile_id") else "-"
                    lines.append(
                        f"{marker} {item.get('name', 'Profil')} | "
                        f"{item.get('configuration', {}).get('environment', '-')}"
                    )
    elif stage == "B82":
        license_status = _mapping(response.get("license"))
        if not license_status:
            license_status = _mapping(response)
        lines.append(
            f"Licencja: {license_status.get('status', 'UNKNOWN')} | "
            f"tryb {license_status.get('mode', 'UNKNOWN')}"
        )
        lines.append(
            f"Odcisk komputera: {license_status.get('machine_fingerprint', '-')}"
        )
        lines.append(
            f"Ważna do: {license_status.get('expires_at') or 'bezterminowa'}"
        )
        export_path = str(response.get("export_path", "")).strip()
        if export_path:
            lines.append(f"Pakiet aktywacyjny: {export_path}")
    elif stage == "B83":
        lines.append(
            f"Użytkownik: {response.get('principal', '-')} | "
            f"rola {response.get('active_role', '-')}"
        )
        permissions = response.get("permissions", [])
        if isinstance(permissions, list):
            lines.append(
                "Uprawnienia: "
                + ("PEŁNE" if "*" in permissions else ", ".join(map(str, permissions)) or "BRAK")
            )
        events = response.get("audit_events", [])
        lines.append(
            f"Zdarzenia audytu: {len(events) if isinstance(events, list) else 0}"
        )
    elif stage == "B81-B83":
        profiles = _mapping(response.get("organization_profiles"))
        access = _mapping(response.get("access_control"))
        license_status = _mapping(response.get("license"))
        lines.append(
            f"Profile: {profiles.get('profile_count', 0)} | "
            f"licencja {license_status.get('status', 'UNKNOWN')} | "
            f"rola {access.get('active_role', 'UNKNOWN')}"
        )
    elif stage == "B80":
        business = _mapping(response.get("business"))
        license_status = _mapping(response.get("license"))
        integrity = _mapping(response.get("integrity"))
        safety = _mapping(response.get("safety"))
        lines.append(
            f"Edycja: {business.get('product_name', 'JARVIS OS')} | "
            f"organizacja {business.get('organization', '-')} | "
            f"wydanie {business.get('release', 'B80')}"
        )
        lines.append(
            f"Środowisko: {business.get('environment', 'OWNER DEVELOPMENT')}"
        )
        lines.append(
            f"Licencja: {license_status.get('status', 'UNKNOWN')} | "
            f"tryb {license_status.get('mode', 'UNKNOWN')}"
        )
        lines.append(
            f"Integralność: {integrity.get('status', 'UNKNOWN')} | "
            f"sprawdzono {integrity.get('files_checked', 0)} plików"
        )
        changed = list(integrity.get("changed", []) or [])
        missing = list(integrity.get("missing", []) or [])
        if changed:
            lines.append("Zmienione pliki: " + ", ".join(map(str, changed[:5])))
        if missing:
            lines.append("Brakujące pliki: " + ", ".join(map(str, missing[:5])))
        lines.append(
            "Polityka Business: "
            f"auto-approve {'TAK' if safety.get('auto_approve') else 'NIE'}, "
            f"maks. aktywnych wykonań {safety.get('max_active_executions', 1)}"
        )

    decision = str(response.get("decision", runtime.get("last_decision", "")))
    if decision:
        lines.append(f"Decyzja: {decision}")
    reason = str(response.get("reason", "")).strip()
    if reason:
        lines.append(f"Uzasadnienie: {reason}")
    for error in response.get("errors", [])[:5]:
        lines.append(f"Błąd: {error}")
    lines.append("Bezpieczeństwo: auto-approve NIE, maks. 1 aktywne wykonanie.")
    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport: {report_path}")
    return "\n".join(lines)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
