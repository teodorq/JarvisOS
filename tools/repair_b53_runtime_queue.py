from __future__ import annotations

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai.software_engineer.long_running_autonomy_service import (
    LongRunningAutonomyService,
)


def main() -> int:
    service = LongRunningAutonomyService(PROJECT_ROOT)
    result = service.repair_queue(force_running=True)
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
