from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import threading
import traceback
from typing import Any

from .strategic_policy_evolution_analyzer import StrategicPolicyEvolutionAnalyzer
from .strategic_policy_evolution_models import StrategicPolicyRevision
from .strategic_policy_evolution_store import StrategicPolicyEvolutionStore
from .strategic_portfolio_service import (
    StrategicPortfolioService,
    bootstrap_strategic_portfolio,
)


class StrategicPolicyEvolutionService:
    """B60 safe self-learning for the B59 strategic portfolio policy."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        strategic_portfolio: StrategicPortfolioService | Any,
        store: StrategicPolicyEvolutionStore | None = None,
        analyzer: StrategicPolicyEvolutionAnalyzer | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.strategic_portfolio = strategic_portfolio
        self.strategic_execution = strategic_portfolio.strategic_execution
        self.store = store or StrategicPolicyEvolutionStore(self.project_root)
        self.analyzer = analyzer or StrategicPolicyEvolutionAnalyzer()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def learn(
        self,
        *,
        apply_if_safe: bool | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            evolution_policy = self.store.policy()
            self.store.update_runtime({"phase": "LEARNING", "last_error": ""})
            try:
                if not bool(evolution_policy.get("integrate_with_b58", True)):
                    return self._finish_cycle(
                        "STRATEGIC_POLICY_B58_INTEGRATION_DISABLED",
                        success=True,
                        phase="READY",
                    )
                if not bool(evolution_policy.get("integrate_with_b59", True)):
                    return self._finish_cycle(
                        "STRATEGIC_POLICY_B59_INTEGRATION_DISABLED",
                        success=True,
                        phase="READY",
                    )
                self._ensure_baseline()
                executions = self.strategic_execution.store.list_records(
                    limit=int(evolution_policy.get("observation_window", 200))
                )
                signature = self._evidence_signature(executions)
                runtime = self.store.runtime()
                if signature and signature == str(
                    runtime.get("last_evidence_signature", "")
                ):
                    return self._finish_cycle(
                        "STRATEGIC_POLICY_NO_NEW_EVIDENCE",
                        success=True,
                        phase="READY",
                        decision="HOLD",
                        reason="Brak nowych zakończonych wyników B58.",
                        metrics=dict(runtime.get("last_metrics", {}) or {}),
                        changes={},
                    )
                entries = self.strategic_portfolio.store.list_entries(limit=1000)
                current_policy = self.strategic_portfolio.store.policy()
                analysis = self.analyzer.analyze(
                    executions,
                    entries,
                    current_policy=current_policy,
                    evolution_policy=evolution_policy,
                )
                decision = str(analysis.get("decision", "HOLD")).upper()
                changes = dict(analysis.get("changes", {}) or {})
                metrics = dict(analysis.get("metrics", {}) or {})
                self.store.update_runtime({
                    "last_evidence_signature": signature,
                    "last_observation_count": int(
                        metrics.get("observations", 0) or 0
                    ),
                })
                confidence = float(analysis.get("confidence", 0.0) or 0.0)
                reason = str(analysis.get("reason", ""))
                proposed: dict[str, Any] = {}
                if decision == "PROPOSE" and changes:
                    active = self.store.active_revision() or {}
                    revision = StrategicPolicyRevision(
                        policy=dict(analysis.get("proposed_policy", {}) or {}),
                        changes=changes,
                        metrics=metrics,
                        parent_revision_id=str(active.get("revision_id", "")),
                        reason=reason,
                        evidence_count=int(metrics.get("observations", 0) or 0),
                        confidence=confidence,
                    )
                    proposed = self.store.save_revision(revision)
                    self.store.update_runtime({
                        "proposed_revision_id": proposed["revision_id"],
                    })
                should_apply = (
                    bool(evolution_policy.get("auto_apply_safe_changes", True))
                    if apply_if_safe is None else bool(apply_if_safe)
                )
                if self._validation_required():
                    should_apply = False
                if (
                    proposed
                    and should_apply
                    and confidence >= float(evolution_policy.get("min_confidence", 0.45))
                ):
                    return self.apply_proposal(str(proposed["revision_id"]))
                status = (
                    "STRATEGIC_POLICY_PROPOSAL_READY"
                    if proposed else "STRATEGIC_POLICY_EVOLUTION_HOLD"
                )
                return self._finish_cycle(
                    status,
                    success=True,
                    phase="PROPOSAL_READY" if proposed else "READY",
                    decision=decision,
                    reason=reason,
                    metrics=metrics,
                    changes=changes,
                    proposal=proposed,
                )
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                self.store.update_runtime({"phase": "FAILED", "last_error": message})
                result = self._response(
                    "STRATEGIC_POLICY_EVOLUTION_FAILED",
                    success=False,
                    errors=[message],
                    traceback=traceback.format_exc()[-12000:],
                )
                self._record(result)
                return result

    def apply_proposal(self, revision_id: str = "") -> dict[str, Any]:
        with self._lock:
            target_id = str(revision_id).strip() or str(
                self.store.runtime().get("proposed_revision_id", "")
            )
            revision = self.store.get_revision(target_id)
            if not revision or str(revision.get("status", "")).upper() != "PROPOSED":
                return self._response(
                    "STRATEGIC_POLICY_NO_PROPOSAL",
                    success=False,
                    errors=["Brak bezpiecznej proponowanej wersji polityki."],
                )
            changes = dict(revision.get("changes", {}) or {})
            if not changes:
                return self._response(
                    "STRATEGIC_POLICY_EMPTY_PROPOSAL",
                    success=False,
                    errors=["Propozycja nie zawiera bezpiecznych zmian."],
                )
            previous = self.store.active_revision()
            applied_policy = self.strategic_portfolio.store.update_policy({
                **changes,
                "max_active_goals": 1,
                "auto_approve": False,
            })
            if previous:
                previous["status"] = "SUPERSEDED"
                self.store.save_revision(previous)
            revision["status"] = "ACTIVE"
            revision["policy"] = dict(applied_policy)
            revision["applied_at"] = self._now()
            saved = self.store.save_revision(revision)
            self.store.update_runtime({
                "phase": "APPLIED",
                "active_revision_id": saved["revision_id"],
                "proposed_revision_id": "",
                "last_decision": "APPLY",
                "last_error": "",
            })
            rebalance = self.strategic_portfolio.rebalance(
                refresh_roadmap=False,
                reconcile_execution=False,
            )
            result = self._response(
                "STRATEGIC_POLICY_EVOLUTION_APPLIED",
                success=bool(rebalance.get("success", False)),
                revision=saved,
                applied_policy=applied_policy,
                portfolio_rebalance=rebalance,
            )
            self._record(result)
            return result

    def rollback(self) -> dict[str, Any]:
        with self._lock:
            current = self.store.active_revision()
            previous = self.store.previous_active_revision()
            if not current or not previous:
                return self._response(
                    "STRATEGIC_POLICY_ROLLBACK_UNAVAILABLE",
                    success=False,
                    errors=["Brak poprzedniej aktywnej wersji polityki."],
                )
            restored = self.strategic_portfolio.store.update_policy({
                **dict(previous.get("policy", {}) or {}),
                "max_active_goals": 1,
                "auto_approve": False,
            })
            current["status"] = "ROLLED_BACK"
            current["rolled_back_at"] = self._now()
            self.store.save_revision(current)
            previous["status"] = "ACTIVE"
            previous["applied_at"] = self._now()
            saved = self.store.save_revision(previous)
            self.store.update_runtime({
                "phase": "ROLLED_BACK",
                "active_revision_id": saved["revision_id"],
                "proposed_revision_id": "",
                "last_decision": "ROLLBACK",
                "last_error": "",
            })
            result = self._response(
                "STRATEGIC_POLICY_EVOLUTION_ROLLED_BACK",
                success=True,
                revision=saved,
                applied_policy=restored,
            )
            self._record(result)
            return result

    def observe_execution(self, execution: dict[str, Any]) -> dict[str, Any]:
        item = dict(execution or {})
        execution_id = str(item.get("execution_id", "")).strip()
        if execution_id and not self.store.mark_observed(execution_id):
            return self._response(
                "STRATEGIC_POLICY_EXECUTION_ALREADY_OBSERVED",
                success=True,
                execution_id=execution_id,
            )
        self.store.update_runtime({
            "last_observed_execution_id": execution_id,
            "phase": "OBSERVING",
        })
        if not self.is_enabled():
            return self._response(
                "STRATEGIC_POLICY_EXECUTION_OBSERVED",
                success=True,
                execution_id=execution_id,
            )
        validator = getattr(self, "strategic_policy_validation_service", None)
        if validator is not None and validator.is_enabled():
            return validator.observe_execution(item)
        return self.learn()

    def start_background(self) -> dict[str, Any]:
        if self.is_running():
            return self._response(
                "STRATEGIC_POLICY_SUPERVISOR_ALREADY_RUNNING",
                success=True,
            )
        with self._lock:
            if self.is_running():
                return self._response(
                    "STRATEGIC_POLICY_SUPERVISOR_ALREADY_RUNNING",
                    success=True,
                )
            policy = self.store.update_policy({"enabled": True, "auto_approve": False})
            self.store.update_runtime({
                "enabled": True, "paused": False, "running": False,
                "phase": "STARTING", "last_error": "",
            })
            if bool(policy.get("start_b59_with_supervisor", True)):
                self.strategic_portfolio.start_background()
            self.store.update_runtime({
                "enabled": True, "paused": False, "running": True,
                "phase": "RUNNING", "last_error": "",
            })
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-strategic-policy-evolution",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "STRATEGIC_POLICY_SUPERVISOR_STARTED",
                success=True,
            )

    def start_if_enabled(self) -> dict[str, Any]:
        self.store.compact()
        if bool(self.store.runtime().get("enabled", False)):
            return self.start_background()
        return self._response(
            "STRATEGIC_POLICY_SUPERVISOR_DISABLED",
            success=True,
        )

    def stop_background(self) -> dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        runtime = self.store.update_runtime({
            "enabled": False, "paused": False, "running": False, "phase": "STOPPED",
        })
        return self._response(
            "STRATEGIC_POLICY_SUPERVISOR_STOPPED", success=True, runtime=runtime
        )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({"paused": True, "phase": "PAUSED"})
        return self._response(
            "STRATEGIC_POLICY_SUPERVISOR_PAUSED", success=True, runtime=runtime
        )

    def resume(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({
            "enabled": True, "paused": False, "phase": "RESUMING"
        })
        if not self.is_running():
            return self.start_background()
        return self._response(
            "STRATEGIC_POLICY_SUPERVISOR_RESUMED", success=True, runtime=runtime
        )

    def status(self) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_POLICY_EVOLUTION_STATUS",
            success=True,
            active_revision=self.store.active_revision() or {},
            proposal=self.store.get_revision(
                str(self.store.runtime().get("proposed_revision_id", ""))
            ) or {},
            revisions=self.store.list_revisions(limit=10),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_POLICY_EVOLUTION_HISTORY",
            success=True,
            history=self.store.history(limit=limit),
        )

    def revisions(self, *, limit: int = 50) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_POLICY_EVOLUTION_REVISIONS",
            success=True,
            revisions=self.store.list_revisions(limit=limit),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy({**dict(updates), "auto_approve": False})
        return self._response(
            "STRATEGIC_POLICY_EVOLUTION_POLICY_UPDATED",
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
            and policy.get("integrate_with_b58", True)
            and policy.get("integrate_with_b59", True)
        )

    def _run_loop(self) -> None:
        try:
            if self._stop_event.wait(36.0):
                return

            while not self._stop_event.is_set():
                try:
                    if not bool(self.store.runtime().get("paused", False)):
                        self.learn()
                except Exception as error:
                    self.store.update_runtime({
                        "last_error": f"{type(error).__name__}: {error}",
                        "phase": "FAILED",
                    })
                interval = float(
                    self.store.policy().get("learning_interval_seconds", 300.0)
                )
                self._stop_event.wait(max(60.0, interval))
        finally:
            self.store.update_runtime({"running": False})

    def _ensure_baseline(self) -> dict[str, Any]:
        active = self.store.active_revision()
        if active:
            return active
        revision = StrategicPolicyRevision(
            policy=self.strategic_portfolio.store.policy(),
            status="ACTIVE",
            reason="Bazowa bezpieczna polityka B59 przed ewolucją B60.",
            confidence=1.0,
            metadata={"source": "B60Baseline"},
        )
        saved = self.store.save_revision(revision)
        self.store.update_runtime({"active_revision_id": saved["revision_id"]})
        return saved

    def _finish_cycle(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime()
        updates = {
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_learning_at": self._now(),
            "last_decision": str(extra.get("decision", "")),
            "last_metrics": dict(extra.get("metrics", {}) or {}),
            "last_result": {"status": status, "success": success},
            "last_error": "",
        }
        self.store.update_runtime(updates)
        result = self._response(status, success=success, **extra)
        self._record(result)
        return result

    def _record(self, response: dict[str, Any]) -> None:
        revision = response.get("revision") or response.get("proposal") or {}
        revision = dict(revision) if isinstance(revision, dict) else {}
        errors = response.get("errors", [])
        self.store.record_history({
            "status": response.get("status", "UNKNOWN"),
            "success": bool(response.get("success", False)),
            "phase": self.store.runtime().get("phase", ""),
            "revision_id": revision.get("revision_id", ""),
            "decision": response.get("decision", ""),
            "reason": response.get("reason", ""),
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
            "operation": "strategic_policy_evolution",
            "runtime": dict(extra.pop("runtime", self.store.runtime())),
            "policy": dict(extra.pop("policy", self.store.policy())),
            "summary": self.store.summary(),
            "portfolio_summary": self.strategic_portfolio.store.summary(),
            "execution_summary": self.strategic_execution.store.summary(),
            "current_portfolio_policy": self.strategic_portfolio.store.policy(),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    def _validation_required(self) -> bool:
        validator = getattr(self, "strategic_policy_validation_service", None)
        if validator is not None:
            return bool(validator.store.policy().get("require_validation", True))
        path = self.project_root / "data" / "autodev" / (
            "strategic_policy_validation.json"
        )
        if not path.exists():
            return False
        try:
            import json
            payload = json.loads(path.read_text(encoding="utf-8"))
            policy = payload.get("policy", {}) if isinstance(payload, dict) else {}
            return bool(policy.get("require_validation", True))
        except (OSError, ValueError, TypeError):
            return True

    @staticmethod
    def _evidence_signature(executions: list[dict[str, Any]]) -> str:
        evidence = [
            f"{item.get('execution_id', '')}:{item.get('status', '')}:"
            f"{item.get('observed_at') or item.get('updated_at') or ''}"
            for item in executions
            if isinstance(item, dict)
            and str(item.get("execution_id", "")).strip()
        ]
        if not evidence:
            return ""
        return hashlib.sha256("|".join(evidence).encode("utf-8")).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


def bootstrap_strategic_policy_evolution(
    controller: Any,
) -> StrategicPolicyEvolutionService:
    service = getattr(controller, "strategic_policy_evolution_service", None)
    if service is None:
        portfolio = bootstrap_strategic_portfolio(controller)
        service = StrategicPolicyEvolutionService(
            controller.project_root,
            strategic_portfolio=portfolio,
        )
        controller.strategic_policy_evolution_service = service
        portfolio.strategic_policy_evolution_service = service
    service.store.compact()
    service.start_if_enabled()
    return service
