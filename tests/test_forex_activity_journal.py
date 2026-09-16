from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.market_data.forex_environment import ForexDataSettings
from app.trading.forex_activity import ForexPaperActivityFeed
from app.trading.forex_activity_journal import ForexPaperActivityJournal
from app.trading.forex_candidate_v2 import ForexRegimeCandidatePolicy
from app.trading.forex_forward_evidence import (
    expected_candidate_implementation_sha256,
)


def _settings() -> ForexDataSettings:
    return ForexDataSettings(
        enabled=True,
        paper_autopilot_enabled=True,
        primary_provider="MT5_DEMO",
    )


def _payload(
    cycle: int,
    *,
    action: str = "",
    status: str = "PAPER_CYCLE_COMPLETED",
) -> dict:
    executions = []
    if action:
        executions.append({
            "status": "EXECUTED",
            "fill": {
                "fill_id": f"fill-{cycle}",
                "action": action,
                "pair": "EUR_USD",
                "realized_pnl_pln": "12.34",
                "filled_at": f"2026-08-21T10:{cycle:02d}:00+00:00",
            },
        })
    return {
        "status": status,
        "cycle_id": f"cycle-{cycle}",
        "observed_at": f"2026-08-21T10:{cycle:02d}:00+00:00",
        "paper": {"execution": {"executions": executions}},
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def _complete_forward_report() -> dict:
    policy = ForexRegimeCandidatePolicy()
    day_values = ("21",) * 7 + ("24",) * 7 + ("25",) * 6
    accepted = []
    for index, day in enumerate(day_values):
        token = hashlib.sha256(f"accepted-{index}".encode("ascii")).hexdigest()
        accepted.append({
            "sequence": index + 1,
            "observation_id": f"forward-notification-{index:04d}",
            "observation_hash": token,
            "observed_at": f"2026-08-{day}T10:{index % 7 * 2:02d}:00+00:00",
            "source_cycle_id": f"forward-source-cycle-{index:04d}",
            "bars_sha256": token,
            "decision_input_sha256": token,
            "capture_nonce_sha256": token,
        })
    report = {
        "schema_version": 1,
        "status": "FORWARD_OBSERVATION_SAMPLE_COMPLETE",
        "mode": "FOREX_V2_FORWARD_SIGNAL_EVIDENCE_ONLY",
        "generated_at": "2026-08-26T12:00:00+00:00",
        "source_state_valid": True,
        "source_cutoff_sequence": 20,
        "source_head_hash": hashlib.sha256(b"forward-head").hexdigest(),
        "candidate_id": policy.candidate_id,
        "frozen_after": policy.frozen_after.isoformat(),
        "policy_fingerprint_sha256": policy.fingerprint_sha256,
        "implementation_sha256": expected_candidate_implementation_sha256(),
        "accepted_cycle_count": 20,
        "accepted_market_day_count": 3,
        "minimum_accepted_cycle_count": 20,
        "minimum_market_day_count": 3,
        "remaining_accepted_cycles": 0,
        "remaining_market_days": 0,
        "observation_sample_complete": True,
        "excluded_cycle_count": 0,
        "invalid_cycle_count": 0,
        "accepted_observations": accepted,
        "accepted_by_market_day": {
            "2026-08-21": 7,
            "2026-08-24": 7,
            "2026-08-25": 6,
        },
        "exclusions": {},
        "invalid_issues": {},
        "signal_comparison": {
            "base_entry_signal_count": 0,
            "retained_entry_signal_count": 0,
            "filtered_entry_signal_count": 0,
        },
        "evidence_valid": True,
        "pnl_included": False,
        "strategy_performance_validated": False,
        "automatic_paper_strategy_change": False,
        "automatic_paper_promotion": False,
        "automatic_live_promotion": False,
        "paper_changes_applied": False,
        "live_changes_applied": False,
        "paper_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }
    canonical = json.dumps(
        {
            key: value
            for key, value in report.items()
            if key not in {"generated_at", "content_sha256"}
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    report["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    return report


def test_closed_gui_events_are_delivered_oldest_first_after_start() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        journal = ForexPaperActivityJournal(root)
        journal.initialize()
        journal.record(_payload(1, action="OPEN_LONG"))
        journal.record(_payload(2, action="CLOSE_LONG"))

        feed = ForexPaperActivityFeed(root, settings=_settings())
        first = feed.poll()
        second = feed.poll()

        assert first is not None and first["activity_kind"] == "POSITION_OPENED"
        assert second is not None and second["activity_kind"] == "POSITION_CLOSED"
        assert first["activity_sequence"] < second["activity_sequence"]
        assert feed.poll() is None
        assert feed.status()["pending_count"] == 0


def test_duplicate_cycle_never_creates_duplicate_history_event() -> None:
    with TemporaryDirectory() as temporary:
        journal = ForexPaperActivityJournal(Path(temporary))
        result = _payload(3, action="OPEN_SHORT")

        first = journal.record(result)
        duplicate = journal.record(result)

        assert first == {"status": "RECORDED", "events_recorded": 1}
        assert duplicate == {"status": "DUPLICATE_CYCLE", "events_recorded": 0}
        assert journal.status()["event_count"] == 1


def test_completed_forward_sample_is_notified_once_with_trade_event() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        journal = ForexPaperActivityJournal(root)
        first = _payload(60, action="OPEN_LONG")
        first["forward_evidence"] = _complete_forward_report()

        recorded = journal.record(first)
        repeated = _payload(61)
        repeated["forward_evidence"] = _complete_forward_report()
        duplicate_milestone = journal.record(repeated)
        events = journal.events(limit=10)

        assert recorded == {"status": "RECORDED", "events_recorded": 2}
        assert duplicate_milestone == {
            "status": "RECORDED",
            "events_recorded": 0,
        }
        assert [event["kind"] for event in events] == [
            "POSITION_OPENED",
            "FOREX_V2_FORWARD_REVIEW_READY",
        ]
        assert "nie potwierdza zysku" in events[-1]["message"]
        assert "nie włącza LIVE" in events[-1]["message"]
        feed = ForexPaperActivityFeed(root, settings=_settings())
        assert feed.poll()["activity_kind"] == "POSITION_OPENED"
        assert feed.poll()["activity_kind"] == "FOREX_V2_FORWARD_REVIEW_READY"
        assert feed.poll() is None


def test_tampered_forward_completion_never_creates_review_milestone() -> None:
    with TemporaryDirectory() as temporary:
        journal = ForexPaperActivityJournal(Path(temporary))
        payload = _payload(62)
        report = _complete_forward_report()
        report["accepted_cycle_count"] = 21
        canonical = json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"generated_at", "content_sha256"}
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        report["content_sha256"] = hashlib.sha256(canonical).hexdigest()
        payload["forward_evidence"] = report

        result = journal.record(payload)

        assert result == {"status": "RECORDED", "events_recorded": 0}
        assert journal.events(limit=10) == []


def test_block_and_recovery_are_recorded_only_on_transitions() -> None:
    with TemporaryDirectory() as temporary:
        journal = ForexPaperActivityJournal(Path(temporary))
        journal.record(_payload(4))
        journal.record(_payload(5, status="PAPER_CYCLE_BLOCKED"))
        journal.record(_payload(6, status="PAPER_CYCLE_BLOCKED"))
        journal.record(_payload(7))

        events = journal.events(limit=10)

        assert [event["kind"] for event in events] == [
            "DATA_BLOCKED",
            "DATA_RECOVERED",
        ]


def test_protection_close_is_healthy_and_does_not_fake_a_recovery() -> None:
    with TemporaryDirectory() as temporary:
        journal = ForexPaperActivityJournal(Path(temporary))
        journal.record(_payload(30))
        journal.record(_payload(
            31,
            action="CLOSE_LONG",
            status="PAPER_PROTECTION_APPLIED",
        ))
        journal.record(_payload(32))

        events = journal.events(limit=10)

        assert [event["kind"] for event in events] == ["POSITION_CLOSED"]
        assert journal.status()["last_health"] == "HEALTHY"


def test_sustained_protection_failure_and_recovery_are_notified_once() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        for cycle in range(40, 42):
            result = ForexPaperActivityJournal(root).record_protection_health(
                _payload(cycle, status="PAPER_PROTECTION_BLOCKED")
            )
            assert result["events_recorded"] == 0
            assert result["attention_required"] is False
        attention = ForexPaperActivityJournal(root).record_protection_health(
            _payload(42, status="PAPER_PROTECTION_BLOCKED")
        )
        repeated = ForexPaperActivityJournal(root).record_protection_health(
            _payload(43, status="PAPER_PROTECTION_BLOCKED")
        )
        recovered = ForexPaperActivityJournal(root).record_protection_health(
            _payload(44, status="NO_PROTECTION_TRIGGER")
        )
        healthy = ForexPaperActivityJournal(root).record_protection_health(
            _payload(45, status="NO_PROTECTION_TRIGGER")
        )

        events = ForexPaperActivityJournal(root).events(limit=10)

        assert attention["events_recorded"] == 1
        assert attention["consecutive_failure_count"] == 3
        assert attention["attention_required"] is True
        assert repeated["events_recorded"] == 0
        assert recovered["events_recorded"] == 1
        assert recovered["consecutive_failure_count"] == 0
        assert healthy["events_recorded"] == 0
        assert [event["kind"] for event in events] == [
            "POSITION_PROTECTION_ATTENTION",
            "POSITION_PROTECTION_RECOVERED",
        ]
        assert all(
            event["origin"] == "PROTECTION_WATCHDOG" for event in events
        )
        feed = ForexPaperActivityFeed(root, settings=_settings())
        first = feed.poll()
        second = feed.poll()
        assert first is not None
        assert first["activity_kind"] == "POSITION_PROTECTION_ATTENTION"
        assert second is not None
        assert second["activity_kind"] == "POSITION_PROTECTION_RECOVERED"
        assert feed.poll() is None


def test_protection_health_rejects_an_unsafe_report_without_state_change() -> None:
    with TemporaryDirectory() as temporary:
        journal = ForexPaperActivityJournal(Path(temporary))
        journal.record_protection_health(
            _payload(46, status="NO_PROTECTION_TRIGGER")
        )
        unsafe = _payload(47, status="PAPER_PROTECTION_BLOCKED")
        unsafe["live_orders_sent"] = True

        result = journal.record_protection_health(unsafe)
        status = journal.status()

        assert result == {
            "status": "INVALID_PROTECTION_HEALTH",
            "events_recorded": 0,
        }
        assert status["last_protection_health"] == "HEALTHY"
        assert status["protection_consecutive_failure_count"] == 0
        assert journal.events(limit=10) == []


def test_existing_ledger_fills_are_history_but_not_replayed_as_alerts() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        path = root / "data" / "trading" / "forex_paper_ledger.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "mode": "FOREX_PAPER_ONLY",
            "fills": [{
                "fill_id": "old-fill",
                "action": "OPEN_SHORT",
                "pair": "USD_CHF",
                "filled_at": "2026-08-21T09:00:00+00:00",
            }],
        }), encoding="utf-8")
        feed = ForexPaperActivityFeed(root, settings=_settings())

        history = feed.history()

        assert len(history) == 1
        assert history[0]["origin"] == "LEDGER_BACKFILL"
        assert history[0]["delivery_status"] == "HISTORIA"
        assert history[0]["delivered"] is True
        assert feed.poll() is None


def test_history_is_bounded_and_reports_dropped_entries() -> None:
    with TemporaryDirectory() as temporary:
        journal = ForexPaperActivityJournal(Path(temporary))
        journal.MAX_EVENTS = 3
        for cycle in range(10, 15):
            journal.record(_payload(cycle, action="OPEN_LONG"))

        events = journal.events(limit=10)
        status = journal.status()

        assert [event["sequence"] for event in events] == [3, 4, 5]
        assert status["event_count"] == 3
        assert status["dropped_event_count"] == 2


def test_history_never_persists_unrelated_payload_secrets() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        payload = _payload(20, action="OPEN_LONG")
        payload["api_key"] = "SHOULD_NOT_BE_STORED"
        ForexPaperActivityJournal(root).record(payload)

        saved = (
            root / "data" / "trading" / "forex_paper_activity_history.json"
        ).read_text(encoding="utf-8")

        assert "SHOULD_NOT_BE_STORED" not in saved
        assert "api_key" not in saved
        assert "broker_orders_sent" not in saved


def test_concurrent_duplicate_records_produce_one_event() -> None:
    with TemporaryDirectory() as temporary:
        journal = ForexPaperActivityJournal(Path(temporary))
        journal.initialize()
        payload = _payload(21, action="OPEN_SHORT")

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(journal.record, (payload, payload)))

        assert sorted(result["status"] for result in results) == [
            "DUPLICATE_CYCLE",
            "RECORDED",
        ]
        assert journal.status()["event_count"] == 1
        assert not journal.lock_path.exists()


def test_corrupted_event_sequence_is_ignored_without_crashing() -> None:
    with TemporaryDirectory() as temporary:
        journal = ForexPaperActivityJournal(Path(temporary))
        journal.store.save({
            "schema_version": 1,
            "mode": "FOREX_PAPER_ONLY",
            "events": [{"sequence": "broken", "message": "ignore"}],
            "recent_cycle_keys": "broken",
        })

        assert journal.events() == []
        assert journal.status()["event_count"] == 0


def test_hidden_runner_records_history_before_printing_result() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "run_forex_paper_cycle.py"
    ).read_text(encoding="utf-8")

    assert "ForexPaperActivityJournal" in source
    assert "activity_history.initialize()" in source
    assert "activity_history.record(result)" in source
    assert source.index("activity_history.record(result)") < source.index(
        "print(json.dumps"
    )


def test_protection_runner_records_an_applied_close_before_printing() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "run_forex_paper_protection.py"
    ).read_text(encoding="utf-8")

    assert "ForexPaperActivityJournal" in source
    assert "record_protection_health(result)" in source
    assert "protection_consecutive_failure_count" in source
    assert 'result.get("status") == "PAPER_PROTECTION_APPLIED"' in source
    assert source.index("ForexPaperActivityJournal") < source.index(
        "print(json.dumps"
    )


def test_new_activity_modules_remain_bounded() -> None:
    root = Path(__file__).resolve().parents[1]
    limits = {
        "app/trading/forex_activity_journal.py": 540,
        "app/trading/forex_activity.py": 260,
        "app/gui/forex_paper_page.py": 380,
    }
    for relative, limit in limits.items():
        assert len((root / relative).read_text(encoding="utf-8").splitlines()) < limit
