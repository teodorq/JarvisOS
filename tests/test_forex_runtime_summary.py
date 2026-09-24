from __future__ import annotations

import json
from pathlib import Path

from app.gui.forex_runtime_cycle_view import forex_runtime_cycle_text
from app.trading.forex_runtime_summary import ForexRuntimeCycleSummary


def _write(root: Path, value: object) -> None:
    path = root / "data" / "trading" / "forex_paper_last.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_runtime_summary_tolerates_malformed_nested_collections(
    tmp_path: Path,
) -> None:
    _write(tmp_path, {
        "status": "PAPER_CYCLE_COMPLETED",
        "paper": {
            "status": "CYCLE_COMPLETED",
            "assessments": 17,
            "execution": {"executions": {"unexpected": True}},
        },
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    })

    summary = ForexRuntimeCycleSummary(tmp_path).snapshot()

    assert summary["status"] == "PAPER_CYCLE_COMPLETED"
    assert summary["ready_pair_count"] == 0
    assert summary["execution_count"] == 0
    assert summary["live_orders_sent"] is False


def test_runtime_summary_and_view_fail_closed_on_unsafe_flags(
    tmp_path: Path,
) -> None:
    _write(tmp_path, {
        "status": "PAPER_CYCLE_COMPLETED",
        "paper": {"assessments": [], "execution": {"executions": []}},
        "broker_orders_sent": False,
        "live_orders_sent": True,
        "real_money_access": False,
    })

    summary = ForexRuntimeCycleSummary(tmp_path).snapshot()
    text = forex_runtime_cycle_text(summary)

    assert summary["status"] == "SAFETY_VIOLATION"
    assert summary["live_orders_sent"] is True
    assert "odrzucony przez kontrolę bezpieczeństwa" in text
    assert "LIVE pozostaje wyłączony" in text
