from __future__ import annotations

from typing import Any


class ProactiveConflictBriefGuard:
    """Prevents a periodic daily brief from repeating a known conflict."""

    @staticmethod
    def evaluate(
        scan_result: dict[str, Any],
        notification_status: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(scan_result or {})
        status = dict(notification_status or {})
        fingerprint = str(result.get("fingerprint", "") or "")
        conflict_present = bool(result.get("conflict_count")) and bool(
            fingerprint
        )

        if not result.get("scan_completed"):
            return {
                "suppress": False,
                "reason": "transient",
                "fingerprint": fingerprint,
            }
        if not conflict_present:
            return {
                "suppress": False,
                "reason": "quiet",
                "fingerprint": "",
            }
        if not result.get("should_show"):
            return {
                "suppress": True,
                "reason": "suppressed_by_decision",
                "fingerprint": fingerprint,
            }

        active = str(status.get("active_fingerprint", "") or "")
        same = active == fingerprint
        reactivated = bool(result.get("reactivated_after_undo"))
        if same and not reactivated:
            return {
                "suppress": True,
                "reason": "unchanged",
                "fingerprint": fingerprint,
            }
        return {
            "suppress": False,
            "reason": "changed" if same else "new",
            "fingerprint": fingerprint,
        }

    @staticmethod
    def status() -> dict[str, Any]:
        return {
            "status": "LIVE_REFRESH_FALLBACK_SUPPRESSION_READY",
            "duplicate_brief_suppressed": True,
            "automatic_writes": False,
        }
