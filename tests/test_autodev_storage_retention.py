from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.ai.software_engineer.full_autonomy_store import FullAutonomyStore
from app.ai.software_engineer.safe_development_store import SafeDevelopmentStore
from tools.compact_autodev_json import compact_autodev_json


def test_autodev_json_stores_use_compact_atomic_serialization() -> None:
    root = Path(__file__).resolve().parents[1]
    store_root = root / "app" / "ai" / "software_engineer"
    checked = 0
    for path in store_root.glob("*_store.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "JsonStore"
            ):
                continue
            checked += 1
            indent = next(
                (item.value for item in node.keywords if item.arg == "indent"),
                None,
            )
            assert isinstance(indent, ast.Constant), path.name
            assert indent.value is None, path.name
    assert checked >= 10


def test_autodev_compactor_is_allowlisted_atomic_and_semantic() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        data = root / "data" / "autodev"
        data.mkdir(parents=True)
        selected = data / "change_campaigns.json"
        unrelated = data / "owner_notes.json"
        payload = {"version": 1, "items": [{"name": "zażółć", "value": 7}]}
        selected.write_text(
            json.dumps(payload, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        unrelated.write_text('{"keep": true}\n', encoding="utf-8")
        before = selected.read_bytes()

        preview = compact_autodev_json(root)
        assert selected.read_bytes() == before
        result = compact_autodev_json(root, apply=True)

        assert preview["saved_bytes"] == 0
        assert result["saved_bytes"] > 0
        assert json.loads(selected.read_text(encoding="utf-8")) == payload
        assert selected.stat().st_size < len(before)
        assert unrelated.read_text(encoding="utf-8") == '{"keep": true}\n'
        assert not list(data.glob("*.compact.tmp"))


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


def test_full_autonomy_compaction_rewrites_existing_history_compactly() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        path = root / "data" / "autodev" / "full_autonomy_runs.json"
        path.parent.mkdir(parents=True)
        payload = {
            "version": 1,
            "updated_at": "",
            "runs": {
                "run-1": {
                    "run_id": "run-1",
                    "details": {"items": list(range(100))},
                },
            },
            "order": ["run-1"],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        before_bytes = path.stat().st_size

        result = FullAutonomyStore(root).compact()
        compact_text = path.read_text(encoding="utf-8")

    assert result == {"kept": 1, "removed": 0}
    assert len(compact_text.encode("utf-8")) < before_bytes
    assert "\n" not in compact_text
    assert ": " not in compact_text
    assert json.loads(compact_text) == payload


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


def test_changed_source_expires_pending_session_and_drops_workspace() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        target = root / "app" / "example.py"
        target.parent.mkdir(parents=True)
        original = "VALUE = 1\n"
        target.write_text(original, encoding="utf-8")
        store = SafeDevelopmentStore(root)
        session = store.new_session(
            target="app/example.py",
            transform="replace",
            title="Test",
            rationale="Test stale reconciliation",
            risk_score=1.0,
            confidence=1.0,
        )
        workspace = Path(session.workspace_path)
        workspace.mkdir(parents=True)
        (workspace / "copy.py").write_text(original, encoding="utf-8")
        artifacts = store.session_dir(session.session_id) / "artifacts"
        artifacts.mkdir()
        evidence = artifacts / "change.diff"
        evidence.write_text("evidence", encoding="utf-8")
        session.source_hash = hashlib.sha256(original.encode()).hexdigest()
        session.status = "READY_FOR_APPROVAL"
        store.save_session(session)
        target.write_text("VALUE = 2\n", encoding="utf-8")

        refreshed = SafeDevelopmentStore(root)
        saved = refreshed.load_session(session.session_id)

        assert saved.status == "STALE"
        assert not workspace.exists()
        assert evidence.read_text(encoding="utf-8") == "evidence"


def test_line_ending_difference_does_not_expire_pending_session() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        target = root / "app" / "example.py"
        target.parent.mkdir(parents=True)
        normalized = "VALUE = 1\n"
        target.write_bytes(b"VALUE = 1\r\n")
        store = SafeDevelopmentStore(root)
        session = store.new_session(
            target="app/example.py",
            transform="replace",
            title="Test",
            rationale="Test newline normalization",
            risk_score=1.0,
            confidence=1.0,
        )
        workspace = Path(session.workspace_path)
        workspace.mkdir(parents=True)
        session.source_hash = hashlib.sha256(normalized.encode()).hexdigest()
        session.status = "READY_FOR_APPROVAL"
        store.save_session(session)

        refreshed = SafeDevelopmentStore(root)

        assert refreshed.load_session(session.session_id).status == "READY_FOR_APPROVAL"
        assert workspace.exists()
