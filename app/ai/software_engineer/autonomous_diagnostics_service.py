from __future__ import annotations

from pathlib import Path
import traceback
from typing import Any

from .autonomous_diagnostics_analyzer import AutonomousDiagnosticsAnalyzer
from .autonomous_diagnostics_collector import AutonomousDiagnosticsCollector
from .autonomous_diagnostics_store import AutonomousDiagnosticsStore
from .autonomous_self_repair import AutonomousSelfRepair
from .long_running_autonomy_store import LongRunningAutonomyStore


class AutonomousDiagnosticsService:
    """Persistent diagnostics, explanations and bounded self-repair."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomousDiagnosticsStore | None = None,
        long_running_store: LongRunningAutonomyStore | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store or AutonomousDiagnosticsStore(self.project_root)
        self.long_running_store = long_running_store or LongRunningAutonomyStore(
            self.project_root
        )
        self.collector = AutonomousDiagnosticsCollector(
            self.project_root,
            long_running_store=self.long_running_store,
        )
        self.analyzer = AutonomousDiagnosticsAnalyzer()
        self.repair_engine = AutonomousSelfRepair(
            self.project_root,
            long_running_store=self.long_running_store,
            diagnostics_store=self.store,
        )

    def diagnose_job(
        self,
        job_id: str,
        *,
        response: dict[str, Any] | None = None,
        exception: BaseException | None = None,
        traceback_text: str = "",
    ) -> dict[str, Any]:
        if exception is not None and not traceback_text:
            traceback_text = "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )
        snapshot = self.collector.collect_job(
            job_id,
            response=response,
            exception=exception,
            traceback_text=traceback_text,
        )
        evidence = self.collector.evidence(snapshot)
        diagnostic = self.analyzer.analyze(snapshot, evidence)
        saved = self.store.save_diagnostic(diagnostic)
        return self._response(
            "AUTONOMOUS_DIAGNOSTIC_READY",
            diagnostic=saved,
            success=True,
        )

    def diagnose_run(self, run_id: str) -> dict[str, Any]:
        snapshot = self.collector.collect_run(run_id)
        evidence = self.collector.evidence(snapshot)
        diagnostic = self.analyzer.analyze(snapshot, evidence)
        saved = self.store.save_diagnostic(diagnostic)
        return self._response(
            "AUTONOMOUS_DIAGNOSTIC_READY",
            diagnostic=saved,
            success=True,
        )

    def record_job_result(
        self,
        job: dict[str, Any],
        response: dict[str, Any],
        *,
        exception: BaseException | None = None,
        traceback_text: str = "",
    ) -> dict[str, Any]:
        job_id = str(job.get("job_id", "")).strip()
        if not job_id:
            return self._response(
                "AUTONOMOUS_DIAGNOSTIC_JOB_ID_REQUIRED",
                success=False,
                errors=["Brak job_id dla automatycznej diagnostyki."],
            )
        return self.diagnose_job(
            job_id,
            response=response,
            exception=exception,
            traceback_text=traceback_text,
        )

    def latest(self, *, job_id: str = "", run_id: str = "") -> dict[str, Any]:
        diagnostic = None
        if job_id:
            diagnostic = self.store.latest_for_job(job_id)
        elif run_id:
            diagnostic = self.store.latest_for_run(run_id)
        else:
            recent = self.store.list_recent(limit=1)
            diagnostic = recent[0] if recent else None
        if diagnostic is None:
            return self._response(
                "AUTONOMOUS_DIAGNOSTIC_NOT_FOUND",
                success=False,
                errors=["Nie znaleziono diagnostyki."],
            )
        return self._response(
            "AUTONOMOUS_DIAGNOSTIC_STATUS",
            diagnostic=diagnostic,
            success=True,
        )

    def recent(self, *, limit: int = 20, category: str = "") -> dict[str, Any]:
        return self._response(
            "AUTONOMOUS_DIAGNOSTICS_RECENT",
            diagnostics=self.store.list_recent(
                limit=limit,
                category=category,
            ),
            success=True,
            summary=self.store.summary(),
        )

    def repair_job(self, job_id: str) -> dict[str, Any]:
        job = self.long_running_store.get_job(job_id) or {}
        last_result = dict(job.get("last_result", {}) or {})
        expected_diagnostic_id = str(
            last_result.get("diagnostic_id", "")
        ).strip()
        latest = self.store.latest_for_job(job_id)
        if (
            latest
            and expected_diagnostic_id
            and str(latest.get("diagnostic_id", ""))
            == expected_diagnostic_id
        ):
            diagnostic = dict(latest)
            diagnostic_response = self._response(
                "AUTONOMOUS_DIAGNOSTIC_STATUS",
                diagnostic=diagnostic,
                success=True,
            )
        else:
            diagnostic_response = self.diagnose_job(job_id)
            diagnostic = dict(
                diagnostic_response.get("diagnostic", {}) or {}
            )
        if not diagnostic:
            return diagnostic_response
        repair = self.repair_engine.repair_job(job_id, diagnostic)
        return self._response(
            str(repair.get("status", "AUTONOMOUS_REPAIR_UNKNOWN")),
            diagnostic=diagnostic,
            repair=repair,
            success=bool(repair.get("success", False)),
            errors=list(repair.get("errors", []) or []),
        )

    def repairs(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "AUTONOMOUS_REPAIRS_RECENT",
            repairs=self.store.list_repairs(limit=limit),
            success=True,
        )

    def status(self) -> dict[str, Any]:
        return self._response(
            "AUTONOMOUS_DIAGNOSTICS_STATUS",
            success=True,
            summary=self.store.summary(),
        )

    def _response(
        self,
        status: str,
        *,
        success: bool,
        diagnostic: dict[str, Any] | None = None,
        diagnostics: list[dict[str, Any]] | None = None,
        repair: dict[str, Any] | None = None,
        repairs: list[dict[str, Any]] | None = None,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": bool(success),
            "status": str(status),
            "operation": "autonomous_diagnostics",
            "diagnostic": dict(diagnostic or {}),
            "diagnostics": list(diagnostics or []),
            "repair": dict(repair or {}),
            "repairs": list(repairs or []),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }
