from __future__ import annotations

from typing import Any


class ProactiveCalendarReliabilityGate:
    """Evaluate the B176-B180 proactive calendar safety contract."""

    REQUIRED_STAGES = {
        "B176": "STARTUP_CONFLICT_SCAN_READY",
        "B177": "NEW_CHANGED_CONFLICT_NOTIFICATION_READY",
        "B178": "LIVE_CONFLICT_REFRESH_READY",
        "B178.1": "LIVE_REFRESH_FALLBACK_SUPPRESSION_READY",
        "B179": "SAFE_PROACTIVITY_POLICY_READY",
        "B180": "PROACTIVE_CALENDAR_RELIABILITY_GATE_READY",
    }

    @classmethod
    def evaluate(cls, status: dict[str, Any]) -> dict[str, Any]:
        stages = dict(status.get("stages", {}) or {})
        startup = dict(status.get("startup_conflicts", {}) or {})
        notifications = dict(status.get("startup_notifications", {}) or {})
        brief_guard = dict(status.get("proactive_brief_guard", {}) or {})
        active = dict(status.get("active_resolution", {}) or {})
        checks = {
            **{
                f"stage_{name.lower().replace('.', '_')}":
                stages.get(name) == expected
                for name, expected in cls.REQUIRED_STAGES.items()
            },
            "startup_checks_today_and_tomorrow":
                startup.get("days_checked") == 2,
            "startup_is_silent": bool(startup.get("silent_startup")),
            "new_or_changed_only": bool(
                notifications.get("duplicate_notifications_suppressed")
            ),
            "periodic_brief_duplicate_suppressed": bool(
                brief_guard.get("duplicate_brief_suppressed")
            ),
            "writes_require_confirmation": bool(
                status.get("writes_require_confirmation")
            ) and bool(active.get("writes_require_confirmation")),
            "no_automatic_calendar_changes": not any((
                startup.get("automatic_writes"),
                notifications.get("automatic_writes"),
                brief_guard.get("automatic_writes"),
                active.get("automatic_calendar_changes"),
            )),
        }
        failed = [name for name, passed in checks.items() if not passed]
        ready = not failed
        return {
            "status": (
                "B176_B180_PROACTIVE_CALENDAR_READY"
                if ready
                else "B176_B180_PROACTIVE_CALENDAR_BLOCKED"
            ),
            "ready": ready,
            "checks": checks,
            "failed": failed,
            "client_policy": "NONTECHNICAL_SILENT_ALERTS_ONLY",
            "automatic_calendar_changes": False,
            "confirmation_required_for_resolution": True,
        }
