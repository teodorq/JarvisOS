from __future__ import annotations

from pathlib import Path
import json
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
root_text = str(PROJECT_ROOT)
if root_text not in sys.path:
    sys.path.insert(0, root_text)

from app.ai.software_engineer.project_intelligence_store import (
    ProjectIntelligenceStore,
)


def main() -> int:
    store = ProjectIntelligenceStore(PROJECT_ROOT)
    store.compact()
    runtime = store.update_runtime({
        "running": False,
        "last_error": "",
    })
    policy = store.update_policy({
        "auto_approve": False,
    })
    print(
        json.dumps(
            {
                "success": True,
                "status": "B55_PROJECT_INTELLIGENCE_INITIALIZED",
                "runtime": runtime,
                "policy": policy,
                "summary": store.summary(),
                "report_path": str(store.path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
