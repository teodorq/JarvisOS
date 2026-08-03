from __future__ import annotations

import re
from typing import Any

from .autonomous_diagnostics_service import AutonomousDiagnosticsService


class SoftwareEngineerDiagnosticsRouter:
    """Routes diagnostics and safe repair commands before long-running routing."""

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self._is_diagnostics(controller, command=command, context=context):
            return None

        service = getattr(controller, "autonomous_diagnostics_service", None)
        if service is None:
            service = AutonomousDiagnosticsService(controller.project_root)
            controller.autonomous_diagnostics_service = service

        action = self._action(controller, command=command, context=context)
        job_id = self._job_id(command, context)
        run_id = self._run_id(command, context)

        if action in {"job", "repair"} and not job_id:
            return {
                "success": False,
                "status": "AUTONOMOUS_DIAGNOSTIC_JOB_ID_REQUIRED",
                "operation": "autonomous_diagnostics",
                "diagnostic": {},
                "diagnostics": [],
                "repair": {},
                "repairs": [],
                "errors": ["Podaj identyfikator longrun-..."],
            }

        if action == "job":
            return service.diagnose_job(job_id)
        if action == "run":
            if not run_id:
                return {
                    "success": False,
                    "status": "AUTONOMOUS_DIAGNOSTIC_RUN_ID_REQUIRED",
                    "operation": "autonomous_diagnostics",
                    "diagnostic": {},
                    "errors": ["Podaj identyfikator autonomy-..."],
                }
            return service.diagnose_run(run_id)
        if action == "repair":
            return service.repair_job(job_id)
        if action == "repairs":
            return service.repairs(limit=self._bounded_int(context.get("limit", 20), 1, 100))
        if action == "recent":
            return service.recent(
                limit=self._bounded_int(context.get("limit", 20), 1, 100),
                category=str(context.get("category", "")),
            )
        if action == "status":
            return service.status()
        return service.latest(job_id=job_id, run_id=run_id)

    @staticmethod
    def _is_diagnostics(
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> bool:
        operation = str(
            context.get("operation", context.get("mode", ""))
        ).strip().casefold()
        if operation in {
            "autonomous_diagnostics",
            "autonomy_diagnostics",
            "self_repair",
            "autonomous_self_repair",
        } or context.get("autonomous_diagnostics") is True:
            return True
        normalized = controller._normalize(command)
        return any(
            phrase in normalized
            for phrase in (
                "diagnostyka autonomii",
                "diagnostykę autonomii",
                "diagnostyke autonomii",
                "diagnostyka zadania",
                "diagnostykę zadania",
                "diagnostyke zadania",
                "wyjaśnij błąd zadania",
                "wyjasnij blad zadania",
                "wyjaśnij awarię",
                "wyjasnij awarie",
                "raport błędów autonomii",
                "raport bledow autonomii",
                "historia napraw autonomii",
                "bezpieczna naprawa zadania",
                "bezpieczną naprawę zadania",
                "bezpieczna naprawe zadania",
                "napraw zadanie longrun-",
                "spróbuj naprawić zadanie",
                "sprobuj naprawic zadanie",
                "autonomous diagnostics",
                "diagnose longrun-",
                "safe repair longrun-",
            )
        )

    @staticmethod
    def _action(
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> str:
        explicit = str(
            context.get("diagnostics_action", context.get("action", ""))
        ).strip().casefold()
        aliases = {
            "job": "job",
            "diagnose_job": "job",
            "run": "run",
            "diagnose_run": "run",
            "latest": "latest",
            "recent": "recent",
            "history": "recent",
            "repair": "repair",
            "self_repair": "repair",
            "repairs": "repairs",
            "repair_history": "repairs",
            "status": "status",
        }
        if explicit in aliases:
            return aliases[explicit]
        normalized = controller._normalize(command)
        if any(phrase in normalized for phrase in (
            "historia napraw", "pokaż naprawy", "pokaz naprawy", "repair history"
        )):
            return "repairs"
        if any(phrase in normalized for phrase in (
            "napraw zadanie", "bezpieczna naprawa", "bezpieczną naprawę",
            "sprobuj naprawic", "spróbuj naprawić", "safe repair"
        )):
            return "repair"
        if any(phrase in normalized for phrase in (
            "raport błędów", "raport bledow", "ostatnie diagnostyki",
            "historia diagnostyki", "diagnostics history"
        )):
            return "recent"
        if "autonomy-" in normalized and "longrun-" not in normalized:
            return "run"
        if "longrun-" in normalized:
            return "job"
        if any(phrase in normalized for phrase in (
            "status diagnostyki", "status diagnostyki autonomii"
        )):
            return "status"
        return "latest"

    @staticmethod
    def _job_id(command: str, context: dict[str, Any]) -> str:
        explicit = str(context.get("job_id", "")).strip()
        if explicit:
            return explicit
        match = re.search(r"\blongrun-[a-z0-9_-]+\b", str(command).casefold())
        return match.group(0) if match else ""

    @staticmethod
    def _run_id(command: str, context: dict[str, Any]) -> str:
        explicit = str(context.get("autonomy_run_id", context.get("run_id", ""))).strip()
        if explicit:
            return explicit
        match = re.search(r"\bautonomy-[a-z0-9_-]+\b", str(command).casefold())
        return match.group(0) if match else ""

    @staticmethod
    def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = minimum
        return min(maximum, max(minimum, parsed))
