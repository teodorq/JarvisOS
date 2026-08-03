from __future__ import annotations

from typing import Any


class ReliabilityReleaseGate:
    """Evaluate the B171-B175 calendar reliability release contract."""

    REQUIRED_STAGES = {
        "B171": "STALE_CALENDAR_PLAN_GUARD_READY",
        "B172": "LIVE_CALENDAR_RESULT_VERIFICATION_READY",
        "B173": "DUPLICATE_PROTECTION_SAFE_RETRY_READY",
        "B174": "SAFE_UNDO_LAST_CALENDAR_CHANGE_READY",
        "B175": "RELIABILITY_RELEASE_GATE_READY",
    }

    @classmethod
    def evaluate(cls, status: dict[str, Any]) -> dict[str, Any]:
        stages = dict(status.get("stages", {}) or {})
        active = dict(status.get("active_resolution", {}) or {})
        checks = {
            **{
                f"stage_{name.lower()}": stages.get(name) == expected
                for name, expected in cls.REQUIRED_STAGES.items()
            },
            "writes_require_confirmation": bool(
                status.get("writes_require_confirmation")
            ) and bool(active.get("writes_require_confirmation")),
            "no_automatic_calendar_changes": not bool(
                active.get("automatic_calendar_changes")
            ),
            "no_automatic_mail_sending": not bool(
                active.get("automatic_mail_sending")
            ) and not bool(status.get("automatic_sending")),
            "duplicate_protection": bool(active.get("duplicate_protection")),
            "safe_retry_is_bounded": active.get("safe_retry_limit") == 1,
            "safe_undo": bool(active.get("safe_undo")),
        }
        failed = [name for name, passed in checks.items() if not passed]
        ready = not failed
        return {
            "status": (
                "B171_B175_RELIABILITY_RELEASE_READY"
                if ready
                else "B171_B175_RELIABILITY_RELEASE_BLOCKED"
            ),
            "ready": ready,
            "checks": checks,
            "failed": failed,
            "client_policy": "NONTECHNICAL_MESSAGES_ONLY",
            "owner_client_execution_parity": True,
        }
