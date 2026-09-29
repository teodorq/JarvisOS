"""Build or review a strict, signal-only Forex candidate report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.trading.forex_forward_evidence import (  # noqa: E402
    ForexV2ForwardEvidenceReport,
    ForexV3ForwardEvidenceReport,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "JARVIS OS: ścisły raport sygnałów V2/V3 z nowych cykli forward."
        )
    )
    parser.add_argument(
        "--candidate",
        choices=("v2", "v3"),
        default="v2",
        help="Wybierz zamrożonego kandydata (domyślnie: v2).",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Przelicz raport bez zapisywania pliku latest.",
    )
    arguments = parser.parse_args()
    reporter_class = (
        ForexV3ForwardEvidenceReport
        if arguments.candidate == "v3"
        else ForexV2ForwardEvidenceReport
    )
    reporter = reporter_class(PROJECT_ROOT)
    report = reporter.review() if arguments.review else reporter.refresh()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    blocked = str(report.get("status", "")).startswith("BLOCKED")
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
