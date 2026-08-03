from __future__ import annotations

from typing import Any

from .autonomous_diagnostics_models import AutonomousDiagnostic


class AutonomousDiagnosticsAnalyzer:
    """Classifies the real root cause instead of the final retry symptom."""

    APPROVAL_STATUSES = {
        "PREVIEW_READY",
        "CAMPAIGN_PREVIEW_READY",
        "WAITING_FOR_APPROVAL",
        "APPROVAL_REQUIRED",
        "AUTOMATIC_APPROVAL_BLOCKED",
        "APPROVAL_BLOCKED",
    }

    def analyze(
        self,
        snapshot: dict[str, Any],
        evidence: dict[str, Any],
    ) -> AutonomousDiagnostic:
        ids = dict(snapshot.get("identifiers", {}) or {})
        statuses = [str(item).upper() for item in evidence.get("statuses", [])]
        errors = [str(item) for item in evidence.get("errors", [])]
        haystack = "\n".join([*statuses, *errors]).casefold()
        source_status = self._source_status(snapshot, statuses)
        category = "UNKNOWN"
        severity = "WARNING"
        stage = self._stage(snapshot, evidence)
        root_cause = "Nie udało się jednoznacznie ustalić przyczyny."
        summary = "Autonomia wymaga dokładniejszej diagnostyki."
        retryable = False
        repairable = False
        requires_approval = False
        repair_type = "NONE"
        actions = [
            "Sprawdź pełny raport diagnostyczny i ostatni wynik wykonania."
        ]

        if any(status in {"FULL_AUTONOMY_COMPLETED", "COMPLETED", "CAMPAIGN_COMPLETED"} for status in statuses) and not any("FAILED" in status for status in statuses):
            category = "SUCCESS"
            severity = "INFO"
            root_cause = "Przebieg zakończył się pomyślnie."
            summary = "Brak awarii wymagającej naprawy."
            actions = []
        elif self._has_approval_evidence(statuses, haystack, snapshot):
            category = "APPROVAL_REQUIRED"
            severity = "INFO"
            root_cause = (
                "Wykonanie zatrzymało się na bezpiecznym podglądzie zmian. "
                "Kod nie został zmieniony, ponieważ brakowało jawnej akceptacji."
            )
            summary = "Zadanie czeka na zatwierdzenie przygotowanej transakcji."
            repairable = True
            requires_approval = True
            repair_type = "ONE_TIME_APPROVAL"
            actions = [
                "Uruchom bezpieczną naprawę zadania i potwierdź ją w GUI.",
                "Jednorazowa akceptacja nie zmienia globalnej polityki auto_approve.",
            ]
        elif "target już istnieje" in haystack or "already exists" in haystack:
            category = "TARGET_CONFLICT"
            severity = "WARNING"
            root_cause = (
                "Co najmniej jeden plik docelowy już istnieje, a polityka "
                "bezpieczeństwa blokuje jego automatyczne nadpisanie."
            )
            summary = "Bezpieczna blokada istniejącego celu."
            actions = [
                "Wybierz nową nazwę modułu albo jawnie zaplanuj refaktoryzację istniejących plików."
            ]
        elif self._contains(statuses, "VALIDATION_FAILED") or "test" in haystack and "failed" in haystack:
            category = "VALIDATION_FAILED"
            severity = "ERROR"
            root_cause = "Walidacja lub zestaw testów nie przeszedł pomyślnie."
            summary = "Zmiana nie spełniła kryteriów walidacji."
            repairable = True
            repair_type = "GENERATE_REPAIR_PROPOSAL"
            actions = [
                "Wygeneruj propozycję poprawki na podstawie stderr, stdout i listy plików.",
                "Nie wykonuj automatycznego zapisu bez ponownej walidacji i rollbacku."
            ]
        elif self._has_constraints_pause_evidence(
            snapshot,
            statuses,
            errors,
        ):
            category = "CONSTRAINTS_PAUSE"
            severity = "WARNING"
            root_cause = (
                "Żadna kampania nie spełniła aktualnych ograniczeń wykonania."
            )
            summary = "Dyrektor zatrzymał portfolio ze względu na ograniczenia."
            retryable = False
            repairable = False
            repair_type = "NONE"
            actions = [
                "Odrocz to zadanie i wybierz następną bezpieczną możliwość bez osłabiania bramek bezpieczeństwa."
            ]
        elif "dependency" in haystack or "zależ" in haystack:
            category = "DEPENDENCY_BLOCKED"
            severity = "ERROR"
            root_cause = "Zadanie lub kampania jest zablokowana przez nieudaną zależność."
            summary = "Nie można kontynuować przed naprawą zależności."
            repairable = True
            repair_type = "RESET_DEPENDENCY_STATE"
            actions = ["Napraw zależność, a następnie bezpiecznie wznów zadanie."]
        elif "waiting_resources" in haystack or "resource" in haystack:
            category = "RESOURCE_LIMIT"
            severity = "INFO"
            root_cause = "Zasoby komputera przekroczyły skonfigurowane limity."
            summary = "Zadanie oczekuje na bezpieczne zasoby."
            retryable = True
            actions = ["Poczekaj na spadek użycia CPU/RAM albo zmień limity po potwierdzeniu."]
        elif self._contains(statuses, "PLANNING_FAILED"):
            category = "PLANNING_FAILED"
            severity = "ERROR"
            root_cause = "Planer nie zbudował poprawnego planu wykonania."
            summary = "Błąd etapu planowania."
            repairable = True
            repair_type = "REPLAN"
            actions = ["Utwórz nowy plan z doprecyzowanym celem i bez nadpisywania istniejących plików."]
        elif evidence.get("traceback") or "exception" in haystack or "traceback" in haystack:
            category = "EXECUTION_EXCEPTION"
            severity = "CRITICAL"
            root_cause = "Wykonanie przerwał wyjątek programu."
            summary = "Wyjątek w autonomicznym pipeline."
            retryable = self._looks_transient(haystack)
            repairable = retryable
            repair_type = "RESET_TRANSIENT" if retryable else "GENERATE_REPAIR_PROPOSAL"
            actions = ["Sprawdź traceback i dokładny moduł, który zgłosił wyjątek."]
        elif "cycle_limit" in haystack:
            category = "CYCLE_LIMIT"
            severity = "WARNING"
            root_cause = "Dyrektor osiągnął limit cykli bez zakończenia kampanii."
            summary = "Pętla wykonania nie osiągnęła postępu przed limitem cykli."
            repairable = True
            repair_type = "RESET_STALLED_STATE"
            actions = ["Zresetuj wyłącznie stan zablokowanej kampanii i uruchom jeden kontrolowany cykl."]
        elif "rollback" in haystack and "failed" in haystack:
            category = "ROLLBACK_FAILED"
            severity = "CRITICAL"
            root_cause = "Rollback nie przywrócił wszystkich plików."
            summary = "Wymagana ręczna kontrola spójności projektu."
            actions = ["Nie uruchamiaj kolejnej zmiany przed sprawdzeniem manifestu backupu."]
        elif "limit prób" in haystack or "attempts_exhausted" in haystack:
            category = "ATTEMPTS_EXHAUSTED"
            severity = "ERROR"
            root_cause = "Wyczerpano budżet prób, ale brak głębszego dowodu przyczyny."
            summary = "Zadanie zatrzymane po przekroczeniu limitu prób."
            actions = ["Nie zeruj prób bez ustalenia pierwotnej przyczyny."]

        evidence_summary = {
            "current_stage_id": evidence.get("current_stage_id", ""),
            "current_campaign_id": evidence.get("current_campaign_id", ""),
            "status_count": len(statuses),
            "error_count": len(errors),
        }
        return AutonomousDiagnostic(
            job_id=str(ids.get("job_id", "")),
            autonomy_run_id=str(ids.get("autonomy_run_id", "")),
            portfolio_id=str(ids.get("portfolio_id", "")),
            director_run_id=str(ids.get("director_run_id", "")),
            source_status=source_status,
            category=category,
            severity=severity,
            stage=stage,
            summary=summary,
            root_cause=root_cause,
            retryable=retryable,
            repairable=repairable,
            requires_approval=requires_approval,
            repair_type=repair_type,
            errors=errors,
            traceback=str(evidence.get("traceback", "")),
            stdout=str(evidence.get("stdout", "")),
            stderr=str(evidence.get("stderr", "")),
            files=[str(item) for item in evidence.get("files", [])],
            statuses=statuses,
            suggested_actions=actions,
            evidence=evidence_summary,
            metadata={
                "maximum_risk": self._maximum_risk(snapshot),
                "approval_evidence": requires_approval,
            },
        )

    @classmethod
    def _has_constraints_pause_evidence(
        cls,
        snapshot: dict[str, Any],
        statuses: list[str],
        errors: list[str],
    ) -> bool:
        markers = {
            "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS",
            "MULTI_CAMPAIGN_PAUSED_CONSTRAINTS",
            "PORTFOLIO_PAUSED_CONSTRAINTS",
            "SCORE_BELOW_MINIMUM",
            "CONSTRAINTS_PAUSE",
        }
        if markers.intersection(statuses):
            return True
        if any(str(item).strip().upper() in markers for item in errors):
            return True

        evidence_keys = {
            "status",
            "state",
            "event",
            "director_status",
            "portfolio_status",
            "reason",
            "reasons",
            "error",
            "errors",
        }

        def walk(value: Any, *, key: str = "", depth: int = 0) -> bool:
            if depth > 10:
                return False
            if isinstance(value, dict):
                for child_key, child in value.items():
                    normalized = str(child_key).casefold()
                    if normalized in evidence_keys and walk(
                        child,
                        key=normalized,
                        depth=depth + 1,
                    ):
                        return True
                    if isinstance(child, (dict, list)) and walk(
                        child,
                        key=normalized,
                        depth=depth + 1,
                    ):
                        return True
                return False
            if isinstance(value, list):
                return any(
                    walk(item, key=key, depth=depth + 1)
                    for item in value[:200]
                )
            if key not in evidence_keys:
                return False
            return str(value).strip().upper() in markers

        return walk(snapshot)

    @classmethod
    def _has_approval_evidence(
        cls,
        statuses: list[str],
        haystack: str,
        snapshot: dict[str, Any],
    ) -> bool:
        if cls.APPROVAL_STATUSES.intersection(statuses):
            return True
        if "waiting_for_approval" in haystack or "preview_ready" in haystack:
            return True
        for campaign in snapshot.get("campaigns", []):
            if not isinstance(campaign, dict):
                continue
            for stage in campaign.get("stages", []):
                if isinstance(stage, dict) and str(stage.get("status", "")).upper() == "PREVIEW_READY":
                    return True
        return False

    @staticmethod
    def _source_status(snapshot: dict[str, Any], statuses: list[str]) -> str:
        for key in ("response", "job", "run", "director", "portfolio"):
            value = snapshot.get(key, {})
            if isinstance(value, dict):
                status = str(value.get("status", value.get("state", ""))).strip()
                if status:
                    return status.upper()
        return statuses[0] if statuses else "UNKNOWN"

    @staticmethod
    def _stage(snapshot: dict[str, Any], evidence: dict[str, Any]) -> str:
        if evidence.get("current_stage_id"):
            return str(evidence["current_stage_id"])
        for campaign in snapshot.get("campaigns", []):
            if not isinstance(campaign, dict):
                continue
            for stage in campaign.get("stages", []):
                if not isinstance(stage, dict):
                    continue
                status = str(stage.get("status", "")).upper()
                if status in {"FAILED", "PREVIEW_READY", "RUNNING"}:
                    return str(stage.get("stage_id", "UNKNOWN"))
        return "UNKNOWN"

    @staticmethod
    def _maximum_risk(snapshot: dict[str, Any]) -> float:
        risks: list[float] = []
        portfolio = snapshot.get("portfolio", {})
        for campaign in portfolio.get("campaigns", []) if isinstance(portfolio, dict) else []:
            if not isinstance(campaign, dict):
                continue
            try:
                risks.append(float(dict(campaign.get("metadata", {}) or {}).get("estimated_risk", 0.0)))
            except (TypeError, ValueError):
                raise RuntimeError("AutoDev: przechwycony wyjątek")
        return max(risks, default=0.0)

    @staticmethod
    def _contains(statuses: list[str], fragment: str) -> bool:
        return any(fragment in status for status in statuses)

    @staticmethod
    def _looks_transient(haystack: str) -> bool:
        return any(
            token in haystack
            for token in ("timeout", "tempor", "locked", "busy", "connection", "resource")
        )
