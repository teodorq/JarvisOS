from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import traceback
from typing import Any

from .strategic_policy_evolution_service import (
    StrategicPolicyEvolutionService,
    bootstrap_strategic_policy_evolution,
)
from .strategic_policy_validation_analyzer import (
    StrategicPolicyValidationAnalyzer,
)
from .strategic_policy_validation_models import StrategicPolicyExperiment
from .strategic_policy_validation_store import StrategicPolicyValidationStore


class StrategicPolicyValidationService:
    """B61 shadow validation and safe promotion gate for B60 revisions."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        strategic_policy_evolution: StrategicPolicyEvolutionService | Any,
        store: StrategicPolicyValidationStore | None = None,
        analyzer: StrategicPolicyValidationAnalyzer | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.strategic_policy_evolution = strategic_policy_evolution
        self.strategic_portfolio = strategic_policy_evolution.strategic_portfolio
        self.strategic_execution = strategic_policy_evolution.strategic_execution
        self.store = store or StrategicPolicyValidationStore(self.project_root)
        self.analyzer = analyzer or StrategicPolicyValidationAnalyzer()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def run_cycle(self) -> dict[str, Any]:
        with self._lock:
            self._enforce_gate()
            self.store.update_runtime({"phase": "LEARNING", "last_error": ""})
            learning = self.strategic_policy_evolution.learn(apply_if_safe=False)
            proposal = self._proposal()
            if not proposal:
                return self._finish_cycle(
                    "STRATEGIC_POLICY_VALIDATION_NO_PROPOSAL",
                    success=True,
                    phase="READY",
                    decision="HOLD",
                    reason=str(learning.get("reason", "Brak propozycji B60.")),
                    learning=learning,
                )
            validated = self.validate(str(proposal.get("revision_id", "")))
            if (
                validated.get("status") == "STRATEGIC_POLICY_VALIDATION_PASSED"
                and bool(self.store.policy().get("auto_promote_validated", True))
            ):
                return self.promote(str(validated.get("experiment", {}).get(
                    "experiment_id", ""
                )))
            return validated

    def validate(self, revision_id: str = "") -> dict[str, Any]:
        with self._lock:
            self._enforce_gate()
            revision = self._revision(revision_id)
            if not revision:
                return self._response(
                    "STRATEGIC_POLICY_VALIDATION_NO_PROPOSAL",
                    success=False,
                    errors=["Brak proponowanej wersji B60 do walidacji."],
                )
            policy = self.store.policy()
            executions = self.strategic_execution.store.list_records(
                limit=int(policy.get("observation_window", 500))
            )
            entries = self.strategic_portfolio.store.list_entries(limit=1000)
            active = self.strategic_policy_evolution.store.active_revision() or {}
            baseline_policy = dict(
                active.get("policy") or self.strategic_portfolio.store.policy()
            )
            candidate_policy = dict(revision.get("policy", {}) or {})
            analysis = self.analyzer.analyze(
                entries,
                executions,
                baseline_policy=baseline_policy,
                candidate_policy=candidate_policy,
                changes=dict(revision.get("changes", {}) or {}),
                validation_policy=policy,
            )
            signature = str(analysis.get("evidence_signature", ""))
            previous = self.store.latest_for_revision(
                str(revision.get("revision_id", "")), signature
            )
            if previous and str(previous.get("status", "")) in {
                "PASSED", "REJECTED", "INSUFFICIENT_EVIDENCE", "PROMOTED"
            }:
                return self._response(
                    "STRATEGIC_POLICY_VALIDATION_ALREADY_RECORDED",
                    success=True,
                    experiment=previous,
                    decision=previous.get("decision", ""),
                    reason=previous.get("reason", ""),
                    metrics=previous.get("metrics", {}),
                    checks=previous.get("checks", {}),
                )
            decision = str(analysis.get("decision", "HOLD")).upper()
            status = {
                "PASS": "PASSED",
                "REJECT": "REJECTED",
                "HOLD": "INSUFFICIENT_EVIDENCE",
            }.get(decision, "REJECTED")
            experiment = StrategicPolicyExperiment(
                revision_id=str(revision.get("revision_id", "")),
                baseline_revision_id=str(active.get("revision_id", "")),
                candidate_policy=candidate_policy,
                baseline_policy=baseline_policy,
                status=status,
                decision=decision,
                reason=str(analysis.get("reason", "")),
                evidence_signature=signature,
                evidence_count=int(analysis.get("evidence_count", 0) or 0),
                metrics=dict(analysis.get("metrics", {}) or {}),
                checks=dict(analysis.get("checks", {}) or {}),
                completed_at=self._now(),
                metadata={"source": "B61ShadowReplay"},
            )
            saved = self.store.save_experiment(experiment)
            response_status = {
                "PASSED": "STRATEGIC_POLICY_VALIDATION_PASSED",
                "REJECTED": "STRATEGIC_POLICY_VALIDATION_REJECTED",
                "INSUFFICIENT_EVIDENCE": (
                    "STRATEGIC_POLICY_VALIDATION_INSUFFICIENT_EVIDENCE"
                ),
            }[status]
            return self._finish_cycle(
                response_status,
                success=True,
                phase=status,
                decision=decision,
                reason=experiment.reason,
                experiment=saved,
                metrics=experiment.metrics,
                checks=experiment.checks,
            )

    def promote(self, experiment_id: str = "") -> dict[str, Any]:
        with self._lock:
            experiment = self._experiment(experiment_id)
            if not experiment or str(experiment.get("status", "")) != "PASSED":
                return self._response(
                    "STRATEGIC_POLICY_PROMOTION_UNAVAILABLE",
                    success=False,
                    errors=["Brak eksperymentu B61 ze statusem PASSED."],
                )
            revision_id = str(experiment.get("revision_id", ""))
            result = self.strategic_policy_evolution.apply_proposal(revision_id)
            if not bool(result.get("success", False)):
                return self._response(
                    "STRATEGIC_POLICY_PROMOTION_FAILED",
                    success=False,
                    errors=list(result.get("errors", []) or []),
                    experiment=experiment,
                    policy_result=result,
                )
            experiment["status"] = "PROMOTED"
            experiment["promoted_at"] = self._now()
            saved = self.store.save_experiment(experiment)
            self.store.update_runtime({
                "phase": "PROMOTED",
                "last_experiment_id": saved["experiment_id"],
                "last_revision_id": revision_id,
                "last_decision": "PROMOTE",
                "last_result": {"status": "STRATEGIC_POLICY_PROMOTED", "success": True},
                "last_error": "",
            })
            response = self._response(
                "STRATEGIC_POLICY_PROMOTED",
                success=True,
                experiment=saved,
                revision=result.get("revision", {}),
                policy_result=result,
            )
            self._record(response)
            return response

    def reject(self, revision_id: str = "") -> dict[str, Any]:
        with self._lock:
            revision = self._revision(revision_id)
            if not revision:
                return self._response(
                    "STRATEGIC_POLICY_REJECTION_UNAVAILABLE",
                    success=False,
                    errors=["Brak propozycji B60 do odrzucenia."],
                )
            revision["status"] = "REJECTED"
            revision["metadata"] = {
                **dict(revision.get("metadata", {}) or {}),
                "rejected_by": "B61",
            }
            self.strategic_policy_evolution.store.save_revision(revision)
            runtime = self.strategic_policy_evolution.store.runtime()
            if str(runtime.get("proposed_revision_id", "")) == str(
                revision.get("revision_id", "")
            ):
                self.strategic_policy_evolution.store.update_runtime({
                    "proposed_revision_id": "",
                    "phase": "READY",
                })
            experiment = self.store.latest_for_revision(
                str(revision.get("revision_id", ""))
            )
            if experiment:
                experiment["status"] = "REJECTED"
                experiment["decision"] = "REJECT"
                experiment["rejected_at"] = self._now()
                experiment = self.store.save_experiment(experiment)
            response = self._response(
                "STRATEGIC_POLICY_PROPOSAL_REJECTED",
                success=True,
                experiment=experiment or {},
                revision=revision,
            )
            self._record(response)
            return response

    def observe_execution(self, execution: dict[str, Any]) -> dict[str, Any]:
        if not self.is_enabled():
            return self._response(
                "STRATEGIC_POLICY_VALIDATION_EXECUTION_OBSERVED",
                success=True,
                execution_id=str(execution.get("execution_id", "")),
            )
        return self.run_cycle()

    def start_background(self) -> dict[str, Any]:
        if self.is_running():
            return self._response(
                "STRATEGIC_POLICY_VALIDATION_ALREADY_RUNNING",
                success=True,
            )
        with self._lock:
            if self.is_running():
                return self._response(
                    "STRATEGIC_POLICY_VALIDATION_ALREADY_RUNNING",
                    success=True,
                )
            self.store.update_policy({"enabled": True, "auto_approve": False})
            self.store.update_runtime({
                "enabled": True, "paused": False, "running": False,
                "phase": "STARTING", "last_error": "",
            })
            self._enforce_gate()
            if bool(self.store.policy().get("start_b60_with_supervisor", True)):
                self.strategic_policy_evolution.start_background()
            self.store.update_runtime({
                "enabled": True, "paused": False, "running": True,
                "phase": "RUNNING", "last_error": "",
            })
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-strategic-policy-validation",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "STRATEGIC_POLICY_VALIDATION_SUPERVISOR_STARTED",
                success=True,
            )

    def start_if_enabled(self) -> dict[str, Any]:
        self.store.compact()
        self._enforce_gate()
        if bool(self.store.runtime().get("enabled", False)):
            return self.start_background()
        return self._response(
            "STRATEGIC_POLICY_VALIDATION_SUPERVISOR_DISABLED",
            success=True,
        )

    def stop_background(self) -> dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        runtime = self.store.update_runtime({
            "enabled": False, "paused": False, "running": False,
            "phase": "STOPPED",
        })
        return self._response(
            "STRATEGIC_POLICY_VALIDATION_SUPERVISOR_STOPPED",
            success=True,
            runtime=runtime,
        )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({"paused": True, "phase": "PAUSED"})
        return self._response(
            "STRATEGIC_POLICY_VALIDATION_SUPERVISOR_PAUSED",
            success=True,
            runtime=runtime,
        )

    def resume(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({
            "enabled": True, "paused": False, "phase": "RESUMING",
        })
        if not self.is_running():
            return self.start_background()
        return self._response(
            "STRATEGIC_POLICY_VALIDATION_SUPERVISOR_RESUMED",
            success=True,
            runtime=runtime,
        )

    def status(self) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_POLICY_VALIDATION_STATUS",
            success=True,
            latest_experiment=self._experiment("") or {},
            proposal=self._proposal() or {},
            active_revision=(
                self.strategic_policy_evolution.store.active_revision() or {}
            ),
            experiments=self.store.list_experiments(limit=10),
        )

    def experiments(self, *, limit: int = 50) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_POLICY_VALIDATION_EXPERIMENTS",
            success=True,
            experiments=self.store.list_experiments(limit=limit),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_POLICY_VALIDATION_HISTORY",
            success=True,
            history=self.store.history(limit=limit),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy({**dict(updates), "auto_approve": False})
        self._enforce_gate()
        return self._response(
            "STRATEGIC_POLICY_VALIDATION_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def is_enabled(self) -> bool:
        runtime = self.store.runtime()
        policy = self.store.policy()
        return bool(
            runtime.get("enabled", False)
            and not runtime.get("paused", False)
            and policy.get("enabled", True)
            and policy.get("require_validation", True)
        )

    def _run_loop(self) -> None:
        try:
            if self._stop_event.wait(42.0):
                return

            while not self._stop_event.is_set():
                try:
                    if not bool(self.store.runtime().get("paused", False)):
                        self.run_cycle()
                except Exception as error:
                    self.store.update_runtime({
                        "last_error": f"{type(error).__name__}: {error}",
                        "phase": "FAILED",
                    })
                interval = float(
                    self.store.policy().get("validation_interval_seconds", 300.0)
                )
                self._stop_event.wait(max(60.0, interval))
        finally:
            self.store.update_runtime({"running": False})

    def _enforce_gate(self) -> None:
        if bool(self.store.policy().get("require_validation", True)):
            self.strategic_policy_evolution.store.update_policy({
                "auto_apply_safe_changes": False,
                "auto_approve": False,
            })

    def _revision(self, revision_id: str) -> dict[str, Any] | None:
        target_id = str(revision_id).strip() or str(
            self.strategic_policy_evolution.store.runtime().get(
                "proposed_revision_id", ""
            )
        )
        revision = self.strategic_policy_evolution.store.get_revision(target_id)
        if not revision or str(revision.get("status", "")).upper() != "PROPOSED":
            return None
        return revision

    def _proposal(self) -> dict[str, Any] | None:
        return self._revision("")

    def _experiment(self, experiment_id: str) -> dict[str, Any] | None:
        target_id = str(experiment_id).strip() or str(
            self.store.runtime().get("last_experiment_id", "")
        )
        if target_id:
            item = self.store.get_experiment(target_id)
            if item:
                return item
        values = self.store.list_experiments(limit=1)
        return values[0] if values else None

    def _finish_cycle(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime()
        experiment = extra.get("experiment", {})
        experiment = dict(experiment) if isinstance(experiment, dict) else {}
        self.store.update_runtime({
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_validation_at": self._now(),
            "last_experiment_id": experiment.get("experiment_id", ""),
            "last_revision_id": experiment.get("revision_id", ""),
            "last_decision": str(extra.get("decision", "")),
            "last_metrics": dict(extra.get("metrics", {}) or {}),
            "last_result": {"status": status, "success": success},
            "last_error": "",
        })
        response = self._response(status, success=success, **extra)
        self._record(response)
        return response

    def _record(self, response: dict[str, Any]) -> None:
        experiment = response.get("experiment", {})
        experiment = dict(experiment) if isinstance(experiment, dict) else {}
        errors = response.get("errors", [])
        self.store.record_history({
            "status": response.get("status", "UNKNOWN"),
            "success": bool(response.get("success", False)),
            "phase": self.store.runtime().get("phase", ""),
            "experiment_id": experiment.get("experiment_id", ""),
            "revision_id": experiment.get("revision_id", ""),
            "decision": response.get("decision", experiment.get("decision", "")),
            "reason": response.get("reason", experiment.get("reason", "")),
            "error": "; ".join(str(item) for item in errors[:5])
            if isinstance(errors, list) else "",
        })

    def _response(
        self,
        status: str,
        *,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "strategic_policy_validation",
            "runtime": dict(extra.pop("runtime", self.store.runtime())),
            "policy": dict(extra.pop("policy", self.store.policy())),
            "summary": self.store.summary(),
            "b60_summary": self.strategic_policy_evolution.store.summary(),
            "portfolio_summary": self.strategic_portfolio.store.summary(),
            "execution_summary": self.strategic_execution.store.summary(),
            "current_portfolio_policy": self.strategic_portfolio.store.policy(),
            "b60_policy": self.strategic_policy_evolution.store.policy(),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


def bootstrap_strategic_policy_validation(
    controller: Any,
) -> StrategicPolicyValidationService:
    service = getattr(controller, "strategic_policy_validation_service", None)
    if service is None:
        store = StrategicPolicyValidationStore(controller.project_root)
        store.compact()
        policy_evolution = bootstrap_strategic_policy_evolution(controller)
        service = StrategicPolicyValidationService(
            controller.project_root,
            strategic_policy_evolution=policy_evolution,
            store=store,
        )
        controller.strategic_policy_validation_service = service
        policy_evolution.strategic_policy_validation_service = service
        policy_evolution.strategic_portfolio.strategic_policy_validation_service = service
    service.store.compact()
    service._enforce_gate()
    service.start_if_enabled()
    from .autonomy_governance_suite import (
        bootstrap_autonomy_governance_suite,
    )
    bootstrap_autonomy_governance_suite(
        controller,
        strategic_policy_validation=service,
    )
    return service
