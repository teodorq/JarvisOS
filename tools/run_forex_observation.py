"""Run one local Forex observation cycle without executing any order."""

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
from app.market_data.forex_gateway import ForexReadOnlyDataGateway  # noqa: E402
from app.trading.forex_observation import (  # noqa: E402
    ForexObservationJournal,
    ForexObservationService,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="JARVIS OS: obserwacja Forex bez wykonywania zleceń."
    )
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--observation-id", default="")
    arguments = parser.parse_args()
    journal = ForexObservationJournal(PROJECT_ROOT)
    if arguments.status:
        print(json.dumps(journal.summary(), ensure_ascii=False, indent=2))
        return 0
    load_forex_environment(PROJECT_ROOT)
    settings = ForexDataSettings.from_environment()
    now = datetime.now(timezone.utc)
    observation_id = arguments.observation_id.strip() or (
        "forex-observation-" + now.strftime("%Y%m%dT%H%M%SZ")
    )
    service = ForexObservationService(
        PROJECT_ROOT,
        gateway=ForexReadOnlyDataGateway(settings),
        journal=journal,
    )
    result = service.observe_once(observation_id=observation_id, now=now)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OBSERVATION_RECORDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
