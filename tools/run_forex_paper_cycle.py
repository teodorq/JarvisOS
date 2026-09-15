"""Run one explicitly enabled autonomous local Forex PAPER cycle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.market_data.forex_environment import (  # noqa: E402
    ForexDataSettings,
    load_forex_environment,
)
from app.market_data.forex_paper_runtime import ForexDemoPaperRuntime  # noqa: E402
from app.trading.forex_activity_journal import ForexPaperActivityJournal  # noqa: E402


_SCHEDULED_NONCE = re.compile(r"^[0-9a-f]{32}$")


def _watchdog_ancestor_matches(expected_process_id: int) -> bool:
    if expected_process_id <= 0:
        return False
    expected_script = str(
        (PROJECT_ROOT / "tools" / "forex_observer_watchdog.ps1").resolve()
    ).replace("/", "\\").casefold()
    try:
        for ancestor in psutil.Process().parents()[:8]:
            if ancestor.pid != expected_process_id:
                continue
            executable = ancestor.name().casefold()
            command_line = " ".join(ancestor.cmdline()).replace(
                "/", "\\"
            ).casefold()
            return (
                executable in {"powershell.exe", "pwsh.exe"}
                and expected_script in command_line
            )
    except (psutil.Error, OSError):
        return False
    return False


def _capture_context() -> tuple[str, dict[str, object]]:
    nonce = os.environ.pop("JARVIS_OS_FOREX_SCHEDULED_NONCE", "")
    raw_parent = os.environ.pop("JARVIS_OS_FOREX_WATCHDOG_PID", "")
    try:
        expected_watchdog = int(raw_parent)
    except (TypeError, ValueError):
        expected_watchdog = 0
    watchdog_matches = _watchdog_ancestor_matches(expected_watchdog)
    if _SCHEDULED_NONCE.fullmatch(nonce) and watchdog_matches:
        return "SCHEDULED_FORWARD", {
            "kind": "LOCAL_WATCHDOG_ANCESTRY_NONCE_V1",
            "verified": True,
            "trust_level": "BEST_EFFORT_LOCAL_PROCESS",
            "verified_scope": "WATCHDOG_ANCESTRY_AND_NONCE_FORMAT",
            "nonce_sha256": hashlib.sha256(nonce.encode("ascii")).hexdigest(),
            "watchdog_process_id": expected_watchdog,
        }
    return "MANUAL", {
        "kind": "MANUAL_DIRECT_V1",
        "verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "JARVIS OS: autonomiczny lokalny Forex PAPER bez zlecen brokera."
        )
    )
    parser.add_argument("--cycle-id", default="")
    arguments = parser.parse_args()
    load_forex_environment(PROJECT_ROOT)
    settings = ForexDataSettings.from_environment()
    now = datetime.now(timezone.utc)
    cycle_id = arguments.cycle_id.strip() or (
        "autopaper-" + now.strftime("%Y%m%dT%H%M%SZ")
    )
    capture_origin, capture_attestation = _capture_context()
    activity_history = ForexPaperActivityJournal(PROJECT_ROOT)
    try:
        activity_history.initialize()
    except (OSError, RuntimeError, TimeoutError):
        pass
    result = ForexDemoPaperRuntime(
        PROJECT_ROOT,
        settings=settings,
    ).run_once(
        cycle_id=cycle_id,
        now=now,
        capture_origin=capture_origin,
        capture_attestation=capture_attestation,
    )
    result.setdefault("observed_at", now.isoformat())
    try:
        history = activity_history.record(result)
        result["activity_history_status"] = history["status"]
        result["activity_history_events_recorded"] = history["events_recorded"]
    except (OSError, RuntimeError, TimeoutError):
        result["activity_history_status"] = "WRITE_FAILED"
        result["activity_history_events_recorded"] = 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PAPER_CYCLE_COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
