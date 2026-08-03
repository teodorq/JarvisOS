from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root


DEFAULT_POLICY = {
    "enabled": True,
    "scan_interval_seconds": 900.0,
    "max_dispatch_per_cycle": 1,
    "max_active_jobs": 1,
    "max_backlog": 200,
    "min_score": 25.0,
    "max_risk": 65.0,
    "min_confidence": 0.30,
    "auto_dispatch": True,
    "auto_approve": False,
    "auto_rollback": True,
    "final_validation": True,
}


def prepare_safe_autodev_runtime(project_root: str | Path) -> dict[str, Any]:
    """Repair AutoDev runtime into an active, approval-gated preview lane."""
    root = resolve_project_root(project_root)
    config = _load_json(root / "config" / "b195_autodev_safe_preview.json")
    if config and not bool(config.get("enabled", True)):
        return {"status": "SAFE_AUTODEV_PREVIEW_DISABLED", "enabled": False}

    path = root / "data" / "autodev" / "project_intelligence.json"
    data = _load_json(path)
    if not data:
        data = {
            "version": 1,
            "opportunities": {},
            "order": [],
            "cycles": [],
            "runtime": {},
            "policy": {},
        }
    runtime = dict(data.get("runtime", {}) or {})
    runtime.update({
        "enabled": True,
        "paused": False,
        "running": False,
        "last_error": "",
        "updated_at": _now(),
    })
    policy = {**DEFAULT_POLICY, **dict(data.get("policy", {}) or {})}
    policy.update({
        "auto_dispatch": True,
        "auto_approve": False,
        "max_dispatch_per_cycle": 1,
        "max_active_jobs": 1,
        "scan_interval_seconds": max(
            300.0, float(config.get("scan_interval_seconds", 900.0) or 900.0)
        ),
    })
    data.update({
        "runtime": runtime,
        "policy": policy,
        "updated_at": _now(),
    })
    _save_json(path, data)
    cleaned = _clean_orphan_temps(root / "data" / "autodev")
    return {
        "status": "SAFE_AUTODEV_PREVIEW_READY",
        "enabled": True,
        "auto_dispatch": True,
        "auto_approve": False,
        "max_active_jobs": 1,
        "cleaned_temp_files": cleaned,
        "path": str(path),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return dict(value) if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".foundation2.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _clean_orphan_temps(directory: Path) -> int:
    if not directory.exists():
        return 0
    removed = 0
    for item in directory.glob(".*.tmp"):
        try:
            item.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

if __name__ == "__main__":
    import sys

    selected_root = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(
        prepare_safe_autodev_runtime(selected_root),
        ensure_ascii=False,
        indent=2,
    ))
