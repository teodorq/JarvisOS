from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import count_statuses, now


class LongTermDevelopmentMemoryService:
    """B77 bounded long-term lessons from autonomy outcomes."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store

    def capture(self) -> dict[str, Any]:
        existing = {
            str(item.get("fingerprint", ""))
            for item in self.store.list_records("B77", limit=10000)
        }
        created: list[dict[str, Any]] = []
        policy = self.store.policy("B77")
        stages = tuple(policy.get(
            "source_stages",
            ["B69", "B70", "B71", "B72", "B74", "B75", "B76"],
        ))
        for stage in stages:
            for item in self.store.history(stage=str(stage), limit=50):
                fingerprint = self._fingerprint(item)
                if fingerprint in existing:
                    continue
                memory = self.store.append_record("B77", {
                    "memory_id": f"development-memory-{uuid4().hex}",
                    "fingerprint": fingerprint,
                    "source_stage": str(item.get("stage", stage)),
                    "status": "ACTIVE",
                    "outcome_status": str(item.get("status", "UNKNOWN")),
                    "success": bool(item.get("success", False)),
                    "decision": str(item.get("decision", "")),
                    "lesson": self._lesson(item),
                    "evidence": {
                        "phase": str(item.get("phase", "")),
                        "reason": str(item.get("reason", "")),
                        "error": str(item.get("error", "")),
                    },
                    "created_at": now(),
                })
                existing.add(fingerprint)
                created.append(memory)

        runtime = self.store.runtime("B77")
        self.store.update_runtime("B77", {
            "enabled": True,
            "phase": "READY",
            "cycles_completed": int(runtime.get("cycles_completed", 0) or 0) + 1,
            "last_cycle_at": now(),
            "last_status": "LONG_TERM_DEVELOPMENT_MEMORY_CAPTURED",
            "last_decision": "REMEMBER",
            "last_record_id": str(created[-1].get("memory_id", "")) if created else "",
            "last_result": {"created": len(created)},
            "last_error": "",
        })
        self.store.record_history("B77", {
            "status": "LONG_TERM_DEVELOPMENT_MEMORY_CAPTURED",
            "success": True,
            "phase": "READY",
            "decision": "REMEMBER",
            "reason": f"Nowe lekcje: {len(created)}",
            "error": "",
        })
        return self._response(
            "LONG_TERM_DEVELOPMENT_MEMORY_CAPTURED",
            success=True,
            decision="REMEMBER",
            created=created,
            created_count=len(created),
        )

    def status(self) -> dict[str, Any]:
        memories = self.store.list_records("B77", limit=100)
        return self._response(
            "LONG_TERM_DEVELOPMENT_MEMORY_STATUS",
            success=True,
            memories=memories,
            memory_counts=count_statuses(memories),
            successful_lessons=sum(1 for item in memories if item.get("success")),
            failure_lessons=sum(1 for item in memories if not item.get("success")),
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "LONG_TERM_DEVELOPMENT_MEMORY_HISTORY",
            success=True,
            memories=self.store.list_records("B77", limit=limit),
            history=self.store.history(stage="B77", limit=limit),
        )

    @staticmethod
    def _fingerprint(item: dict[str, Any]) -> str:
        payload = {
            "stage": item.get("stage", ""),
            "status": item.get("status", ""),
            "decision": item.get("decision", ""),
            "reason": item.get("reason", ""),
            "error": item.get("error", ""),
            "created_at": item.get("created_at", ""),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _lesson(item: dict[str, Any]) -> str:
        stage = str(item.get("stage", "UNKNOWN"))
        status = str(item.get("status", "UNKNOWN"))
        decision = str(item.get("decision", ""))
        if bool(item.get("success", False)):
            return (
                f"{stage}: wynik {status} był skuteczny; "
                f"decyzja {decision or 'BRAK'} może być ponownie oceniona."
            )
        error = str(item.get("error", "") or item.get("reason", ""))
        return (
            f"{stage}: wynik {status} nie był skuteczny; "
            f"unikaj powtórzenia bez nowych dowodów. {error[:500]}"
        )

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
            "stage": "B77",
            "runtime": self.store.runtime("B77"),
            "policy": self.store.policy("B77"),
            "summary": self.store.summary("B77"),
            "report_path": str(self.store.path),
            "errors": list(errors or []),
            **extra,
        }
