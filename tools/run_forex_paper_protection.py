"""Run one local close-only SL/TP check for existing Forex PAPER positions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.market_data.forex_environment import (  # noqa: E402
    ForexDataSettings,
    load_forex_environment,
)
from app.market_data.forex_paper_protection import (  # noqa: E402
    ForexPaperProtectionRuntime,
)
from app.trading.forex_activity_journal import ForexPaperActivityJournal  # noqa: E402
from app.trading.models import aware_utc  # noqa: E402


def _utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return aware_utc(parsed, "recovery_since")
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("invalid UTC recovery timestamp") from error


def main() -> int:
    parser = argparse.ArgumentParser(
        description="JARVIS OS: lokalna ochrona SL/TP istniejacej pozycji PAPER."
    )
    parser.add_argument("--cycle-id", default="")
    parser.add_argument("--recovery-since", type=_utc_datetime, default=None)
    arguments = parser.parse_args()
    load_forex_environment(PROJECT_ROOT)
    settings = ForexDataSettings.from_environment()
    now = datetime.now(timezone.utc)
    cycle_id = arguments.cycle_id.strip() or (
        "paper-protection-" + now.strftime("%Y%m%dT%H%M%SZ")
    )
    result = ForexPaperProtectionRuntime(
        PROJECT_ROOT,
        settings=settings,
    ).run_once(
        cycle_id=cycle_id,
        now=now,
        recovery_since=arguments.recovery_since,
    )
    activity_history = ForexPaperActivityJournal(PROJECT_ROOT)
    try:
        protection_health = activity_history.record_protection_health(result)
        result["protection_health_status"] = protection_health["status"]
        result["protection_consecutive_failure_count"] = protection_health[
            "consecutive_failure_count"
        ]
        result["protection_attention_required"] = protection_health[
            "attention_required"
        ]
        result["protection_health_events_recorded"] = protection_health[
            "events_recorded"
        ]
    except (
        KeyError,
        OSError,
        RuntimeError,
        TimeoutError,
        TypeError,
        ValueError,
    ):
        result["protection_health_status"] = "WRITE_FAILED"
    if result.get("status") == "PAPER_PROTECTION_APPLIED":
        try:
            history = activity_history.record(result)
            result["activity_history_status"] = history["status"]
            result["activity_history_events_recorded"] = history[
                "events_recorded"
            ]
        except (OSError, RuntimeError, TimeoutError):
            result["activity_history_status"] = "WRITE_FAILED"
            result["activity_history_events_recorded"] = 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {
        "NO_OPEN_POSITIONS",
        "NO_PROTECTION_TRIGGER",
        "PAPER_PROTECTION_APPLIED",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
