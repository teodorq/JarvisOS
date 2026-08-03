from __future__ import annotations

from pathlib import Path
import json
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)

from app.ai.software_engineer.project_intelligence_store import (  # noqa: E402
    ProjectIntelligenceStore,
)
from app.ai.software_engineer.self_directed_development_store import (  # noqa: E402
    SelfDirectedDevelopmentStore,
)


def main() -> int:
    store = SelfDirectedDevelopmentStore(PROJECT_ROOT)
    compacted = store.compact()
    project_store = ProjectIntelligenceStore(PROJECT_ROOT)
    summary = project_store.summary()
    payload = {
        "success": True,
        "status": "B56_SELF_DIRECTED_DEVELOPMENT_INITIALIZED",
        "runtime": store.runtime(),
        "policy": store.policy(),
        "project_summary": summary,
        "compacted": compacted,
        "report_path": str(store.path),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
