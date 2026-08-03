from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    root = Path(args.project_root).resolve(strict=False)
    sys.path.insert(0, str(root))
    from app.ai.software_engineer.autonomous_backlog import AutonomousBacklogReader

    candidates = AutonomousBacklogReader(root).candidates()
    selected = candidates[0].to_dict() if candidates else {}
    print(json.dumps({
        "status": "BACKLOG_AUDIT_COMPLETED",
        "eligible_candidates": len(candidates),
        "selected_task_id": selected.get("task_id", ""),
        "selected_target": selected.get("target", ""),
        "selected_title": selected.get("title", ""),
        "project_files_modified": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
