from __future__ import annotations

from typing import Any

from app.ai.software_engineer.software_engineer_full_autonomy_formatter import (
    format_full_autonomy_response,
)
from app.ai.software_engineer.software_engineer_campaign_formatter import (
    format_change_campaign_response,
)
from app.ai.software_engineer.software_engineer_portfolio_formatter import (
    format_multi_campaign_response,
)
from app.ai.software_engineer.software_engineer_learning_formatter import (
    format_autonomous_learning_response,
)


class BrainResponseFormatter:
    """Formats Brain controller responses without owning orchestration state."""

    def _format_software_engineer_response(
        self,
        response: dict[str, Any],
    ) -> str:
        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )
        campaign = response.get(
            "campaign",
            {},
        )
        portfolio = response.get(
            "portfolio",
            {},
        )

        if response.get(
            "operation"
        ) == "autonomous_learning":
            return format_autonomous_learning_response(
                response
            )

        if response.get(
            "operation"
        ) == "full_autonomy":
            return format_full_autonomy_response(
                response
            )

        if (
            isinstance(
                portfolio,
                dict,
            )
            and portfolio
        ) or response.get(
            "operation"
        ) == "multi_campaign":
            return format_multi_campaign_response(
                response
            )

        if isinstance(
            campaign,
            dict,
        ) and campaign:
            return format_change_campaign_response(
                response
            )

        if not response.get(
            "success",
            False,
        ):
            errors = response.get(
                "errors",
                [],
            )
            error_text = "; ".join(
                str(item)
                for item in errors
            )
            result = (
                "Autonomous Software Engineer: "
                f"{status}"
            )

            if error_text:
                result += f" | {error_text}"

            return result

        cross_plan = response.get(
            "cross_module_plan",
            {},
        )

        if isinstance(
            cross_plan,
            dict,
        ) and cross_plan:
            subsystems = cross_plan.get(
                "subsystems",
                {},
            )
            files = (
                cross_plan.get(
                    "refactor_plan",
                    {},
                ).get(
                    "files",
                    [],
                )
                if isinstance(
                    cross_plan.get(
                        "refactor_plan",
                        {},
                    ),
                    dict,
                )
                else []
            )
            lines = [
                (
                    "Autonomous Software Engineer: "
                    f"{status}"
                ),
                (
                    "Zmiana między modułami: "
                    f"{len(files) if isinstance(files, list) else 0} plików"
                ),
                (
                    "Podsystemy: "
                    + ", ".join(
                        str(value)
                        for value in (
                            subsystems
                            if isinstance(
                                subsystems,
                                dict,
                            )
                            else []
                        )
                    )
                ),
                (
                    "Poziom ryzyka: "
                    f"{cross_plan.get('risk_level', 'UNKNOWN')}"
                ),
            ]
            module_order = cross_plan.get(
                "module_order",
                [],
            )

            if isinstance(module_order, list) and module_order:
                lines.append(
                    "Kolejność modułów: "
                    + " -> ".join(
                        str(item)
                        for item in module_order
                    )
                )

            run_id = str(
                response.get(
                    "run_id",
                    "",
                )
            ).strip()

            if run_id:
                lines.append(
                    f"Identyfikator przebiegu: {run_id}"
                )

            verification = response.get(
                "verification",
                {},
            )

            if isinstance(verification, dict) and verification:
                lines.append(
                    "Weryfikacja końcowa: "
                    f"{verification.get('status', 'UNKNOWN')}"
                )

            report_path = str(
                response.get(
                    "report_path",
                    "",
                )
            ).strip()

            if report_path:
                lines.append(
                    f"Raport przebiegów: {report_path}"
                )

            return "\n".join(lines)

        blueprint = response.get(
            "feature_blueprint",
            {},
        )

        if isinstance(
            blueprint,
            dict,
        ) and blueprint:
            files = blueprint.get(
                "files",
                [],
            )
            execution = response.get(
                "execution",
                {},
            )
            lines = [
                (
                    "Autonomous Software Engineer: "
                    f"{status}"
                ),
                (
                    "Funkcjonalność: "
                    f"{blueprint.get('feature_name', 'brak')}"
                ),
                (
                    "Pakiet: "
                    f"{blueprint.get('package_path', 'brak')}"
                ),
                (
                    "Pliki funkcjonalności: "
                    f"{len(files) if isinstance(files, list) else 0}"
                ),
            ]

            if isinstance(
                execution,
                dict,
            ) and execution:
                files_count = execution.get(
                    "files_count",
                    0,
                )
                lines.append(
                    "Pliki w transakcji: "
                    f"{int(files_count or 0)}"
                )

            run_id = str(
                response.get(
                    "run_id",
                    "",
                )
            ).strip()

            if run_id:
                lines.append(
                    f"Identyfikator przebiegu: {run_id}"
                )

            verification = response.get(
                "verification",
                {},
            )

            if isinstance(
                verification,
                dict,
            ) and verification:
                lines.append(
                    "Weryfikacja końcowa: "
                    f"{verification.get('status', 'UNKNOWN')}"
                )

            report_path = str(
                response.get(
                    "report_path",
                    "",
                )
            ).strip()

            if report_path:
                lines.append(
                    f"Raport przebiegów: {report_path}"
                )

            if status == "PREVIEW_READY":
                lines.append(
                    "Podgląd wieloplikowej transakcji "
                    "jest gotowy do akceptacji."
                )

            if status == "COMPLETED":
                lines.append(
                    "Wszystkie pliki zostały utworzone "
                    "i zweryfikowane jako jedna transakcja."
                )

            return "\n".join(
                lines
            )

        plan = response.get(
            "plan",
            {},
        )
        tasks = (
            plan.get(
                "tasks",
                [],
            )
            if isinstance(
                plan,
                dict,
            )
            else []
        )
        queue = response.get(
            "queue",
            {},
        )
        execution = response.get(
            "execution",
            {},
        )

        lines = [
            (
                "Autonomous Software Engineer: "
                f"{status}"
            ),
            (
                "Zadania planu: "
                f"{len(tasks)}"
            ),
        ]

        if isinstance(
            queue,
            dict,
        ):
            lines.append(
                "Nowe zadania AutoDev: "
                f"{int(queue.get('created', 0))}"
            )

        target_path = str(
            response.get(
                "target_path",
                "",
            )
        ).strip()

        if target_path:
            lines.append(
                f"Plik docelowy: {target_path}"
            )
        else:
            lines.append(
                "Plan gotowy. Aby wykonać zmianę "
                "bezpośrednio, podaj ścieżkę pliku .py."
            )

        if isinstance(
            execution,
            dict,
        ) and execution:
            lines.append(
                "Próby wykonania: "
                f"{int(execution.get('attempt_count', 0))}"
            )

        return "\n".join(
            lines
        )

    def _format_architect_response(
        self,
        response: dict[str, Any],
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(response)

        if not response.get(
            "success",
            False,
        ):
            status = str(
                response.get(
                    "status",
                    "FAILED",
                )
            )
            error = str(
                response.get(
                    "error",
                    "",
                )
            ).strip()

            result = (
                "Autonomous Architect: "
                f"{status}"
            )

            if error:
                result += f" | {error}"

            return result

        architecture_score = response.get(
            "architecture_score",
            "N/A",
        )
        smell_score = response.get(
            "smell_score",
            "N/A",
        )
        recommended_count = int(
            response.get(
                "recommended_count",
                0,
            )
        )

        queue_result = response.get(
            "autodev_queue",
            {},
        )
        queued = 0

        if isinstance(
            queue_result,
            dict,
        ):
            queued = int(
                queue_result.get(
                    "created",
                    0,
                )
            )

        lines = [
            "Autonomous Architect zakończył analizę.",
            f"Architecture Score: {architecture_score}",
            f"Architecture Smell Score: {smell_score}",
            (
                "Blueprinty refaktoryzacji: "
                f"{recommended_count}"
            ),
            f"Nowe zadania AutoDev: {queued}",
        ]

        blueprints = response.get(
            "blueprints",
            [],
        )

        if isinstance(
            blueprints,
            list,
        ):
            for index, blueprint in enumerate(
                blueprints[:5],
                start=1,
            ):
                if not isinstance(
                    blueprint,
                    dict,
                ):
                    continue

                title = str(
                    blueprint.get(
                        "title",
                        "Refaktoryzacja",
                    )
                )
                score = blueprint.get(
                    "architect_score",
                    "N/A",
                )
                lines.append(
                    f"{index}. {title} "
                    f"(score: {score})"
                )

        return "\n".join(lines)

    def _format_autonomous_dev_response(
        self,
        response: dict[str, Any],
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        ).upper()

        success = bool(
            response.get(
                "success",
                status not in {
                    "FAILED",
                    "GENERATION_FAILED",
                    "EXECUTION_FAILED",
                },
            )
        )

        if status == "STATUS":
            controller = getattr(
                self,
                "autonomous_dev_controller",
                None,
            )

            controller_status = {}

            if controller is not None:
                status_method = getattr(
                    controller,
                    "status",
                    None,
                )

                if callable(status_method):
                    try:
                        controller_status = (
                            status_method() or {}
                        )
                    except Exception as error:
                        controller_status = {
                            "status_error": (
                                f"{type(error).__name__}: "
                                f"{error}"
                            )
                        }

            return self._format_autonomous_status(
                controller_status=controller_status,
                fallback_response=response,
            )

        task_id = str(
            response.get(
                "task_id",
                response.get(
                    "autodev_task_id",
                    "",
                ),
            )
        ).strip()

        lines = [
            (
                "Autonomous AutoDev "
                "obsłużył polecenie."
                if success
                else (
                    "Autonomous AutoDev nie zakończył "
                    "operacji poprawnie."
                )
            ),
            f"Status: {status}",
        ]

        duration_seconds = self._safe_int(
            response.get(
                "duration_seconds",
                0,
            )
        )

        if status == "TIMED_LOOP_STARTED":
            if duration_seconds > 0:
                lines.append(
                    "Zaplanowany czas pracy: "
                    + self._format_duration(
                        duration_seconds
                    )
                )

            lines.append(
                "Pętla autonomicznego rozwoju "
                "działa w tle."
            )

        elif status == "ALREADY_RUNNING":
            lines.append(
                "Pętla autonomicznego rozwoju "
                "już działa."
            )

        elif status == "STOP_REQUESTED":
            lines.append(
                "Wysłano żądanie zatrzymania "
                "pętli autonomicznej."
            )

        elif status == "NOT_RUNNING":
            lines.append(
                "Pętla autonomiczna nie jest uruchomiona."
            )

        if task_id:
            lines.append(
                f"Task ID: {task_id}"
            )

        message = response.get(
            "message"
        )

        if message:
            lines.append(
                f"Wynik: {message}"
            )

        if status in {
            "QUEUED",
            "PENDING",
            "READY",
        }:
            lines.append(
                "Zadanie zostało dodane "
                "do autonomicznej kolejki."
            )

        if status == "WAITING_FOR_APPROVAL":
            lines.append(
                "Zmiany są przygotowane "
                "i czekają na akceptację."
            )

        if status == "WAITING_FOR_CODE_INPUT":
            lines.append(
                "Pętla czeka na kompletne dane kodu "
                "potrzebne do przygotowania zmiany."
            )

        if status in {
            "COMPLETED",
            "TIME_LIMIT_REACHED",
            "MAX_CYCLES_REACHED",
        }:
            lines.append(
                "Cykl autonomicznego rozwoju "
                "został zakończony."
            )

        if status in {
            "ROLLED_BACK",
            "FAILED_AND_ROLLED_BACK",
        }:
            lines.append(
                "Wykryto błąd i bezpiecznie "
                "cofnięto zmiany."
            )

        completed_cycles = self._safe_int(
            response.get(
                "completed_cycles",
                0,
            )
        )

        if completed_cycles:
            lines.append(
                f"Wykonane cykle: {completed_cycles}"
            )

        changed_files = response.get(
            "changed_files",
            [],
        )

        if isinstance(
            changed_files,
            list,
        ) and changed_files:
            lines.append(
                "Zmienione pliki: "
                + ", ".join(
                    str(path)
                    for path in changed_files
                )
            )

        blocking_reason = response.get(
            "blocking_reason"
        )

        if blocking_reason:
            lines.append(
                f"Blokada: {blocking_reason}"
            )

        error = response.get(
            "error"
        )

        if error:
            lines.append(
                f"Błąd: {error}"
            )

        errors = response.get(
            "errors",
            [],
        )

        if isinstance(
            errors,
            list,
        ) and errors:
            lines.append(
                "Błędy: "
                + "; ".join(
                    str(item)
                    for item in errors
                )
            )

        return "\n".join(
            lines
        )

    def _format_autonomous_status(
        self,
        *,
        controller_status: dict[str, Any],
        fallback_response: dict[str, Any],
    ) -> str:

        timed_running = bool(
            controller_status.get(
                "timed_loop_running",
                False,
            )
        )

        timed_loop = controller_status.get(
            "last_timed_loop",
            {},
        )

        if not isinstance(
            timed_loop,
            dict,
        ):
            timed_loop = {}

        autonomous_loop = controller_status.get(
            "last_autonomous_loop",
            {},
        )

        if not isinstance(
            autonomous_loop,
            dict,
        ):
            autonomous_loop = {}

        pipeline = controller_status.get(
            "pipeline",
            fallback_response.get(
                "pipeline",
                {},
            ),
        )

        if not isinstance(
            pipeline,
            dict,
        ):
            pipeline = {}

        backlog = controller_status.get(
            "backlog",
            fallback_response.get(
                "backlog",
                {},
            ),
        )

        if not isinstance(
            backlog,
            dict,
        ):
            backlog = {}

        if timed_running:
            display_status = "RUNNING"
        else:
            display_status = str(
                timed_loop.get(
                    "status",
                    pipeline.get(
                        "state",
                        "STOPPED",
                    ),
                )
            ).upper()

        lines = [
            "Autonomous AutoDev — status",
            f"Status: {display_status}",
        ]

        duration_seconds = self._safe_int(
            timed_loop.get(
                "duration_seconds",
                0,
            )
        )

        started_at = timed_loop.get(
            "started_at"
        )

        if timed_running and duration_seconds > 0:
            elapsed_seconds = 0

            try:
                elapsed_seconds = max(
                    0,
                    int(
                        time.time()
                        - float(started_at)
                    ),
                )
            except (TypeError, ValueError):
                elapsed_seconds = 0

            remaining_seconds = max(
                0,
                duration_seconds - elapsed_seconds,
            )

            lines.append(
                "Czas działania: "
                + self._format_duration(
                    elapsed_seconds
                )
            )
            lines.append(
                "Pozostały czas: "
                + self._format_duration(
                    remaining_seconds
                )
            )

        elif duration_seconds > 0:
            elapsed_seconds = self._safe_int(
                timed_loop.get(
                    "elapsed_seconds",
                    0,
                )
            )

            lines.append(
                "Zaplanowany czas: "
                + self._format_duration(
                    duration_seconds
                )
            )

            if elapsed_seconds:
                lines.append(
                    "Rzeczywisty czas: "
                    + self._format_duration(
                        elapsed_seconds
                    )
                )

        completed_cycles = max(
            self._safe_int(
                timed_loop.get(
                    "completed_cycles",
                    0,
                )
            ),
            self._safe_int(
                autonomous_loop.get(
                    "completed_cycles",
                    0,
                )
            ),
        )

        attempted_cycles = max(
            self._safe_int(
                timed_loop.get(
                    "attempted_cycles",
                    0,
                )
            ),
            self._safe_int(
                autonomous_loop.get(
                    "cycles_attempted",
                    0,
                )
            ),
        )

        lines.append(
            f"Wykonane cykle: {completed_cycles}"
        )
        lines.append(
            f"Próby cykli: {attempted_cycles}"
        )

        pipeline_state = str(
            pipeline.get(
                "state",
                pipeline.get(
                    "status",
                    "UNKNOWN",
                ),
            )
        ).upper()

        lines.append(
            f"Pipeline: {pipeline_state}"
        )

        backlog_total = self._safe_int(
            backlog.get(
                "total",
                0,
            )
        )

        lines.append(
            f"Backlog: {backlog_total} zadań"
        )

        last_result = timed_loop.get(
            "last_result"
        )

        if not isinstance(
            last_result,
            dict,
        ):
            last_result = autonomous_loop

        if isinstance(
            last_result,
            dict,
        ) and last_result:
            last_status = str(
                last_result.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper()

            lines.append(
                f"Ostatni wynik: {last_status}"
            )

            blocking_reason = last_result.get(
                "blocking_reason"
            )

            if blocking_reason:
                lines.append(
                    f"Blokada: {blocking_reason}"
                )

            error = last_result.get(
                "error"
            )

            if error:
                lines.append(
                    f"Błąd: {error}"
                )

        status_error = controller_status.get(
            "status_error"
        )

        if status_error:
            lines.append(
                f"Błąd statusu: {status_error}"
            )

        return "\n".join(lines)

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:

        try:
            return int(
                float(value or 0)
            )
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _format_duration(
        total_seconds: int,
    ) -> str:

        normalized = max(
            0,
            int(total_seconds),
        )

        hours, remainder = divmod(
            normalized,
            3600,
        )
        minutes, seconds = divmod(
            remainder,
            60,
        )

        if hours:
            return (
                f"{hours:02d}:"
                f"{minutes:02d}:"
                f"{seconds:02d}"
            )

        return (
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    def _format_meta_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        meta_id = str(
            response.get(
                "meta_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Meta Executive "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if meta_id:
                lines.append(
                    f"Meta ID: {meta_id}"
                )

            selected_strategy = response.get(
                "selected_strategy"
            )

            if selected_strategy:
                lines.append(
                    "Strategia: "
                    f"{selected_strategy}"
                )

            selected_layer = response.get(
                "selected_layer"
            )

            if selected_layer:
                lines.append(
                    "Wybrana warstwa: "
                    f"{selected_layer}"
                )

            cycle = response.get(
                "cycle"
            )

            if cycle is not None:
                lines.append(
                    f"Cykl: {cycle}"
                )

            if response.get(
                "requires_approval",
                False,
            ):
                lines.append(
                    "Proces wymaga akceptacji "
                    "przed wykonaniem."
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Meta Executive czeka "
                    "na akceptację."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces nadrzędnego zarządzania "
                    "został zakończony poprawnie."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                current_stage = summary.get(
                    "current_stage"
                )

                priority = summary.get(
                    "priority"
                )

                risk_level = summary.get(
                    "risk_level"
                )

                if current_stage:
                    lines.append(
                        f"Etap: {current_stage}"
                    )

                if priority:
                    lines.append(
                        f"Priorytet: {priority}"
                    )

                if risk_level:
                    lines.append(
                        f"Ryzyko: {risk_level}"
                    )

            sessions = response.get(
                "sessions"
            )

            if isinstance(
                sessions,
                list,
            ):
                lines.append(
                    "Liczba sesji: "
                    f"{len(sessions)}"
                )

            memory_summary = response.get(
                "memory_summary"
            )

            if isinstance(
                memory_summary,
                dict,
            ):
                total_records = memory_summary.get(
                    "total_records"
                )

                if total_records is not None:
                    lines.append(
                        "Rekordy pamięci: "
                        f"{total_records}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Meta Executive zakończył "
                    "operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Meta Executive nie zakończył "
                "operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if meta_id:
            lines.append(
                f"Meta ID: {meta_id}"
            )

        return "\n".join(
            lines
        )

    def _format_executive_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        executive_id = str(
            response.get(
                "executive_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Executive AI "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if executive_id:
                lines.append(
                    f"Executive ID: {executive_id}"
                )

            selected_strategy = response.get(
                "selected_strategy"
            )

            if selected_strategy:
                lines.append(
                    "Strategia: "
                    f"{selected_strategy}"
                )

            delegated_module = response.get(
                "delegated_module"
            )

            if delegated_module:
                lines.append(
                    "Delegowany moduł: "
                    f"{delegated_module}"
                )

            phase = response.get(
                "phase"
            )

            if phase is not None:
                lines.append(
                    f"Faza: {phase}"
                )

            if response.get(
                "requires_approval",
                False,
            ):
                lines.append(
                    "Proces wymaga akceptacji "
                    "przed wykonaniem."
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Executive AI czeka "
                    "na akceptację."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces strategiczny został "
                    "zakończony poprawnie."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                current_phase = summary.get(
                    "current_phase"
                )

                priority = summary.get(
                    "priority"
                )

                risk_level = summary.get(
                    "risk_level"
                )

                if current_phase:
                    lines.append(
                        f"Etap: {current_phase}"
                    )

                if priority:
                    lines.append(
                        f"Priorytet: {priority}"
                    )

                if risk_level:
                    lines.append(
                        f"Ryzyko: {risk_level}"
                    )

            sessions = response.get(
                "sessions"
            )

            if isinstance(
                sessions,
                list,
            ):
                lines.append(
                    "Liczba sesji: "
                    f"{len(sessions)}"
                )

            memory_summary = response.get(
                "memory_summary"
            )

            if isinstance(
                memory_summary,
                dict,
            ):
                total_records = memory_summary.get(
                    "total_records"
                )

                if total_records is not None:
                    lines.append(
                        "Rekordy pamięci: "
                        f"{total_records}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Executive AI zakończył "
                    "operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Executive AI nie zakończył "
                "operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if executive_id:
            lines.append(
                f"Executive ID: {executive_id}"
            )

        return "\n".join(
            lines
        )

    def _format_project_director_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        director_id = str(
            response.get(
                "director_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Autonomous Project Director "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if director_id:
                lines.append(
                    f"Director ID: {director_id}"
                )

            selected_module = response.get(
                "selected_module"
            )

            if selected_module:
                lines.append(
                    "Wybrany moduł: "
                    f"{selected_module}"
                )

            iteration = response.get(
                "iteration"
            )

            if iteration is not None:
                lines.append(
                    f"Iteracja: {iteration}"
                )

            if response.get(
                "requires_approval",
                False,
            ):
                lines.append(
                    "Proces wymaga akceptacji "
                    "przed wykonaniem."
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Project Director czeka "
                    "na akceptację."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces zarządzania projektem "
                    "został zakończony poprawnie."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                current_stage = summary.get(
                    "current_stage"
                )

                priority = summary.get(
                    "priority"
                )

                risk_level = summary.get(
                    "risk_level"
                )

                if current_stage:
                    lines.append(
                        f"Etap: {current_stage}"
                    )

                if priority:
                    lines.append(
                        f"Priorytet: {priority}"
                    )

                if risk_level:
                    lines.append(
                        f"Ryzyko: {risk_level}"
                    )

            sessions = response.get(
                "sessions"
            )

            if isinstance(
                sessions,
                list,
            ):
                lines.append(
                    "Liczba sesji: "
                    f"{len(sessions)}"
                )

            memory_summary = response.get(
                "memory_summary"
            )

            if isinstance(
                memory_summary,
                dict,
            ):
                total_records = memory_summary.get(
                    "total_records"
                )

                if total_records is not None:
                    lines.append(
                        "Rekordy pamięci: "
                        f"{total_records}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Autonomous Project Director "
                    "zakończył operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Autonomous Project Director nie "
                "zakończył operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if director_id:
            lines.append(
                f"Director ID: {director_id}"
            )

        return "\n".join(
            lines
        )

    def _format_improvement_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        session_id = str(
            response.get(
                "session_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Self Improvement Brain "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if session_id:
                lines.append(
                    f"Session ID: {session_id}"
                )

            decision = response.get(
                "decision"
            )

            if decision:
                lines.append(
                    f"Decyzja: {decision}"
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Sesja czeka na akceptację "
                    "przed wykonaniem zmian."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces samodoskonalenia został "
                    "zakończony poprawnie."
                )

            if status == "NO_ACTION":
                lines.append(
                    "Nie wykryto działania, które "
                    "należy teraz wykonać."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                sessions = summary.get(
                    "sessions"
                )

                memory = summary.get(
                    "memory"
                )

                if isinstance(
                    sessions,
                    list,
                ):
                    lines.append(
                        "Liczba sesji: "
                        f"{len(sessions)}"
                    )

                if isinstance(
                    memory,
                    dict,
                ):
                    total_records = memory.get(
                        "total_records",
                        memory.get(
                            "count"
                        ),
                    )

                    if total_records is not None:
                        lines.append(
                            "Rekordy pamięci: "
                            f"{total_records}"
                        )

            error = response.get(
                "error"
            )

            if error:
                lines.append(
                    f"Informacja: {error}"
                )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Self Improvement Brain "
                    "zakończył operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Self Improvement Brain nie "
                "zakończył operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if session_id:
            lines.append(
                f"Session ID: {session_id}"
            )

        return "\n".join(
            lines
        )

    def _format_evolution_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        evolution_id = str(
            response.get(
                "evolution_id",
                "",
            )
        ).strip()

        if success:
            lines = [
                (
                    "Auto Evolution Engine "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if evolution_id:
                lines.append(
                    f"Evolution ID: {evolution_id}"
                )

            iteration = response.get(
                "iteration"
            )

            if iteration is not None:
                lines.append(
                    f"Iteracja: {iteration}"
                )

            decision = response.get(
                "decision"
            )

            if decision:
                lines.append(
                    f"Decyzja: {decision}"
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Proces ewolucji czeka na "
                    "akceptację zmian."
                )

            if status == "COMPLETED":
                lines.append(
                    "Proces ewolucji został "
                    "zakończony poprawnie."
                )

            if status == "NO_CHANGES":
                lines.append(
                    "Nie wykryto zmian wymagających "
                    "wykonania."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                runs = summary.get(
                    "runs"
                )

                if isinstance(
                    runs,
                    list,
                ):
                    lines.append(
                        "Liczba procesów ewolucji: "
                        f"{len(runs)}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Auto Evolution Engine "
                    "zakończył operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Auto Evolution Engine nie "
                "zakończył operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if evolution_id:
            lines.append(
                f"Evolution ID: {evolution_id}"
            )

        return "\n".join(
            lines
        )

    def _format_continuous_dev_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        success = response.get(
            "success",
            False,
        )

        status = str(
            response.get(
                "status",
                "UNKNOWN",
            )
        )

        cycle_id = str(
            response.get(
                "cycle_id",
                "",
            )
        )

        if success:
            lines = [
                (
                    "Continuous Developer "
                    "obsłużył polecenie."
                ),
                f"Status: {status}",
            ]

            if cycle_id:
                lines.append(
                    f"Cycle ID: {cycle_id}"
                )

            if status == "WAITING_FOR_APPROVAL":
                lines.append(
                    "Cykl czeka na akceptację "
                    "przed wykonaniem zmian."
                )

            if status == "COMPLETED":
                lines.append(
                    "Cykl rozwoju został "
                    "zakończony poprawnie."
                )

            if status == "NO_CHANGES":
                lines.append(
                    "Nie wykryto zmian wymagających "
                    "wykonania."
                )

            summary = response.get(
                "summary"
            )

            if isinstance(
                summary,
                dict,
            ):
                current_stage = summary.get(
                    "current_stage"
                )

                iteration = summary.get(
                    "iteration"
                )

                if current_stage:
                    lines.append(
                        f"Etap: {current_stage}"
                    )

                if iteration is not None:
                    lines.append(
                        f"Iteracja: {iteration}"
                    )

            return "\n".join(
                lines
            )

        error = response.get(
            "error",
            response.get(
                "message",
                (
                    "Continuous Developer "
                    "zakończył operację błędem."
                ),
            ),
        )

        lines = [
            (
                "Continuous Developer nie zakończył "
                "operacji poprawnie."
            ),
            f"Status: {status}",
            f"Błąd: {error}",
        ]

        if cycle_id:
            lines.append(
                f"Cycle ID: {cycle_id}"
            )

        return "\n".join(
            lines
        )

    def _format_reasoning_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(response)

        if not response.get(
            "handled",
            False,
        ):
            return (
                "AI Reasoner nie rozpoznał "
                "tego polecenia."
            )

        if response.get(
            "success",
            False,
        ) is False:
            error = response.get(
                "error",
                "",
            )

            result = response.get(
                "result",
                {},
            )

            if (
                not error
                and isinstance(
                    result,
                    dict,
                )
            ):
                error = result.get(
                    "error",
                    "",
                )

            if error:
                return (
                    "AI Reasoner zakończył proces "
                    f"błędem: {error}"
                )

        result = response.get(
            "result",
            {},
        )

        if not isinstance(
            result,
            dict,
        ):
            return str(result)

        session_id = result.get(
            "session_id",
            "",
        )

        strategy = result.get(
            "strategy",
            {},
        )

        if not isinstance(
            strategy,
            dict,
        ):
            strategy = {}

        selected_option = strategy.get(
            "selected_option",
            {},
        )

        if not isinstance(
            selected_option,
            dict,
        ):
            selected_option = {}

        risk_assessment = strategy.get(
            "risk_assessment",
            {},
        )

        if not isinstance(
            risk_assessment,
            dict,
        ):
            risk_assessment = {}

        strategy_name = strategy.get(
            "name",
            selected_option.get(
                "name",
                "Brak strategii",
            ),
        )

        risk_level = risk_assessment.get(
            "risk_level",
            result.get(
                "risk_result",
                {},
            ).get(
                "overall_risk_level",
                "UNKNOWN",
            )
            if isinstance(
                result.get(
                    "risk_result",
                    {},
                ),
                dict,
            )
            else "UNKNOWN",
        )

        status = result.get(
            "status",
            response.get(
                "status",
                "UNKNOWN",
            ),
        )

        requires_confirmation = result.get(
            "requires_confirmation",
            strategy.get(
                "requires_confirmation",
                False,
            ),
        )

        blocking_reasons = result.get(
            "blocking_reasons",
            strategy.get(
                "blocking_reasons",
                [],
            ),
        )

        lines = [
            "AI Reasoner zakończył analizę.",
            f"Status: {status}",
            f"Strategia: {strategy_name}",
            f"Poziom ryzyka: {risk_level}",
        ]

        if session_id:
            lines.append(
                f"Session ID: {session_id}"
            )

        if requires_confirmation:
            lines.append(
                "Wymagana jest akceptacja "
                "przed wykonaniem zmian."
            )

        if isinstance(
            blocking_reasons,
            list,
        ) and blocking_reasons:
            lines.append(
                "Blokady: "
                + "; ".join(
                    str(reason)
                    for reason in blocking_reasons
                )
            )

        return "\n".join(lines)

    def _format_research_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        report = response.get(
            "report",
            "",
        )

        if report:
            return str(
                report
            )

        success = response.get(
            "success",
            False,
        )

        if success:
            return (
                "Research Agent zakończył "
                "analizę projektu."
            )

        error = response.get(
            "error",
            "",
        )

        if error:
            return (
                "Research Agent nie zakończył "
                f"analizy: {error}"
            )

        return (
            "Research Agent nie zwrócił raportu."
        )
