from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.ai.software_engineer.full_autonomy_store import FullAutonomyStore
from app.ai.software_engineer.safe_development_store import SafeDevelopmentStore


def test_full_autonomy_compaction_keeps_newest_records() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        path = root / "data" / "autodev" / "full_autonomy_runs.json"
        path.parent.mkdir(parents=True)
        order = [f"run-{index}" for index in range(12)]
        path.write_text(json.dumps({
            "version": 1,
            "runs": {item: {"run_id": item} for item in order},
            "order": order,
        }), encoding="utf-8")
        result = FullAutonomyStore(root, max_records=10).compact()
        payload = json.loads(path.read_text(encoding="utf-8"))
    assert result == {"kept": 10, "removed": 2}
    assert payload["order"] == order[-10:]
    assert set(payload["runs"]) == set(order[-10:])


def test_terminal_session_drops_workspace_but_keeps_artifacts() -> None:
    with TemporaryDirectory() as temporary:
        store = SafeDevelopmentStore(temporary)
        session = store.new_session(
            target="app/example.py",
            transform="replace",
            title="Test",
            rationale="Test retention",
            risk_score=1.0,
            confidence=1.0,
        )
        workspace = Path(session.workspace_path)
        workspace.mkdir(parents=True)
        (workspace / "copy.py").write_text("print('copy')", encoding="utf-8")
        artifacts = store.session_dir(session.session_id) / "artifacts"
        artifacts.mkdir()
        evidence = artifacts / "change.diff"
        evidence.write_text("evidence", encoding="utf-8")
        session.status = "DEPLOYED"
        store.save_session(session)
        assert not workspace.exists()
        assert evidence.read_text(encoding="utf-8") == "evidence"
