from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore


_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "DEFERRED_CONSTRAINTS", "REJECTED"}


class SafePolicyDeploymentService:
    """B62 canary observation and automatic rollback after B61 promotion."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        strategic_policy_validation: Any,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.validation = strategic_policy_validation
        self.evolution = strategic_policy_validation.strategic_policy_evolution
        self.execution = strategic_policy_validation.strategic_execution

    def run_cycle(self) -> dict[str, Any]:
        policy = self.store.policy("B62")
        if not bool(policy.get("enabled", True)):
            return self._finish(
                "SAFE_POLICY_DEPLOYMENT_DISABLED",
                success=True,
                phase="DISABLED",
                decision="HOLD",
            )
        active = self._active_deployment()
        if active is None:
            promoted = self._latest_promoted_experiment()
            if not promoted:
                return self._finish(
                    "SAFE_POLICY_DEPLOYMENT_NO_CANDIDATE",
                    success=True,
                    phase="READY",
                    decision="HOLD",
                    reason="Brak nowej promowanej polityki B61.",
                )
            active = self._create_canary(promoted)
            return self._finish(
                "SAFE_POLICY_DEPLOYMENT_CANARY_STARTED",
                success=True,
                phase="CANARY",
                decision="OBSERVE",
                deployment=active,
            )

        observations = self._observations(active)
        metrics = self._metrics(observations)
        minimum = int(policy.get("min_canary_observations", 3))
        if metrics["observations"] < minimum:
            active["status"] = "CANARY"
            active["metrics"] = metrics
            active["updated_at"] = self._now()
            active = self._save(active)
            return self._finish(
                "SAFE_POLICY_DEPLOYMENT_CANARY_HOLD",
                success=True,
                phase="CANARY",
                decision="HOLD",
                reason=f"Oczekiwanie na {minimum} obserwacji B58.",
                deployment=active,
                metrics=metrics,
            )

        unsafe = (
            metrics["failure_rate"] > float(policy.get("max_failure_rate", 0.35))
            or metrics["deferred_rate"] > float(policy.get("max_deferred_rate", 0.80))
            or metrics["waiting_approval_rate"]
            > float(policy.get("max_waiting_approval_rate", 0.80))
        )
        if unsafe and bool(policy.get("auto_rollback", True)):
            rollback = self.evolution.rollback()
            active["status"] = "ROLLED_BACK" if rollback.get("success") else "ROLLBACK_FAILED"
            active["metrics"] = metrics
            active["rollback"] = rollback
            active["completed_at"] = self._now()
            active = self._save(active)
            return self._finish(
                "SAFE_POLICY_DEPLOYMENT_ROLLED_BACK",
                success=bool(rollback.get("success", False)),
                phase=active["status"],
                decision="ROLLBACK",
                reason="Canary przekroczył bezpieczne limity B62.",
                deployment=active,
                metrics=metrics,
                rollback=rollback,
            )

        active["status"] = "ACTIVE"
        active["metrics"] = metrics
        active["completed_at"] = self._now()
        active = self._save(active)
        return self._finish(
            "SAFE_POLICY_DEPLOYMENT_ACTIVATED",
            success=True,
            phase="ACTIVE",
            decision="ACTIVATE",
            deployment=active,
            metrics=metrics,
        )

    def rollback(self) -> dict[str, Any]:
        active = self._active_deployment(include_active=True)
        if not active:
            return self._response(
                "SAFE_POLICY_DEPLOYMENT_ROLLBACK_UNAVAILABLE",
                success=False,
                errors=["Brak aktywnego wdrożenia B62."],
            )
        result = self.evolution.rollback()
        active["status"] = "ROLLED_BACK" if result.get("success") else "ROLLBACK_FAILED"
        active["rollback"] = result
        active["completed_at"] = self._now()
        active = self._save(active)
        response = self._response(
            "SAFE_POLICY_DEPLOYMENT_ROLLED_BACK",
            success=bool(result.get("success", False)),
            deployment=active,
            rollback=result,
            decision="ROLLBACK",
        )
        self._record(response)
        return response

    def status(self) -> dict[str, Any]:
        return self._response(
            "SAFE_POLICY_DEPLOYMENT_STATUS",
            success=True,
            deployment=self._active_deployment(include_active=True) or {},
            deployments=self.store.list_records("B62", limit=10),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "SAFE_POLICY_DEPLOYMENT_HISTORY",
            success=True,
            deployments=self.store.list_records("B62", limit=limit),
            history=self.store.history(stage="B62", limit=limit),
        )

    def execution_context(self) -> dict[str, Any]:
        active = self._active_deployment(include_active=True) or {}
        revision = self.evolution.store.active_revision() or {}
        return {
            "strategic_policy_revision_id": str(revision.get("revision_id", "")),
            "policy_deployment_id": str(active.get("deployment_id", "")),
            "policy_deployment_status": str(active.get("status", "")),
        }

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy("B62", {
            **dict(updates),
            "auto_approve": False,
        })
        return self._response(
            "SAFE_POLICY_DEPLOYMENT_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def _create_canary(self, experiment: dict[str, Any]) -> dict[str, Any]:
        revision_id = str(experiment.get("revision_id", ""))
        existing = self._deployment_for_revision(revision_id)
        if existing:
            return existing
        baseline = self.evolution.store.previous_active_revision() or {}
        records = self.execution.store.list_records(limit=10000)
        signature = self._signature(records)
        deployment = {
            "deployment_id": f"policy-deployment-{uuid4().hex}",
            "revision_id": revision_id,
            "experiment_id": str(experiment.get("experiment_id", "")),
            "baseline_revision_id": str(baseline.get("revision_id", "")),
            "status": "CANARY",
            "started_at": self._now(),
            "evidence_signature_at_start": signature,
            "execution_ids_at_start": [
                str(item.get("execution_id", ""))
                for item in records
                if str(item.get("execution_id", ""))
            ],
            "metrics": {},
        }
        return self.store.append_record("B62", deployment)

    def _observations(self, deployment: dict[str, Any]) -> list[dict[str, Any]]:
        previous_ids = {
            str(item)
            for item in deployment.get("execution_ids_at_start", [])
            if str(item)
        }
        result: list[dict[str, Any]] = []
        for item in self.execution.store.list_records(limit=10000):
            execution_id = str(item.get("execution_id", ""))
            if execution_id in previous_ids:
                continue
            status = str(item.get("status", "")).upper()
            if status in _TERMINAL or status == "WAITING_APPROVAL":
                result.append(item)
        return result

    @staticmethod
    def _metrics(observations: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(observations)
        counts: dict[str, int] = {}
        for item in observations:
            status = str(item.get("status", "UNKNOWN")).upper()
            counts[status] = counts.get(status, 0) + 1
        denominator = max(1, total)
        return {
            "observations": total,
            "completed": counts.get("COMPLETED", 0),
            "failed": counts.get("FAILED", 0) + counts.get("REJECTED", 0),
            "deferred": counts.get("DEFERRED_CONSTRAINTS", 0),
            "waiting_approval": counts.get("WAITING_APPROVAL", 0),
            "failure_rate": (
                counts.get("FAILED", 0) + counts.get("REJECTED", 0)
            ) / denominator,
            "deferred_rate": counts.get("DEFERRED_CONSTRAINTS", 0) / denominator,
            "waiting_approval_rate": counts.get("WAITING_APPROVAL", 0) / denominator,
        }

    def _latest_promoted_experiment(self) -> dict[str, Any] | None:
        for item in self.validation.store.list_experiments(limit=1000):
            if str(item.get("status", "")).upper() != "PROMOTED":
                continue
            revision_id = str(item.get("revision_id", ""))
            if revision_id and not self._deployment_for_revision(revision_id):
                return item
        return None

    def _deployment_for_revision(self, revision_id: str) -> dict[str, Any] | None:
        target = str(revision_id)
        for item in self.store.list_records("B62", limit=2000):
            if str(item.get("revision_id", "")) == target:
                return item
        return None

    def _active_deployment(self, *, include_active: bool = False) -> dict[str, Any] | None:
        states = {"CANARY"}
        if include_active:
            states.add("ACTIVE")
        for item in self.store.list_records("B62", limit=2000):
            if str(item.get("status", "")).upper() in states:
                return item
        return None

    def _save(self, deployment: dict[str, Any]) -> dict[str, Any]:
        records = list(reversed(self.store.list_records("B62", limit=2000)))
        target = str(deployment.get("deployment_id", ""))
        saved = dict(deployment)
        found = False
        for index, item in enumerate(records):
            if str(item.get("deployment_id", "")) == target:
                records[index] = saved
                found = True
                break
        if not found:
            records.append(saved)
        self.store.replace_records("B62", records)
        return saved

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        decision: str,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B62")
        deployment = extra.get("deployment", {})
        deployment = deployment if isinstance(deployment, dict) else {}
        runtime = self.store.update_runtime("B62", {
            "enabled": bool(self.store.policy("B62").get("enabled", True)),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_cycle_at": self._now(),
            "last_status": status,
            "last_decision": decision,
            "last_record_id": str(deployment.get("deployment_id", "")),
            "last_result": {"status": status, "success": success},
            "last_error": "" if success else str(extra.get("reason", "")),
        })
        response = self._response(
            status,
            success=success,
            runtime=runtime,
            decision=decision,
            **extra,
        )
        self._record(response)
        return response

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
            "operation": "autonomy_governance_suite",
            "stage": "B62",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B62"))),
            "policy": dict(extra.pop("policy", self.store.policy("B62"))),
            "summary": self.store.summary("B62"),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    def _record(self, response: dict[str, Any]) -> None:
        self.store.record_history("B62", {
            "status": response.get("status", "UNKNOWN"),
            "success": bool(response.get("success", False)),
            "phase": response.get("runtime", {}).get("phase", ""),
            "decision": response.get("decision", ""),
            "reason": response.get("reason", ""),
            "error": "; ".join(response.get("errors", [])[:5]),
        })

    @staticmethod
    def _signature(records: list[dict[str, Any]]) -> str:
        compact = [
            [
                str(item.get("execution_id", "")),
                str(item.get("status", "")),
                str(item.get("updated_at", "")),
            ]
            for item in records
        ]
        return hashlib.sha256(
            json.dumps(compact, sort_keys=True).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
