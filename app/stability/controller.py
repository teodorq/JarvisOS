from __future__ import annotations

from pathlib import Path
from typing import Any

from app.assistant.natural_language import fold_text
from app.core.project_paths import resolve_project_root
from app.stability.beta_readiness import BusinessBetaReadinessCenter
from app.stability.performance_center import RuntimePerformanceCenter
from app.stability.recovery_center import RuntimeRecoveryCenter
from app.stability.scenario_validator import ScenarioValidationCenter
from app.stability.service_restart import SafeServiceRestartCenter


class StabilitySuiteController:
    """B111-B115 local stability, recovery and Business Beta gates."""

    STAGES = {
        "B111": "REAL_SCENARIO_VALIDATION_READY",
        "B112": "RUNTIME_PERFORMANCE_READY",
        "B113": "RUNTIME_RECOVERY_READY",
        "B114": "SAFE_SERVICE_RESTART_READY",
        "B115": "BUSINESS_BETA_READINESS_READY",
    }
    READ_ONLY = {"suite_status", "scenario_status", "performance_status", "recovery_status", "restart_status", "beta_status"}

    def __init__(self, project_root: str | Path | None = None, runtime_status=None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.runtime_status = runtime_status or (lambda: {})
        self.scenarios = ScenarioValidationCenter(self.project_root)
        self.performance = RuntimePerformanceCenter(self.project_root)
        self.recovery = RuntimeRecoveryCenter(self.project_root)
        self.restarts = SafeServiceRestartCenter(self.project_root)
        self.beta = BusinessBetaReadinessCenter(self.project_root)
        self._runtime_state = {"generation": 1, "mode": "OWNER", "safe": True}
        self.restarts.register("stability_runtime", self._snapshot_runtime, self._restart_runtime, self._restore_runtime)

    @staticmethod
    def matches(command: object) -> bool:
        value = fold_text(command)
        phrases = (
            "status b111", "uruchom testy scenariuszy", "testy realnych scenariuszy",
            "status b112", "test wydajnosci", "sonda wydajnosci", "uporzadkuj dane wydajnosci",
            "status b113", "symuluj zawieszenie", "sprawdz odzyskiwanie", "odzyskaj usluge",
            "status b114", "przygotuj restart uslugi", "wykonaj restart uslugi",
            "status b115", "audyt business beta", "potwierdz business beta",
            "status b111-b115", "stabilnosc i beta", "centrum stabilnosci",
        )
        return any(phrase in value for phrase in phrases)

    def plan(self, command: object) -> dict[str, Any]:
        intent = self.intent(command)
        return {
            "command": str(command),
            "goal": "Zweryfikować stabilność, odzyskiwanie i gotowość Business Beta",
            "plan": [
                "Rozpoznać walidację, wydajność, recovery, restart albo bramki Beta",
                "Odczytać lokalny stan i bezpieczne ustawienia",
                "Wykonać ograniczony test bez publikacji i bez kodu zdalnego",
                "Zapisać wynik oraz dowód przywrócenia stanu",
                "Zablokować Business Beta, jeżeli choć jedna bramka nie przejdzie",
            ],
            "actions": [], "can_execute": True, "handler": "personal_assistant",
            "assistant_intent": intent, "read_only": intent in self.READ_ONLY,
        }

    def handle(self, command: object) -> str:
        intent = self.intent(command)
        if intent == "scenario_run":
            result = self.scenarios.run(self.runtime_status())
            return f"B111: scenariusze {result['status']}; zaliczone {result['passed']}/{result['total']}."
        if intent == "performance_probe":
            result = self.performance.probe()
            return f"B112: wydajność {result['status']}; wynik {result['score']}/100; RAM procesu {result['rss_mb']} MB."
        if intent == "performance_compact":
            result = self.performance.compact()
            return f"B112: uporządkowano historię; usunięte rekordy {result['removed']}."
        if intent == "recovery_demo":
            self.recovery.simulate_stale("voice")
            created = self.recovery.check()
            return f"B113: wykryto incydenty {len(created)}; usługa voice oznaczona jako niereagująca."
        if intent == "recovery_execute":
            result = self.recovery.recover()
            return f"B113: {result['status']}; usługa {result['service']}."
        if intent == "restart_prepare":
            result = self.restarts.prepare("stability_runtime")
            return f"B114: przygotowano plan {result['plan_id']} i checkpoint SHA-256."
        if intent == "restart_execute":
            result = self.restarts.execute()
            return f"B114: restart {result['status']}; stan przywrócony {'TAK' if result['state_restored'] else 'NIE'}."
        if intent == "beta_audit":
            result = self.beta.audit(self._beta_snapshot())
            return f"B115: audyt {result['status']}; bramki {result['passed']}/{result['total']}."
        if intent == "beta_confirm":
            result = self.beta.confirm()
            return f"B115: {result['status']}; automatyczna publikacja NIE."
        return self._status_text(intent)

    def status(self) -> dict[str, Any]:
        return {
            "status": "STABILITY_RECOVERY_BETA_SUITE_READY",
            "stages": dict(self.STAGES),
            "scenarios": self.scenarios.status(), "performance": self.performance.status(),
            "recovery": self.recovery.status(), "restart": self.restarts.status(),
            "beta": self.beta.status(),
            "safety": {"auto_approve": False, "remote_code": False, "automatic_publication": False, "max_active_executions": 1},
        }

    @staticmethod
    def intent(command: object) -> str:
        value = fold_text(command)
        if "uruchom testy scenariuszy" in value or "testy realnych scenariuszy" in value:
            return "scenario_run"
        if "test wydajnosci" in value or "sonda wydajnosci" in value:
            return "performance_probe"
        if "uporzadkuj dane wydajnosci" in value:
            return "performance_compact"
        if "symuluj zawieszenie" in value or "sprawdz odzyskiwanie" in value:
            return "recovery_demo"
        if "odzyskaj usluge" in value:
            return "recovery_execute"
        if "przygotuj restart uslugi" in value:
            return "restart_prepare"
        if "wykonaj restart uslugi" in value:
            return "restart_execute"
        if "audyt business beta" in value:
            return "beta_audit"
        if "potwierdz business beta" in value:
            return "beta_confirm"
        for stage, intent in (("b111", "scenario_status"), ("b112", "performance_status"), ("b113", "recovery_status"), ("b114", "restart_status"), ("b115", "beta_status")):
            if f"status {stage}" in value:
                return intent
        return "suite_status"

    def _status_text(self, intent: str) -> str:
        status = self.status()
        mapping = {
            "scenario_status": ("B111", status["scenarios"]),
            "performance_status": ("B112", status["performance"]),
            "recovery_status": ("B113", status["recovery"]),
            "restart_status": ("B114", status["restart"]),
            "beta_status": ("B115", status["beta"]),
        }
        if intent in mapping:
            prefix, value = mapping[intent]
            return f"{prefix}: {value['status']}; {self._summary(prefix, value)}"
        return (
            "B111–B115: walidacja scenariuszy, wydajność, recovery, bezpieczny restart "
            f"i Business Beta GOTOWE. Beta: {status['beta']['latest_audit_status']}."
        )

    @staticmethod
    def _summary(prefix: str, value: dict[str, Any]) -> str:
        summaries = {
            "B111": f"testy {value.get('run_count', 0)}, ostatni {value.get('latest_status', 'NOT_RUN')}",
            "B112": f"wynik {value.get('latest_score', 0)}/100, RAM {value.get('rss_mb', 0)} MB",
            "B113": f"otwarte incydenty {value.get('open_incident_count', 0)}, odzyskania {value.get('recovery_count', 0)}",
            "B114": f"wykonania {value.get('execution_count', 0)}, stan przywrócony {value.get('state_restored', False)}",
            "B115": f"bramki {value.get('gates_passed', 0)}/{value.get('gates_total', 5)}, beta {value.get('beta_ready', False)}",
        }
        return summaries[prefix]

    def _beta_snapshot(self) -> dict[str, Any]:
        runtime = dict(self.runtime_status() or {})
        safety = dict(runtime.get("safety", {}) or {})
        return {
            "scenario_status": self.scenarios.status()["latest_status"],
            "performance_score": self.performance.status()["latest_score"],
            "open_incidents": self.recovery.status()["open_incident_count"],
            "restart_restored": self.restarts.status()["state_restored"],
            "safe_defaults": safety.get("auto_approve") is False and safety.get("remote_code_execution") is False,
        }

    def _snapshot_runtime(self) -> dict[str, Any]:
        return dict(self._runtime_state)

    def _restart_runtime(self) -> None:
        self._runtime_state = {"generation": self._runtime_state["generation"] + 1, "mode": "RESTARTING", "safe": True}

    def _restore_runtime(self, checkpoint: dict[str, Any]) -> None:
        self._runtime_state = dict(checkpoint)
