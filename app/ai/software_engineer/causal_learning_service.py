from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore


class CausalLearningService:
    """B65 conservative evidence attribution without claiming true causality."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        strategic_execution: Any,
        safe_policy_deployment: Any,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.strategic_execution = strategic_execution
        self.safe_policy_deployment = safe_policy_deployment

    def run_cycle(self) -> dict[str, Any]:
        policy = self.store.policy("B65")
        records = [
            item
            for item in self.strategic_execution.store.list_records(limit=10000)
            if str(item.get("status", "")).upper()
            in {"COMPLETED", "FAILED", "DEFERRED_CONSTRAINTS", "REJECTED"}
        ]
        minimum = int(policy.get("min_evidence", 3))
        if len(records) < minimum:
            return self._finish(
                "CAUSAL_LEARNING_INSUFFICIENT_EVIDENCE",
                success=True,
                phase="READY",
                decision="HOLD",
                reason=f"Dostępne dowody: {len(records)}, wymagane: {minimum}.",
                hypotheses=[],
                evidence_count=len(records),
            )

        groups: dict[str, list[dict[str, Any]]] = {}
        for item in records:
            metadata = dict(item.get("metadata", {}) or {})
            key = str(
                metadata.get("policy_deployment_id")
                or metadata.get("strategic_policy_revision_id")
                or metadata.get("subsystem")
                or "baseline"
            )
            groups.setdefault(key, []).append(item)

        hypotheses: list[dict[str, Any]] = []
        for key, values in groups.items():
            metrics = self._metrics(values)
            confidence = min(1.0, len(values) / max(minimum * 2, 1))
            signal = "NEUTRAL"
            if metrics["failure_rate"] >= float(
                policy.get("failure_signal_threshold", 0.30)
            ):
                signal = "FAILURE_RISK"
            elif metrics["deferred_rate"] >= float(
                policy.get("deferred_signal_threshold", 0.60)
            ):
                signal = "CONSTRAINT_PRESSURE"
            elif metrics["success_rate"] >= 0.70:
                signal = "POSITIVE_ASSOCIATION"
            if confidence < float(policy.get("min_confidence", 0.50)):
                signal = "LOW_CONFIDENCE"
            hypotheses.append({
                "hypothesis_id": f"causal-hypothesis-{uuid4().hex}",
                "status": "OBSERVED",
                "factor": key,
                "signal": signal,
                "confidence": round(confidence, 4),
                "evidence_count": len(values),
                "metrics": metrics,
                "claim_scope": "ASSOCIATION_NOT_PROVEN_CAUSATION",
                "created_at": self._now(),
            })

        existing = self.store.list_records("B65", limit=10000)
        signatures = {
            (str(item.get("factor", "")), str(item.get("signal", "")), int(item.get("evidence_count", 0)))
            for item in existing
        }
        fresh = [
            item
            for item in hypotheses
            if (
                str(item.get("factor", "")),
                str(item.get("signal", "")),
                int(item.get("evidence_count", 0)),
            ) not in signatures
        ]
        for item in fresh:
            self.store.append_record("B65", item)
        return self._finish(
            "CAUSAL_LEARNING_COMPLETED",
            success=True,
            phase="READY",
            decision="OBSERVE",
            hypotheses=fresh,
            evidence_count=len(records),
            groups=len(groups),
        )

    def status(self) -> dict[str, Any]:
        return self._response(
            "CAUSAL_LEARNING_STATUS",
            success=True,
            hypotheses=self.store.list_records("B65", limit=20),
            execution_summary=self.strategic_execution.store.summary(),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "CAUSAL_LEARNING_HISTORY",
            success=True,
            hypotheses=self.store.list_records("B65", limit=limit),
            history=self.store.history(stage="B65", limit=limit),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy("B65", {
            **dict(updates),
            "auto_approve": False,
        })
        return self._response(
            "CAUSAL_LEARNING_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    @staticmethod
    def _metrics(values: list[dict[str, Any]]) -> dict[str, Any]:
        total = max(1, len(values))
        statuses = [str(item.get("status", "")).upper() for item in values]
        completed = statuses.count("COMPLETED")
        failed = statuses.count("FAILED") + statuses.count("REJECTED")
        deferred = statuses.count("DEFERRED_CONSTRAINTS")
        return {
            "observations": len(values),
            "completed": completed,
            "failed": failed,
            "deferred": deferred,
            "success_rate": completed / total,
            "failure_rate": failed / total,
            "deferred_rate": deferred / total,
        }

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        decision: str,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B65")
        hypotheses = extra.get("hypotheses", [])
        last_id = ""
        if isinstance(hypotheses, list) and hypotheses:
            last_id = str(hypotheses[-1].get("hypothesis_id", ""))
        runtime = self.store.update_runtime("B65", {
            "enabled": bool(self.store.policy("B65").get("enabled", True)),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_cycle_at": self._now(),
            "last_status": status,
            "last_decision": decision,
            "last_record_id": last_id,
            "last_result": {"status": status, "success": success},
            "last_error": "",
        })
        response = self._response(
            status,
            success=success,
            runtime=runtime,
            decision=decision,
            **extra,
        )
        self.store.record_history("B65", {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": decision,
            "reason": str(extra.get("reason", "")),
        })
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
            "stage": "B65",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B65"))),
            "policy": dict(extra.pop("policy", self.store.policy("B65"))),
            "summary": self.store.summary("B65"),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
