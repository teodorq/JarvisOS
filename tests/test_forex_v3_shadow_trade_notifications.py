from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from app.trading.forex_activity_journal import ForexPaperActivityJournal
from app.trading.forex_v3_shadow_trade_notifications import (
    v3_shadow_trade_specs,
)


def _payload(*, action: str = "OPEN_LONG", pnl: str = "0.00") -> dict:
    executions = [{
        "status": "EXECUTED",
        "fill": {
            "fill_id": "forex-v3-shadow-" + "a" * 32,
            "action": action,
            "pair": "EUR_USD",
            "realized_pnl_pln": pnl,
            "filled_at": "2026-11-08T13:02:20+00:00",
        },
    }]
    return {
        "status": "PAPER_CYCLE_COMPLETED",
        "cycle_id": "AZURE-20261108T130200Z-ABCDEF123456",
        "observed_at": "2026-11-08T13:02:00+00:00",
        "v3_shadow_simulation": {
            "status": "SHADOW_SIMULATION_CYCLE_COMPLETED",
            "mode": "FOREX_V3_SHADOW_PAPER_ONLY",
            "shadow_execution_enabled": True,
            "paper_orders_sent": True,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
            "execution": {
                "status": "APPLIED",
                "mode": "FOREX_V3_SHADOW_PAPER_ONLY",
                "executions": executions,
                "live_orders_sent": False,
                "network_access": False,
            },
        },
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def test_v3_shadow_open_fill_becomes_a_bounded_owner_event() -> None:
    specs = v3_shadow_trade_specs(_payload())

    assert len(specs) == 1
    assert specs[0]["kind"] == "FOREX_V3_SHADOW_POSITION_OPENED"
    assert "EUR/USD" in specs[0]["message"]
    assert "izolowana symulacja" in specs[0]["message"]
    assert "prawdziwe środki pozostają zablokowane" in specs[0]["message"]
    assert specs[0]["token"].endswith("a" * 32)


def test_v3_shadow_close_fill_reports_only_the_simulated_result() -> None:
    specs = v3_shadow_trade_specs(_payload(action="CLOSE_LONG", pnl="-3.456"))

    assert specs[0]["kind"] == "FOREX_V3_SHADOW_POSITION_CLOSED"
    assert "-3.46 PLN" in specs[0]["message"]
    assert "broker, LIVE" in specs[0]["message"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("live_orders_sent",), True),
        (("v3_shadow_simulation", "network_access"), True),
        (("v3_shadow_simulation", "mode"), "FOREX_PAPER_ONLY"),
        (("v3_shadow_simulation", "execution", "live_orders_sent"), True),
        (("v3_shadow_simulation", "paper_orders_sent"), False),
        (
            (
                "v3_shadow_simulation",
                "execution",
                "executions",
                0,
                "fill",
                "fill_id",
            ),
            "fill-from-another-ledger",
        ),
    ],
)
def test_v3_shadow_trade_event_fails_closed_on_contract_mismatch(
    path: tuple[object, ...],
    value: object,
) -> None:
    payload = deepcopy(_payload())
    selected: object = payload
    for key in path[:-1]:
        selected = selected[key]  # type: ignore[index]
    selected[path[-1]] = value  # type: ignore[index]

    assert v3_shadow_trade_specs(payload) == []


def test_activity_history_orders_activation_before_first_v3_fill(
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload["v3_shadow_activation"] = {
        "status": "SIMULATION_ACTIVATED",
        "mode": "FOREX_V3_SHADOW_SIMULATION_CONTROL",
        "simulation_activated": True,
        "shadow_simulation_enabled": True,
        "shadow_execution_enabled": True,
        "review_fingerprint_sha256": "b" * 64,
        "candidate_id": "FOREX_STRENGTH_V3R2_20261104",
        "paper_orders_sent": False,
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "network_access": False,
        "real_money_access": False,
    }
    journal = ForexPaperActivityJournal(tmp_path)

    recorded = journal.record(payload)
    events = journal.events(limit=10)

    assert recorded == {"status": "RECORDED", "events_recorded": 2}
    assert [event["kind"] for event in events] == [
        "FOREX_V3_SHADOW_SIMULATION_ACTIVATED",
        "FOREX_V3_SHADOW_POSITION_OPENED",
    ]


def test_activity_history_deduplicates_same_v3_fill_across_cycles(
    tmp_path: Path,
) -> None:
    journal = ForexPaperActivityJournal(tmp_path)
    first = _payload()
    repeated = deepcopy(first)
    repeated["cycle_id"] = "AZURE-20261108T140200Z-ABCDEF123456"
    repeated["observed_at"] = "2026-11-08T14:02:00+00:00"

    assert journal.record(first)["events_recorded"] == 1
    assert journal.record(repeated)["events_recorded"] == 0
    assert len(journal.events(limit=10)) == 1
