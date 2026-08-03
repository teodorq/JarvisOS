from __future__ import annotations

from copy import deepcopy
from typing import Any


_STAGE_DEFAULTS: dict[str, dict[str, Any]] = {
    "B62": {
        "enabled": True,
        "min_canary_observations": 3,
        "max_failure_rate": 0.35,
        "max_deferred_rate": 0.80,
        "max_waiting_approval_rate": 0.80,
        "auto_rollback": True,
        "auto_promote_canary": True,
        "auto_approve": False,
    },
    "B63": {
        "enabled": True,
        "deduplicate": True,
        "max_ready_goals_per_subsystem": 5,
        "max_blocked_age_days": 30,
        "archive_stale_blocked": True,
        "preserve_active": True,
        "auto_approve": False,
    },
    "B64": {
        "enabled": True,
        "max_cpu_percent": 85.0,
        "max_ram_percent": 90.0,
        "min_free_disk_gb": 2.0,
        "max_active_leases": 1,
        "daily_cycle_budget": 24,
        "max_consecutive_failures": 3,
        "lease_stale_seconds": 1800.0,
        "auto_approve": False,
    },
    "B65": {
        "enabled": True,
        "min_evidence": 3,
        "min_confidence": 0.50,
        "max_hypotheses": 200,
        "failure_signal_threshold": 0.30,
        "deferred_signal_threshold": 0.60,
        "auto_approve": False,
    },
    "B66": {
        "enabled": True,
        "max_candidates": 50,
        "min_completed_executions": 1,
        "require_manual_activation": True,
        "create_source_snapshot": True,
        "max_snapshot_files": 5000,
        "max_snapshot_size_mb": 250,
        "auto_approve": False,
    },
    "B67": {
        "enabled": True,
        "max_findings": 500,
        "max_scan_files": 5000,
        "large_file_mb": 20,
        "safe_cleanup_only": True,
        "auto_cleanup": False,
        "auto_approve": False,
    },
    "B68": {
        "enabled": False,
        "paused": False,
        "interval_seconds": 300.0,
        "max_cycles_per_session": 100,
        "max_daily_cycles": 24,
        "stop_after_consecutive_failures": 3,
        "auto_dispatch": True,
        "run_release_planning": True,
        "run_maintenance_scan": True,
        "max_cycle_seconds": 600.0,
        "stop_join_seconds": 10.0,
        "interval_jitter_seconds": 17.0,
        "auto_approve": False,
    },
    "B69": {
        "enabled": False,
        "interval_seconds": 60.0,
        "stale_heartbeat_seconds": 900.0,
        "dedup_window_seconds": 3600.0,
        "stage_failure_threshold": 2,
        "max_incidents": 1000,
        "auto_contain_critical": True,
        "auto_resolve_recovered": True,
        "auto_approve": False,
    },
    "B70": {
        "enabled": False,
        "interval_seconds": 90.0,
        "max_plans": 1000,
        "max_attempts_per_incident": 3,
        "auto_plan": True,
        "auto_execute_safe": False,
        "require_manual_execution": True,
        "auto_approve": False,
    },

    "B71": {
        "enabled": True,
        "require_manual_execution": True,
        "allow_state_only_rollback": True,
        "max_executions": 1000,
        "auto_approve": False,
    },
    "B72": {
        "enabled": False,
        "interval_seconds": 300.0,
        "min_evidence": 3,
        "block_success_rate_below": 0.25,
        "unblock_success_rate_at": 0.60,
        "max_lessons": 1000,
        "auto_approve": False,
    },
    "B73": {
        "enabled": True,
        "max_snapshots": 1000,
        "safe_supervisors_only": True,
        "auto_approve": False,
    },
    "B74": {
        "enabled": False,
        "interval_seconds": 60.0,
        "stale_heartbeat_seconds": 900.0,
        "max_restart_attempts": 2,
        "auto_restart_safe": False,
        "max_events": 1000,
        "auto_approve": False,
    },
    "B75": {
        "enabled": True,
        "min_canary_cycles": 1,
        "max_canary_cycles": 10,
        "require_manual_promotion": True,
        "auto_promote": False,
        "max_deployments": 500,
        "auto_approve": False,
    },
    "B76": {
        "enabled": True,
        "require_manual_stable_mark": True,
        "max_release_trains": 500,
        "auto_approve": False,
    },
    "B77": {
        "enabled": True,
        "max_memories": 5000,
        "source_stages": ["B69", "B70", "B71", "B72", "B74", "B75", "B76"],
        "auto_approve": False,
    },
    "B78": {
        "enabled": True,
        "max_scan_files": 5000,
        "max_findings": 500,
        "safe_hardening_only": True,
        "auto_approve": False,
    },
    "B79": {
        "enabled": False,
        "interval_seconds": 300.0,
        "max_cycles_per_session": 288,
        "resume_after_restart": True,
        "automatic_code_execution": False,
        "max_cycles": 5000,
        "auto_approve": False,
    },
}


def default_stage_policies() -> dict[str, dict[str, Any]]:
    return deepcopy(_STAGE_DEFAULTS)


def harden_stage_policy(
    stage: str,
    value: dict[str, Any] | None,
) -> dict[str, Any]:
    key = str(stage).upper().strip()
    defaults = deepcopy(_STAGE_DEFAULTS.get(key, {}))
    source = {**defaults, **dict(value or {})}

    if key == "B62":
        source["min_canary_observations"] = _bounded_int(
            source.get("min_canary_observations"), 1, 100, 3
        )
        for name, default in (
            ("max_failure_rate", 0.35),
            ("max_deferred_rate", 0.80),
            ("max_waiting_approval_rate", 0.80),
        ):
            source[name] = _bounded_float(source.get(name), 0.0, 1.0, default)
    elif key == "B63":
        source["max_ready_goals_per_subsystem"] = _bounded_int(
            source.get("max_ready_goals_per_subsystem"), 1, 100, 5
        )
        source["max_blocked_age_days"] = _bounded_int(
            source.get("max_blocked_age_days"), 1, 3650, 30
        )
    elif key == "B64":
        source["max_cpu_percent"] = _bounded_float(
            source.get("max_cpu_percent"), 10.0, 100.0, 85.0
        )
        source["max_ram_percent"] = _bounded_float(
            source.get("max_ram_percent"), 10.0, 100.0, 90.0
        )
        source["min_free_disk_gb"] = _bounded_float(
            source.get("min_free_disk_gb"), 0.1, 10240.0, 2.0
        )
        source["max_active_leases"] = _bounded_int(
            source.get("max_active_leases"), 1, 4, 1
        )
        source["daily_cycle_budget"] = _bounded_int(
            source.get("daily_cycle_budget"), 1, 1000, 24
        )
        source["max_consecutive_failures"] = _bounded_int(
            source.get("max_consecutive_failures"), 1, 100, 3
        )
        source["lease_stale_seconds"] = _bounded_float(
            source.get("lease_stale_seconds"), 60.0, 86400.0, 1800.0
        )
    elif key == "B65":
        source["min_evidence"] = _bounded_int(
            source.get("min_evidence"), 1, 1000, 3
        )
        source["min_confidence"] = _bounded_float(
            source.get("min_confidence"), 0.0, 1.0, 0.50
        )
        source["max_hypotheses"] = _bounded_int(
            source.get("max_hypotheses"), 10, 5000, 200
        )
        source["failure_signal_threshold"] = _bounded_float(
            source.get("failure_signal_threshold"), 0.0, 1.0, 0.30
        )
        source["deferred_signal_threshold"] = _bounded_float(
            source.get("deferred_signal_threshold"), 0.0, 1.0, 0.60
        )
    elif key == "B66":
        source["max_candidates"] = _bounded_int(
            source.get("max_candidates"), 5, 500, 50
        )
        source["min_completed_executions"] = _bounded_int(
            source.get("min_completed_executions"), 0, 10000, 1
        )
        source["max_snapshot_files"] = _bounded_int(
            source.get("max_snapshot_files"), 100, 50000, 5000
        )
        source["max_snapshot_size_mb"] = _bounded_int(
            source.get("max_snapshot_size_mb"), 10, 2048, 250
        )
    elif key == "B67":
        source["max_findings"] = _bounded_int(
            source.get("max_findings"), 10, 10000, 500
        )
        source["max_scan_files"] = _bounded_int(
            source.get("max_scan_files"), 100, 50000, 5000
        )
        source["large_file_mb"] = _bounded_int(
            source.get("large_file_mb"), 1, 4096, 20
        )
        source["auto_cleanup"] = False
    elif key == "B68":
        source["interval_seconds"] = _bounded_float(
            source.get("interval_seconds"), 60.0, 86400.0, 300.0
        )
        source["max_cycles_per_session"] = _bounded_int(
            source.get("max_cycles_per_session"), 1, 10000, 100
        )
        source["max_daily_cycles"] = _bounded_int(
            source.get("max_daily_cycles"), 1, 1000, 24
        )
        source["stop_after_consecutive_failures"] = _bounded_int(
            source.get("stop_after_consecutive_failures"), 1, 100, 3
        )
        source["max_cycle_seconds"] = _bounded_float(
            source.get("max_cycle_seconds"), 120.0, 86400.0, 600.0
        )
        source["stop_join_seconds"] = _bounded_float(
            source.get("stop_join_seconds"), 1.0, 60.0, 10.0
        )
        source["interval_jitter_seconds"] = _bounded_float(
            source.get("interval_jitter_seconds"), 0.0, 300.0, 17.0
        )
    elif key == "B69":
        source["interval_seconds"] = _bounded_float(
            source.get("interval_seconds"), 30.0, 86400.0, 60.0
        )
        source["stale_heartbeat_seconds"] = _bounded_float(
            source.get("stale_heartbeat_seconds"), 120.0, 86400.0, 900.0
        )
        source["dedup_window_seconds"] = _bounded_float(
            source.get("dedup_window_seconds"), 60.0, 604800.0, 3600.0
        )
        source["stage_failure_threshold"] = _bounded_int(
            source.get("stage_failure_threshold"), 1, 100, 2
        )
        source["max_incidents"] = _bounded_int(
            source.get("max_incidents"), 10, 10000, 1000
        )
        source["auto_contain_critical"] = bool(
            source.get("auto_contain_critical", True)
        )
        source["auto_resolve_recovered"] = bool(
            source.get("auto_resolve_recovered", True)
        )
    elif key == "B70":
        source["interval_seconds"] = _bounded_float(
            source.get("interval_seconds"), 30.0, 86400.0, 90.0
        )
        source["max_plans"] = _bounded_int(
            source.get("max_plans"), 10, 10000, 1000
        )
        source["max_attempts_per_incident"] = _bounded_int(
            source.get("max_attempts_per_incident"), 1, 10, 3
        )
        source["auto_plan"] = bool(source.get("auto_plan", True))
        source["auto_execute_safe"] = False
        source["require_manual_execution"] = True

    elif key == "B71":
        source["max_executions"] = _bounded_int(
            source.get("max_executions"), 10, 10000, 1000
        )
        source["require_manual_execution"] = True
        source["allow_state_only_rollback"] = bool(
            source.get("allow_state_only_rollback", True)
        )
    elif key == "B72":
        source["interval_seconds"] = _bounded_float(
            source.get("interval_seconds"), 30.0, 86400.0, 300.0
        )
        source["min_evidence"] = _bounded_int(
            source.get("min_evidence"), 1, 100, 3
        )
        source["block_success_rate_below"] = _bounded_float(
            source.get("block_success_rate_below"), 0.0, 1.0, 0.25
        )
        source["unblock_success_rate_at"] = _bounded_float(
            source.get("unblock_success_rate_at"), 0.0, 1.0, 0.60
        )
        source["max_lessons"] = _bounded_int(
            source.get("max_lessons"), 10, 10000, 1000
        )
    elif key == "B73":
        source["max_snapshots"] = _bounded_int(
            source.get("max_snapshots"), 10, 10000, 1000
        )
        source["safe_supervisors_only"] = True
    elif key == "B74":
        source["interval_seconds"] = _bounded_float(
            source.get("interval_seconds"), 10.0, 86400.0, 60.0
        )
        source["stale_heartbeat_seconds"] = _bounded_float(
            source.get("stale_heartbeat_seconds"), 60.0, 86400.0, 900.0
        )
        source["max_restart_attempts"] = _bounded_int(
            source.get("max_restart_attempts"), 0, 10, 2
        )
        source["auto_restart_safe"] = False
        source["max_events"] = _bounded_int(
            source.get("max_events"), 10, 10000, 1000
        )
    elif key == "B75":
        source["min_canary_cycles"] = _bounded_int(
            source.get("min_canary_cycles"), 1, 20, 1
        )
        source["max_canary_cycles"] = _bounded_int(
            source.get("max_canary_cycles"), 1, 100, 10
        )
        source["require_manual_promotion"] = True
        source["auto_promote"] = False
        source["max_deployments"] = _bounded_int(
            source.get("max_deployments"), 10, 5000, 500
        )
    elif key == "B76":
        source["require_manual_stable_mark"] = True
        source["max_release_trains"] = _bounded_int(
            source.get("max_release_trains"), 10, 5000, 500
        )
    elif key == "B77":
        source["max_memories"] = _bounded_int(
            source.get("max_memories"), 100, 20000, 5000
        )
        stages = source.get("source_stages", [])
        if not isinstance(stages, list):
            stages = []
        source["source_stages"] = [
            str(item).upper()[:10] for item in stages[:20]
        ] or ["B69", "B70", "B71", "B72", "B74", "B75", "B76"]
    elif key == "B78":
        source["max_scan_files"] = _bounded_int(
            source.get("max_scan_files"), 100, 50000, 5000
        )
        source["max_findings"] = _bounded_int(
            source.get("max_findings"), 10, 10000, 500
        )
        source["safe_hardening_only"] = True
    elif key == "B79":
        source["interval_seconds"] = _bounded_float(
            source.get("interval_seconds"), 30.0, 86400.0, 300.0
        )
        source["max_cycles_per_session"] = _bounded_int(
            source.get("max_cycles_per_session"), 1, 10000, 288
        )
        source["resume_after_restart"] = bool(
            source.get("resume_after_restart", True)
        )
        source["automatic_code_execution"] = False
        source["max_cycles"] = _bounded_int(
            source.get("max_cycles"), 10, 20000, 5000
        )

    source["enabled"] = bool(source.get("enabled", defaults.get("enabled", True)))
    source["auto_approve"] = False
    if key in {"B62", "B63", "B65", "B66", "B67"}:
        for name in (
            "auto_rollback",
            "auto_promote_canary",
            "deduplicate",
            "archive_stale_blocked",
            "preserve_active",
            "require_manual_activation",
            "create_source_snapshot",
            "safe_cleanup_only",
        ):
            if name in source:
                source[name] = bool(source[name])
    return source


def _bounded_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return min(maximum, max(minimum, result))


def _bounded_float(
    value: Any,
    minimum: float,
    maximum: float,
    default: float,
) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    return min(maximum, max(minimum, result))
