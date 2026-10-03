from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.autodev_compaction import (  # noqa: E402
    AUTODEV_JSON_FILES,
    compact_autodev_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bezpieczna kompakcja aktywnych magazynów AutoDev JARVIS OS.",
    )
    parser.add_argument("--project-root", default=PROJECT_ROOT)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    result = compact_autodev_json(arguments.project_root, apply=arguments.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["AUTODEV_JSON_FILES", "compact_autodev_json", "main"]
