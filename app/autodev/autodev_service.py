from pathlib import Path
from typing import Optional

from app.autodev.autodev_brain import (
    AutoDevBrain
)
from app.autodev.autodev_report import (
    AutoDevReport
)
from app.autodev.autodev_request import (
    AutoDevRequest
)
from app.autodev.autodev_response import (
    AutoDevResponse
)
from app.autodev.developer_controller import (
    DeveloperController
)


class AutoDevService:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI"
    ):

        self.project_root = Path(
            project_root
        )

        self.brain = AutoDevBrain(
            project_root=str(
                self.project_root
            )
        )

        self.controller = DeveloperController(
            project_root=str(
                self.project_root
            )
        )

        self.last_context = None

        self.last_request: Optional[
            AutoDevRequest
        ] = None

        self.last_response: Optional[
            AutoDevResponse
        ] = None

    def handle(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        self.last_request = request

        valid, errors = request.validate()

        if not valid:
            return self._remember(
                AutoDevResponse(
                    success=False,
                    operation=request.operation,
                    message=(
                        "Polecenie AutoDev "
                        "jest niepoprawne."
                    ),
                    errors=errors
                )
            )

        handlers = {
            "analyze": self._analyze,
            "search": self._search,
            "report": self._report,
            "status": self._status,
            "preview": self._preview,
            "approve": self._approve,
            "reject": self._reject,
            "execute": self._execute,
            "approve_and_execute": (
                self._approve_and_execute
            ),
            "rollback": self._rollback,
            "reset": self._reset
        }

        handler = handlers.get(
            request.operation
        )

        if handler is None:
            return self._remember(
                AutoDevResponse(
                    success=False,
                    operation=request.operation,
                    message=(
                        "Nie znaleziono obsługi "
                        "operacji AutoDev."
                    ),
                    errors=[
                        request.operation
                    ]
                )
            )

        try:
            response = handler(
                request
            )

        except Exception as error:
            response = AutoDevResponse(
                success=False,
                operation=request.operation,
                message=(
                    "Wystąpił błąd podczas "
                    "pracy AutoDev."
                ),
                errors=[
                    str(error)
                ]
            )

        return self._remember(
            response
        )

    def _analyze(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        context = self.brain.analyze(
            request.query
        )

        self.last_context = context

        report = AutoDevReport(
            context=context
        ).build()

        search_results = []

        for result in context.search_results[:20]:
            search_results.append({
                "path": result.path,
                "score": result.score,
                "category": result.category,
                "matched_fields": (
                    result.matched_fields
                )
            })

        graph_count = 0

        if context.knowledge_graph is not None:
            graph_count = (
                context.knowledge_graph.count()
            )

        project_files_count = 0

        if context.project_index is not None:
            project_files_count = (
                context.project_index.count()
            )

        return AutoDevResponse(
            success=True,
            operation="analyze",
            message=(
                "AutoDev zakończył analizę "
                "projektu."
            ),
            report=report,
            data={
                "goal": request.query,
                "project_files_count": (
                    project_files_count
                ),
                "graph_nodes_count": (
                    graph_count
                ),
                "search_results_count": len(
                    context.search_results
                ),
                "search_results": search_results,
                "patch_prepared": False,
                "approval_required": False
            }
        )

    def _search(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        context = self.brain.analyze(
            request.query
        )

        self.last_context = context

        results = []

        lines = [
            "AUTODEV CODE SEARCH",
            f"Zapytanie: {request.query}",
            ""
        ]

        for result in context.search_results[:20]:
            results.append({
                "path": result.path,
                "score": result.score,
                "category": result.category,
                "matched_fields": (
                    result.matched_fields
                )
            })

            lines.append(
                f"{result.score:>5.1f} | "
                f"{result.path}"
            )

        if not results:
            lines.append(
                "Nie znaleziono wyników."
            )

        return AutoDevResponse(
            success=True,
            operation="search",
            message=(
                "Wyszukiwanie kodu "
                "zostało zakończone."
            ),
            report="\n".join(lines),
            data={
                "query": request.query,
                "results_count": len(results),
                "results": results
            }
        )

    def _report(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        sections = []

        if self.last_context is not None:
            sections.append(
                AutoDevReport(
                    context=self.last_context
                ).build()
            )

        controller_report = (
            self.controller.report()
        )

        sections.append(
            controller_report
        )

        if not sections:
            return AutoDevResponse(
                success=False,
                operation="report",
                message=(
                    "Brak raportu AutoDev."
                ),
                errors=[
                    "Nie wykonano jeszcze analizy."
                ]
            )

        return AutoDevResponse(
            success=True,
            operation="report",
            message=(
                "Wygenerowano raport AutoDev."
            ),
            report=(
                "\n\n"
                + "\n\n".join(sections)
            )
        )

    def _status(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        status = self.controller.status()

        has_analysis = (
            self.last_context is not None
        )

        lines = [
            "AUTODEV STATUS",
            (
                "Analiza projektu: TAK"
                if has_analysis
                else "Analiza projektu: NIE"
            ),
            (
                "Aktywna transakcja: TAK"
                if status["has_transaction"]
                else "Aktywna transakcja: NIE"
            ),
            (
                "Zatwierdzona: TAK"
                if status["approved"]
                else "Zatwierdzona: NIE"
            ),
            (
                "Można wykonać: TAK"
                if status["can_execute"]
                else "Można wykonać: NIE"
            ),
            (
                "Status sesji: "
                f"{status['session_status']}"
            ),
            (
                "Status transakcji: "
                f"{status['transaction_status'] or 'brak'}"
            )
        ]

        return AutoDevResponse(
            success=True,
            operation="status",
            message=(
                "Pobrano status AutoDev."
            ),
            report="\n".join(lines),
            data={
                "has_analysis": has_analysis,
                **status
            }
        )

    def _preview(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        transaction = (
            self.controller.session.transaction
        )

        if transaction is None:
            return AutoDevResponse(
                success=False,
                operation="preview",
                message=(
                    "Brak patcha do pokazania."
                ),
                errors=[
                    "Nie przygotowano transakcji zmian."
                ]
            )

        preview = (
            self.controller.current_preview()
        )

        return AutoDevResponse(
            success=True,
            operation="preview",
            message=(
                "Wygenerowano podgląd patcha."
            ),
            report=preview
        )

    def _approve(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        result = self.controller.approve()

        return AutoDevResponse(
            success=result.success,
            operation="approve",
            message=result.message,
            report=result.summary(),
            data=result.as_dict(),
            errors=result.errors
        )

    def _reject(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        result = self.controller.reject(
            reason=request.reason
        )

        return AutoDevResponse(
            success=result.success,
            operation="reject",
            message=result.message,
            report=result.summary(),
            data=result.as_dict(),
            errors=result.errors
        )

    def _execute(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        result = self.controller.execute(
            auto_rollback=True
        )

        return AutoDevResponse(
            success=result.success,
            operation="execute",
            message=result.message,
            report=result.summary(),
            data=result.as_dict(),
            errors=result.errors
        )

    def _approve_and_execute(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        result = (
            self.controller
            .approve_and_execute(
                auto_rollback=True
            )
        )

        return AutoDevResponse(
            success=result.success,
            operation=(
                "approve_and_execute"
            ),
            message=result.message,
            report=result.summary(),
            data=result.as_dict(),
            errors=result.errors
        )

    def _rollback(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        result = (
            self.controller.rollback_last()
        )

        return AutoDevResponse(
            success=result.success,
            operation="rollback",
            message=result.message,
            report=result.summary(),
            data=result.as_dict(),
            errors=result.errors
        )

    def _reset(
        self,
        request: AutoDevRequest
    ) -> AutoDevResponse:

        self.controller.reset()
        self.last_context = None

        return AutoDevResponse(
            success=True,
            operation="reset",
            message=(
                "Sesja AutoDev została "
                "wyczyszczona."
            ),
            report=(
                "AutoDev został zresetowany."
            )
        )

    def _remember(
        self,
        response: AutoDevResponse
    ) -> AutoDevResponse:

        self.last_response = response
        return response