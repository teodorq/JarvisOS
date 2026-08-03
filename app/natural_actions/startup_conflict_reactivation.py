from __future__ import annotations

from typing import Any


def reactivate_after_verified_undo(
    active: Any, issue: dict[str, Any], action: str, result: dict[str, Any],
) -> str:
    """Forget only a completed decision for a conflict restored by verified undo."""
    if (
        action != "completed"
        or not result.get("scan_completed")
        or str(issue.get("type", "")) != "conflict"
    ):
        return action
    events = {
        str(item.get("id", "")): dict(item)
        for item in (issue.get("first", {}), issue.get("second", {}))
        if str(item.get("id", ""))
    }
    for receipt in reversed(active.move_executor.ledger._items()):
        event = events.get(str(receipt.get("event_id", "")))
        if not event or str(receipt.get("undo_status", "")) != "COMPLETED":
            continue
        restored = active.analyzer.dt(receipt.get("original_start"))
        current = active.analyzer.dt(event.get("start_at"))
        if restored is not None and current is not None and restored == current:
            active.memory.clear_decision(str(issue.get("fingerprint", "")))
            active.memory.remember_issue(issue)
            result["reactivated_after_undo"] = True
            return ""
    return action
