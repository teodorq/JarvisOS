from __future__ import annotations

import re
from typing import Any

from .long_running_autonomy_service import (
    LongRunningAutonomyService,
)


class SoftwareEngineerLongRunningRouter:
    """Routes persistent scheduling and supervisor commands."""

    _JOB_ACTIONS = {
        "job_status",
        "pause_job",
        "resume_job",
        "cancel_job",
        "run_job",
        "delete_job",
    }

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self._is_long_running(
            controller,
            command=command,
            context=context,
        ):
            return None

        service = getattr(
            controller,
            "long_running_autonomy_service",
            None,
        )
        if service is None:
            service = LongRunningAutonomyService(
                controller.project_root
            )
            controller.long_running_autonomy_service = service

        action = self._action(
            controller,
            command=command,
            context=context,
        )
        job_id = self._job_id(command, context)

        if action in self._JOB_ACTIONS and not job_id:
            return {
                "success": False,
                "status": "LONG_RUNNING_JOB_ID_REQUIRED",
                "operation": "long_running_autonomy",
                "job_id": "",
                "job": {},
                "jobs": [],
                "errors": ["Podaj identyfikator longrun-..."],
            }

        if action == "status":
            return service.status()
        if action == "job_status":
            return service.status(job_id)
        if action == "recent":
            return service.recent(
                limit=self._bounded_int(
                    context.get("limit", 20), 1, 200
                )
            )
        if action == "tick":
            return service.tick()
        if action == "start":
            return service.start_background()
        if action == "stop":
            return service.stop_background()
        if action == "pause_supervisor":
            return service.pause_supervisor()
        if action == "resume_supervisor":
            return service.resume_supervisor()
        if action == "pause_job":
            return service.pause_job(job_id)
        if action == "resume_job":
            return service.resume_job(job_id)
        if action == "cancel_job":
            return service.cancel_job(job_id)
        if action == "run_job":
            return service.run_job_now(job_id)
        if action == "delete_job":
            return service.delete_job(job_id)
        if action == "clear_completed":
            return service.clear_terminal_jobs()
        if action == "recover":
            recovered = service.recover_interrupted()
            return {
                **service.status(),
                "status": "LONG_RUNNING_RECOVERY_COMPLETED",
                "recovered": len(recovered),
            }
        if action == "policy":
            return service.update_policy(
                self._policy_updates(command, context)
            )

        values = dict(context)
        if not isinstance(values.get("schedule"), dict):
            schedule = self._schedule_from_command(command)
            if schedule:
                values["schedule"] = schedule

        return service.enqueue(
            self._clean_objective(command, objective),
            context=values,
        )

    @staticmethod
    def _is_long_running(
        controller: Any,
        *,
        command: str,
        context: dict[str, Any],
    ) -> bool:
        operation = str(
            context.get(
                "operation",
                context.get("mode", ""),
            )
        ).strip().casefold()
        if operation in {
            "long_running_autonomy",
            "autonomy_supervisor",
            "scheduled_autonomy",
            "persistent_autonomy",
        } or context.get("long_running_autonomy") is True:
            return True

        normalized = controller._normalize(command)
        if re.search(r"\blongrun-[a-z0-9_-]+\b", normalized):
            return True

        return any(
            phrase in normalized
            for phrase in (
                "długotrwała autonomia",
                "długotrwałą autonomię",
                "długotrwałej autonomii",
                "długa autonomia",
                "długiej autonomii",
                "dlugotrwala autonomia",
                "dlugotrwala autonomie",
                "dlugotrwalej autonomii",
                "nadzorca autonomii",
                "nadzorcę autonomii",
                "nadzorce autonomii",
                "harmonogram autonomii",
                "kolejka autonomii",
                "kolejkę autonomii",
                "kolejke autonomii",
                "zadanie długotrwałe",
                "zadania długotrwałego",
                "zadanie dlugotrwale",
                "zadania dlugotrwalego",
                "pokaż wszystkie zadania",
                "pokaz wszystkie zadania",
                "lista zadań autonomii",
                "lista zadan autonomii",
                "usuń zakończone zadania",
                "usun zakonczone zadania",
                "wyczyść zakończone zadania",
                "wyczysc zakonczone zadania",
                "long running autonomy",
                "autonomy supervisor",
                "scheduled autonomy",
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
            context.get(
                "long_running_action",
                context.get("action", ""),
            )
        ).strip().casefold()
        aliases = {
            "enqueue": "enqueue",
            "schedule": "enqueue",
            "status": "status",
            "job_status": "job_status",
            "recent": "recent",
            "list": "recent",
            "queue": "recent",
            "history": "recent",
            "tick": "tick",
            "start": "start",
            "stop": "stop",
            "pause": "pause_supervisor",
            "resume": "resume_supervisor",
            "pause_job": "pause_job",
            "resume_job": "resume_job",
            "cancel": "cancel_job",
            "cancel_job": "cancel_job",
            "run_job": "run_job",
            "delete_job": "delete_job",
            "clear": "clear_completed",
            "clear_completed": "clear_completed",
            "purge_terminal": "clear_completed",
            "recover": "recover",
            "policy": "policy",
        }
        if explicit in aliases:
            return aliases[explicit]

        normalized = controller._normalize(command)
        phrases = (
            (
                "clear_completed",
                (
                    "usuń zakończone zadania",
                    "usun zakonczone zadania",
                    "wyczyść zakończone zadania",
                    "wyczysc zakonczone zadania",
                    "usuń ukończone zadania",
                    "usun ukonczone zadania",
                    "clear completed jobs",
                ),
            ),
            (
                "delete_job",
                (
                    "usuń zadanie",
                    "usun zadanie",
                    "delete job",
                ),
            ),
            (
                "job_status",
                (
                    "pokaż status zadania",
                    "pokaz status zadania",
                    "sprawdź status zadania",
                    "sprawdz status zadania",
                    "status zadania długotrwałego",
                    "status zadania dlugotrwalego",
                    "long job status",
                ),
            ),
            (
                "pause_job",
                (
                    "wstrzymaj zadanie długotrwałe",
                    "wstrzymaj zadanie dlugotrwale",
                    "wstrzymaj zadanie",
                    "pause long job",
                ),
            ),
            (
                "resume_job",
                (
                    "wznów zadanie długotrwałe",
                    "wznow zadanie dlugotrwale",
                    "wznów zadanie",
                    "wznow zadanie",
                    "resume long job",
                ),
            ),
            (
                "cancel_job",
                (
                    "anuluj zadanie długotrwałe",
                    "anuluj zadanie dlugotrwale",
                    "anuluj zadanie",
                    "cancel long job",
                ),
            ),
            (
                "run_job",
                (
                    "wykonaj teraz zadanie długotrwałe",
                    "wykonaj teraz zadanie dlugotrwale",
                    "wykonaj teraz zadanie",
                    "uruchom teraz zadanie",
                    "run long job now",
                ),
            ),
            (
                "recent",
                (
                    "pokaż kolejkę autonomii",
                    "pokaz kolejke autonomii",
                    "kolejka autonomii",
                    "kolejkę autonomii",
                    "pokaż wszystkie zadania",
                    "pokaz wszystkie zadania",
                    "lista zadań autonomii",
                    "lista zadan autonomii",
                    "historia długotrwałej autonomii",
                    "historia dlugotrwalej autonomii",
                    "long running queue",
                ),
            ),
            ("tick", ("wykonaj cykl nadzorcy", "supervisor tick")),
            (
                "start",
                (
                    "uruchom nadzorcę autonomii",
                    "uruchom nadzorce autonomii",
                    "start autonomy supervisor",
                ),
            ),
            (
                "stop",
                (
                    "zatrzymaj nadzorcę autonomii",
                    "zatrzymaj nadzorce autonomii",
                    "stop autonomy supervisor",
                ),
            ),
            (
                "pause_supervisor",
                (
                    "wstrzymaj nadzorcę autonomii",
                    "wstrzymaj nadzorce autonomii",
                ),
            ),
            (
                "resume_supervisor",
                (
                    "wznów nadzorcę autonomii",
                    "wznow nadzorce autonomii",
                ),
            ),
            (
                "recover",
                (
                    "odzyskaj przerwane zadania",
                    "recover autonomy jobs",
                ),
            ),
            (
                "policy",
                (
                    "ustaw limity długiej autonomii",
                    "ustaw limity dlugiej autonomii",
                ),
            ),
            (
                "status",
                (
                    "pokaż status długotrwałej autonomii",
                    "pokaz status dlugotrwalej autonomii",
                    "status długotrwałej autonomii",
                    "status dlugotrwalej autonomii",
                    "status nadzorcy autonomii",
                ),
            ),
        )
        for action, variants in phrases:
            if any(variant in normalized for variant in variants):
                return action
        return "enqueue"

    @staticmethod
    def _job_id(
        command: str,
        context: dict[str, Any],
    ) -> str:
        explicit = str(
            context.get(
                "job_id",
                context.get("long_running_job_id", ""),
            )
        ).strip()
        if explicit:
            return explicit
        match = re.search(
            r"\blongrun-[A-Za-z0-9_-]+\b",
            str(command),
            flags=re.IGNORECASE,
        )
        return match.group(0) if match else ""

    @staticmethod
    def _clean_objective(command: str, objective: str) -> str:
        value = " ".join(str(objective).strip().split())
        value = re.sub(
            r"^(?:zaplanuj|dodaj|utwórz|utworz)\s*:?\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        if not value:
            value = " ".join(str(command).strip().split())
        return value.strip(" :")

    @staticmethod
    def _schedule_from_command(command: str) -> dict[str, Any]:
        text = " ".join(str(command).casefold().split())
        if re.search(r"\bco\s+godzin(?:ę|e)\b", text):
            return {"type": "interval", "interval_minutes": 60}
        if re.search(r"\bco\s+minut(?:ę|e)\b", text):
            return {"type": "interval", "interval_minutes": 1}

        interval = re.search(
            r"\bco\s+(\d{1,4})\s*(minut(?:ę|y)?|min|godzin(?:ę|y)?|h)\b",
            text,
        )
        if interval:
            amount = max(1, int(interval.group(1)))
            unit = interval.group(2)
            minutes = (
                amount * 60
                if unit.startswith(("godzin", "h"))
                else amount
            )
            return {
                "type": "interval",
                "interval_minutes": min(minutes, 43200),
            }

        daily = re.search(
            r"\bcodziennie\s+o\s+([01]?\d|2[0-3]):([0-5]\d)\b",
            text,
        )
        if daily:
            return {
                "type": "daily",
                "hour": int(daily.group(1)),
                "minute": int(daily.group(2)),
            }
        return {}

    @staticmethod
    def _policy_updates(
        command: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        updates = dict(
            context.get("long_running_policy", {}) or {}
        )
        text = " ".join(str(command).casefold().split())
        patterns = (
            (
                "max_cpu_percent",
                r"\bcpu\s*(?:do|max|limit)?\s*[:=]?\s*(\d{1,3}(?:[.,]\d+)?)\s*%?",
            ),
            (
                "max_memory_percent",
                r"\b(?:ram|pamięć|pamiec)\s*(?:do|max|limit)?\s*[:=]?\s*(\d{1,3}(?:[.,]\d+)?)\s*%?",
            ),
            (
                "min_disk_free_gb",
                r"\b(?:dysk|wolne miejsce)\s*(?:min|minimum)?\s*[:=]?\s*(\d{1,4}(?:[.,]\d+)?)\s*gb",
            ),
            (
                "max_parallel_jobs",
                r"\b(?:równolegle|rownolegle|max zadań|max zadan)\s*[:=]?\s*(\d{1,2})\b",
            ),
            (
                "interval_seconds",
                r"\binterwał\s*[:=]?\s*(\d{1,5})\s*(?:s|sekund)",
            ),
        )
        for key, pattern in patterns:
            match = re.search(pattern, text)
            if match:
                updates[key] = float(
                    match.group(1).replace(",", ".")
                )
        updates["auto_approve"] = False
        return updates

    @staticmethod
    def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = minimum
        return min(maximum, max(minimum, parsed))
