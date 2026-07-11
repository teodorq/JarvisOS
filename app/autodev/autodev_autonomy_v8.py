from __future__ import annotations

from typing import Any

from app.autodev.autodev_queue_service import (
    AutoDevQueueService,
)


class AutoDevAutonomyV8:
    """
    Zarządza zatwierdzaniem decyzji przygotowanych przez Autonomy V7.

    Warstwa tworzy oczekujące żądanie, pozwala je zatwierdzić albo
    odrzucić i dopiero po zatwierdzeniu umieszcza bezpieczny pakiet
    preview w kolejce. Nie wykonuje zmian i nie zapisuje kodu.
    """

    def __init__(
        self,
        autonomy_v7: Any,
        queue_service: AutoDevQueueService | None = None,
    ) -> None:
        self.autonomy_v7 = autonomy_v7
        self.queue_service = (
            queue_service
            or AutoDevQueueService()
        )
        self.pending: dict[str, dict[str, Any]] = {}
        self.last_result: dict[str, Any] | None = None
        self._request_counter = 0

    def run(self) -> dict[str, Any]:
        gate = self.autonomy_v7.run()

        if not bool(gate.get("success", False)):
            return self._finish(
                {
                    "success": False,
                    "status": "AUTONOMY_V7_FAILED",
                    "gate": gate,
                    "approved": False,
                    "queued": False,
                    "writes_code": False,
                }
            )

        decision = gate.get("decision", {}) or {}

        if not bool(decision.get("allowed", False)):
            return self._finish(
                {
                    "success": True,
                    "status": "DECISION_BLOCKED",
                    "gate": gate,
                    "approved": False,
                    "queued": False,
                    "writes_code": False,
                }
            )

        if not bool(gate.get("requires_approval", True)):
            return self._finish(
                {
                    "success": True,
                    "status": "APPROVAL_NOT_REQUIRED",
                    "gate": gate,
                    "approved": False,
                    "queued": False,
                    "writes_code": False,
                }
            )

        request_id = self._next_request_id()
        request = {
            "request_id": request_id,
            "status": "PENDING_APPROVAL",
            "goal": dict(gate.get("goal", {}) or {}),
            "decision": dict(decision),
            "preview": self._extract_preview(gate),
            "approved": False,
            "queued": False,
            "writes_code": False,
        }
        self.pending[request_id] = dict(request)

        return self._finish(
            {
                "success": True,
                "status": "AUTONOMY_V8_PENDING_APPROVAL",
                "request": dict(request),
                "approved": False,
                "queued": False,
                "writes_code": False,
            }
        )

    def approve(
        self,
        request_id: str,
    ) -> dict[str, Any]:
        request = self.pending.get(request_id)

        if request is None:
            return self._finish(
                {
                    "success": False,
                    "status": "REQUEST_NOT_FOUND",
                    "request_id": request_id,
                    "approved": False,
                    "queued": False,
                    "writes_code": False,
                }
            )

        queued_item = dict(request)
        queued_item.update(
            {
                "status": "APPROVED_AND_QUEUED",
                "approved": True,
                "queued": True,
                "writes_code": False,
            }
        )
        self.queue_service.enqueue(queued_item)
        self.pending.pop(request_id, None)

        return self._finish(
            {
                "success": True,
                "status": "AUTONOMY_V8_APPROVED",
                "request": dict(queued_item),
                "approved": True,
                "queued": True,
                "writes_code": False,
            }
        )

    def reject(
        self,
        request_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        request = self.pending.pop(request_id, None)

        if request is None:
            return self._finish(
                {
                    "success": False,
                    "status": "REQUEST_NOT_FOUND",
                    "request_id": request_id,
                    "approved": False,
                    "queued": False,
                    "writes_code": False,
                }
            )

        rejected = dict(request)
        rejected.update(
            {
                "status": "REJECTED",
                "rejection_reason": str(reason).strip(),
                "approved": False,
                "queued": False,
                "writes_code": False,
            }
        )

        return self._finish(
            {
                "success": True,
                "status": "AUTONOMY_V8_REJECTED",
                "request": rejected,
                "approved": False,
                "queued": False,
                "writes_code": False,
            }
        )

    def _extract_preview(
        self,
        gate: dict[str, Any],
    ) -> dict[str, Any]:
        cycle_v6 = gate.get("cycle", {}) or {}
        cycle_v5 = cycle_v6.get("cycle", {}) or {}
        cycle_v4 = cycle_v5.get("cycle", {}) or {}
        preview = cycle_v4.get("preview", {}) or {}

        if isinstance(preview, dict):
            return dict(preview)

        return {}

    def _next_request_id(self) -> str:
        self._request_counter += 1
        return f"autodev-v8-{self._request_counter:04d}"

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.last_result = dict(result)
        return dict(result)

    def status(self) -> dict[str, Any]:
        return {
            "pending_count": len(self.pending),
            "pending": [
                dict(item)
                for item in self.pending.values()
            ],
            "queue": self.queue_service.status(),
            "last_result": self.last_result,
        }
