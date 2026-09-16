from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from app.trading.forex_candidate_v2 import ForexRegimeCandidatePolicy
from app.trading.forex_forward_evidence import (
    ForexV2ForwardEvidenceReport,
    build_forex_v2_forward_evidence_report,
    expected_candidate_implementation_sha256,
    verify_forex_v2_forward_evidence_report,
)
from app.trading.forex_models import MAJOR_FOREX_PAIRS
from app.trading.forex_observation import ForexObservationJournal
from app.trading.forex_sample_contract import build_forex_paper_sample_contract


UTC = timezone.utc
AFTER_FREEZE = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


def _fingerprint(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _object_fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _assessments(*, retained: bool = False) -> list[dict[str, object]]:
    result = []
    for index, pair in enumerate(MAJOR_FOREX_PAIRS):
        action = "OPEN_LONG" if index == 0 else "WATCH"
        if retained is False and index == 0:
            action = "WAIT"
        result.append({
            "pair": pair.symbol,
            "action": action,
            "reason_codes": [],
        })
    return result


def _record(
    observed_at: datetime,
    *,
    seed: str,
    observation_id: str,
    source_cycle_id: str | None = None,
) -> dict[str, object]:
    policy = ForexRegimeCandidatePolicy()
    sample = build_forex_paper_sample_contract()
    latest = (observed_at - timedelta(minutes=15)).isoformat()
    base_assessments = _assessments(retained=True)
    candidate_assessments = _assessments(retained=False)
    input_sha256 = _fingerprint(seed)
    components = {
        "quote_snapshot_sha256": _fingerprint(f"quotes-{seed}"),
        "context_snapshot_sha256": _fingerprint(f"contexts-{seed}"),
        "position_snapshot_sha256": _fingerprint(f"positions-{seed}"),
        "account_snapshot_sha256": _fingerprint(f"account-{seed}"),
        "diagnostics_snapshot_sha256": _fingerprint(f"diagnostics-{seed}"),
    }
    decision_input_sha256 = _object_fingerprint({
        "captured_at": observed_at.isoformat(),
        "bars_sha256": input_sha256,
        **components,
    })
    return {
        "status": "OBSERVATION_RECORDED",
        "mode": "FOREX_OBSERVATION_ONLY",
        "observation_schema_version": 2,
        "observation_id": observation_id,
        "observed_at": observed_at.isoformat(),
        "captured_at": observed_at.isoformat(),
        "capture_origin": "SCHEDULED_FORWARD",
        "capture_attestation": {
            "kind": "LOCAL_WATCHDOG_ANCESTRY_NONCE_V1",
            "verified": True,
            "trust_level": "BEST_EFFORT_LOCAL_PROCESS",
            "verified_scope": "WATCHDOG_ANCESTRY_AND_NONCE_FORMAT",
            "nonce_sha256": _fingerprint(
                f"nonce-{source_cycle_id or observation_id}"
            ),
            "watchdog_process_id": 1234,
        },
        "source_cycle_id": source_cycle_id or f"source-cycle-{seed}",
        "market_open": True,
        "fully_cross_checked": True,
        "data": {
            "cross_checked_pair_count": len(MAJOR_FOREX_PAIRS),
            "cross_checked_pairs": [
                pair.symbol for pair in MAJOR_FOREX_PAIRS
            ],
        },
        "opening_blocks": [],
        "assessments": base_assessments,
        "proposed_plan": {"instructions": []},
        "source_evidence": {
            "schema_version": 1,
            "timeframe": "M15_CLOSED_BARS",
            "pair_count": len(MAJOR_FOREX_PAIRS),
            "bar_counts": {
                pair.symbol: policy.required_m15_bar_count
                for pair in MAJOR_FOREX_PAIRS
            },
            "latest_bar_open_at": {
                pair.symbol: latest for pair in MAJOR_FOREX_PAIRS
            },
            "latest_bars_closed": True,
            "bars_strictly_ordered": True,
            "independent_source_counts": {
                pair.symbol: 2 for pair in MAJOR_FOREX_PAIRS
            },
            "input_sha256": input_sha256,
            **components,
            "decision_input_sha256": decision_input_sha256,
            "recovery_replay": False,
            "idempotent_replay": False,
        },
        "development_candidate_v2": {
            "status": "FORWARD_OBSERVATION_RECORDED",
            "candidate_id": policy.candidate_id,
            "policy_fingerprint_sha256": policy.fingerprint_sha256,
            "implementation_sha256": (
                expected_candidate_implementation_sha256()
            ),
            "paper_sample_contract_id": sample["contract_id"],
            "paper_sample_contract_fingerprint_sha256": sample[
                "fingerprint_sha256"
            ],
            "forward_eligible": policy.forward_eligible(observed_at),
            "assessments": candidate_assessments,
            "proposed_plan": {"instructions": []},
            "execution": {"status": "NOT_EXECUTED"},
            "automatic_paper_promotion": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        },
        "execution": {"status": "NOT_EXECUTED"},
        "positions_unchanged": True,
        "order_network_access": False,
        "paper_orders_sent": False,
        "live_orders_sent": False,
    }


def _state(tmp_path: Path, *records: dict[str, object]) -> dict[str, object]:
    journal = ForexObservationJournal(tmp_path)
    for record in records:
        journal.record(record)
    return journal.snapshot()


def test_accepts_one_strict_post_freeze_cycle_and_reports_signals(
    tmp_path: Path,
) -> None:
    state = _state(
        tmp_path,
        _record(
            AFTER_FREEZE,
            seed="accepted",
            observation_id="forward-observation-accepted",
        ),
    )

    report = build_forex_v2_forward_evidence_report(
        state,
        generated_at=AFTER_FREEZE + timedelta(hours=1),
    )

    assert report["status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert report["source_state_valid"] is True
    assert report["source_cutoff_sequence"] == 1
    assert len(report["source_head_hash"]) == 64
    assert len(report["content_sha256"]) == 64
    assert report["implementation_sha256"] == (
        expected_candidate_implementation_sha256()
    )
    assert report["accepted_cycle_count"] == 1
    assert report["accepted_market_day_count"] == 1
    assert report["remaining_accepted_cycles"] == 19
    assert report["remaining_market_days"] == 2
    assert report["observation_sample_complete"] is False
    assert report["excluded_cycle_count"] == 0
    assert report["invalid_cycle_count"] == 0
    assert report["signal_comparison"] == {
        "base_entry_signal_count": 1,
        "retained_entry_signal_count": 0,
        "filtered_entry_signal_count": 1,
    }
    assert set(report["accepted_observations"][0]) == {
        "sequence",
        "observation_id",
        "observation_hash",
        "observed_at",
        "source_cycle_id",
        "bars_sha256",
        "decision_input_sha256",
        "capture_nonce_sha256",
    }
    for field in (
        "pnl_included",
        "strategy_performance_validated",
        "automatic_paper_strategy_change",
        "automatic_paper_promotion",
        "automatic_live_promotion",
        "paper_changes_applied",
        "live_changes_applied",
        "paper_orders_sent",
        "live_orders_sent",
        "real_money_access",
    ):
        assert report[field] is False
    assert verify_forex_v2_forward_evidence_report(report) is True
    assert verify_forex_v2_forward_evidence_report(
        report,
        require_complete=True,
    ) is False


def test_forward_flag_is_derived_and_freeze_boundary_is_excluded(
    tmp_path: Path,
) -> None:
    policy = ForexRegimeCandidatePolicy()
    forged = _record(
        policy.frozen_after - timedelta(minutes=15),
        seed="forged-pre-freeze",
        observation_id="forward-observation-forged",
    )
    forged["development_candidate_v2"]["forward_eligible"] = True
    boundary = _record(
        policy.frozen_after,
        seed="freeze-boundary",
        observation_id="forward-observation-boundary",
    )
    state = _state(tmp_path, forged, boundary)

    report = build_forex_v2_forward_evidence_report(state)

    assert report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert report["accepted_cycle_count"] == 0
    assert report["invalid_cycle_count"] == 1
    assert report["invalid_issues"] == {
        "FORWARD_ELIGIBILITY_MISMATCH": 1,
    }
    assert report["excluded_cycle_count"] == 1
    assert report["exclusions"] == {"PRE_FREEZE": 1}


def test_manual_replay_recovery_legacy_and_unqualified_are_excluded(
    tmp_path: Path,
) -> None:
    records = []
    for index, category in enumerate((
        "manual",
        "idempotent",
        "recovery",
        "legacy",
        "blocked",
        "closed",
        "crosscheck",
    )):
        record = _record(
            AFTER_FREEZE + timedelta(minutes=15 * index),
            seed=category,
            observation_id=f"forward-excluded-{category}",
        )
        if category == "manual":
            record["capture_origin"] = "MANUAL"
        elif category == "idempotent":
            record["source_evidence"]["idempotent_replay"] = True
        elif category == "recovery":
            record["source_evidence"]["recovery_replay"] = True
        elif category == "legacy":
            record["observation_schema_version"] = 1
        elif category == "blocked":
            record["status"] = "DATA_BLOCKED"
        elif category == "closed":
            record["market_open"] = False
        elif category == "crosscheck":
            record["fully_cross_checked"] = False
        records.append(record)

    report = build_forex_v2_forward_evidence_report(
        _state(tmp_path, *records)
    )

    assert report["status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert report["accepted_cycle_count"] == 0
    assert report["excluded_cycle_count"] == 7
    assert report["invalid_cycle_count"] == 0
    assert report["exclusions"] == {
        "CROSS_CHECK_INCOMPLETE": 1,
        "DATA_BLOCKED": 1,
        "IDEMPOTENT_REPLAY": 1,
        "LEGACY_SCHEMA": 1,
        "MANUAL_CAPTURE": 1,
        "MARKET_CLOSED": 1,
        "RECOVERY_REPLAY": 1,
    }


def test_input_time_cycle_and_idempotent_replays_never_double_count(
    tmp_path: Path,
) -> None:
    journal = ForexObservationJournal(tmp_path)
    first = _record(
        AFTER_FREEZE,
        seed="same-input",
        observation_id="forward-unique-first",
        source_cycle_id="source-cycle-first",
    )
    journal.record(first)
    replay = journal.record(deepcopy(first))
    assert replay["idempotent_replay"] is True
    same_input = _record(
        AFTER_FREEZE + timedelta(minutes=15),
        seed="same-input",
        observation_id="forward-duplicate-input",
        source_cycle_id="source-cycle-second",
    )
    same_time = _record(
        AFTER_FREEZE,
        seed="different-input",
        observation_id="forward-duplicate-time",
        source_cycle_id="source-cycle-third",
    )
    journal.record(same_input)
    journal.record(same_time)

    report = build_forex_v2_forward_evidence_report(journal.snapshot())

    assert report["source_cutoff_sequence"] == 3
    assert report["accepted_cycle_count"] == 1
    assert report["excluded_cycle_count"] == 2
    assert report["invalid_cycle_count"] == 0
    assert report["exclusions"] == {
        "DUPLICATE_INPUT_REPLAY": 1,
        "DUPLICATE_OBSERVED_AT_REPLAY": 1,
    }


def test_invalid_candidate_contract_is_blocked_and_not_counted(
    tmp_path: Path,
) -> None:
    record = _record(
        AFTER_FREEZE,
        seed="invalid-candidate",
        observation_id="forward-invalid-candidate",
    )
    record["development_candidate_v2"]["implementation_sha256"] = "0" * 64

    report = build_forex_v2_forward_evidence_report(
        _state(tmp_path, record)
    )

    assert report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert report["accepted_cycle_count"] == 0
    assert report["invalid_cycle_count"] == 1
    assert report["invalid_issues"] == {
        "CANDIDATE_IMPLEMENTATION_MISMATCH": 1,
    }
    assert report["evidence_valid"] is False


def test_nonce_is_consumed_even_when_first_cycle_is_invalid(
    tmp_path: Path,
) -> None:
    invalid = _record(
        AFTER_FREEZE,
        seed="nonce-invalid-first",
        observation_id="forward-nonce-invalid-first",
    )
    invalid["development_candidate_v2"]["implementation_sha256"] = "0" * 64
    reused = _record(
        AFTER_FREEZE + timedelta(minutes=15),
        seed="nonce-reused-second",
        observation_id="forward-nonce-reused-second",
    )
    reused["capture_attestation"]["nonce_sha256"] = (
        invalid["capture_attestation"]["nonce_sha256"]
    )

    report = build_forex_v2_forward_evidence_report(
        _state(tmp_path, invalid, reused)
    )

    assert report["accepted_cycle_count"] == 0
    assert report["invalid_issues"] == {
        "CANDIDATE_IMPLEMENTATION_MISMATCH": 1,
    }
    assert report["exclusions"] == {
        "DUPLICATE_CAPTURE_NONCE_REPLAY": 1,
    }


def test_missing_watchdog_attestation_blocks_scheduled_record(
    tmp_path: Path,
) -> None:
    record = _record(
        AFTER_FREEZE,
        seed="missing-attestation",
        observation_id="forward-missing-attestation",
    )
    record.pop("capture_attestation")

    report = build_forex_v2_forward_evidence_report(
        _state(tmp_path, record)
    )

    assert report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert report["accepted_cycle_count"] == 0
    assert report["invalid_issues"] == {
        "CAPTURE_ATTESTATION_INVALID": 1,
    }


def test_missing_full_decision_fingerprint_blocks_scheduled_record(
    tmp_path: Path,
) -> None:
    record = _record(
        AFTER_FREEZE,
        seed="missing-decision-input",
        observation_id="forward-missing-decision-input",
    )
    record["source_evidence"].pop("decision_input_sha256")

    report = build_forex_v2_forward_evidence_report(
        _state(tmp_path, record)
    )

    assert report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert report["accepted_cycle_count"] == 0
    assert report["invalid_issues"] == {
        "SOURCE_DECISION_FINGERPRINT_INVALID": 1,
    }


def test_forged_crosscheck_count_without_seven_unique_pairs_is_blocked(
    tmp_path: Path,
) -> None:
    record = _record(
        AFTER_FREEZE,
        seed="duplicate-crosscheck-pairs",
        observation_id="forward-duplicate-crosscheck-pairs",
    )
    record["data"]["cross_checked_pairs"] = ["EUR_USD"] * 7

    report = build_forex_v2_forward_evidence_report(
        _state(tmp_path, record)
    )

    assert report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert report["accepted_cycle_count"] == 0
    assert report["invalid_issues"] == {
        "CROSS_CHECK_EVIDENCE_INVALID": 1,
    }


def test_malformed_crosscheck_items_fail_closed_without_crashing(
    tmp_path: Path,
) -> None:
    record = _record(
        AFTER_FREEZE,
        seed="malformed-crosscheck-items",
        observation_id="forward-malformed-crosscheck-items",
    )
    record["data"]["cross_checked_pairs"] = [
        {"unexpected": "mapping"},
        *[pair.symbol for pair in MAJOR_FOREX_PAIRS[1:]],
    ]

    report = build_forex_v2_forward_evidence_report(
        _state(tmp_path, record)
    )

    assert report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert report["invalid_issues"] == {
        "CROSS_CHECK_EVIDENCE_INVALID": 1,
    }


def test_decision_fingerprint_must_match_all_recorded_components(
    tmp_path: Path,
) -> None:
    record = _record(
        AFTER_FREEZE,
        seed="mismatched-decision-input",
        observation_id="forward-mismatched-decision-input",
    )
    record["source_evidence"]["quote_snapshot_sha256"] = _fingerprint(
        "different-quotes"
    )

    report = build_forex_v2_forward_evidence_report(
        _state(tmp_path, record)
    )

    assert report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert report["accepted_cycle_count"] == 0
    assert report["invalid_issues"] == {
        "SOURCE_DECISION_FINGERPRINT_MISMATCH": 1,
    }


def test_corrupt_explicit_state_blocks_without_creating_report(
    tmp_path: Path,
) -> None:
    reporter = ForexV2ForwardEvidenceReport(tmp_path)

    report = reporter.refresh({
        "schema_version": 1,
        "mode": "FOREX_OBSERVATION_ONLY",
        "observations": [{"sequence": 1}],
    })

    assert report["status"] == "BLOCKED_SOURCE_INVALID"
    assert report["source_state_valid"] is False
    assert report["strategy_performance_validated"] is False
    assert not reporter.path.exists()


def test_non_finite_sequence_fails_closed_without_crashing(
    tmp_path: Path,
) -> None:
    state = _state(
        tmp_path,
        _record(
            AFTER_FREEZE,
            seed="non-finite-sequence",
            observation_id="forward-non-finite-sequence",
        ),
    )
    state["observations"][0]["sequence"] = float("inf")

    report = build_forex_v2_forward_evidence_report(state)

    assert report["status"] == "BLOCKED_SOURCE_INVALID"
    assert report["source_state_valid"] is False
    assert report["strategy_performance_validated"] is False


def test_retention_boundary_blocks_instead_of_hiding_dropped_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(ForexObservationJournal, "MAX_OBSERVATIONS", 3)
    state = _state(
        tmp_path,
        *(
            _record(
                AFTER_FREEZE + timedelta(minutes=15 * index),
                seed=f"retention-{index}",
                observation_id=f"forward-retention-{index:04d}",
            )
            for index in range(3)
        ),
    )

    report = build_forex_v2_forward_evidence_report(state)

    assert report["status"] == "BLOCKED_SOURCE_INVALID"
    assert "RETENTION_BOUNDARY" in report["source_error"].upper()
    assert report["observation_sample_complete"] is False
    assert report["strategy_performance_validated"] is False


def test_strict_load_failure_does_not_overwrite_last_good_report(
    tmp_path: Path,
) -> None:
    journal = ForexObservationJournal(tmp_path)
    journal.record(_record(
        AFTER_FREEZE,
        seed="persistent",
        observation_id="forward-persistent-good",
    ))
    reporter = ForexV2ForwardEvidenceReport(tmp_path)
    first = reporter.refresh(generated_at=AFTER_FREEZE + timedelta(hours=1))
    previous = reporter.path.read_bytes()
    reporter.observation_path.write_text("{broken", encoding="utf-8")

    blocked = reporter.refresh(
        generated_at=AFTER_FREEZE + timedelta(hours=2)
    )

    assert first["status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert blocked["status"] == "BLOCKED_SOURCE_INVALID"
    assert reporter.path.read_bytes() == previous


def test_deeply_nested_source_fails_closed_without_crashing(
    tmp_path: Path,
) -> None:
    reporter = ForexV2ForwardEvidenceReport(tmp_path)
    reporter.observation_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        '{"schema_version":1,"mode":"FOREX_OBSERVATION_ONLY",'
        '"observations":[],"unexpected":'
        + "[" * 1_500
        + "0"
        + "]" * 1_500
        + "}"
    )
    reporter.observation_path.write_text(payload, encoding="utf-8")

    report = reporter.refresh(generated_at=AFTER_FREEZE + timedelta(hours=1))

    assert report["status"] == "BLOCKED_SOURCE_INVALID"
    assert report["source_state_valid"] is False
    assert report["strategy_performance_validated"] is False
    assert not reporter.path.exists()


def test_persistence_failure_fails_closed_and_preserves_last_good_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    journal = ForexObservationJournal(tmp_path / "source")
    journal.record(_record(
        AFTER_FREEZE,
        seed="persistence-first",
        observation_id="forward-persistence-first",
    ))
    older_state = journal.snapshot()
    journal.record(_record(
        AFTER_FREEZE + timedelta(minutes=15),
        seed="persistence-second",
        observation_id="forward-persistence-second",
    ))
    newer_state = journal.snapshot()
    reporter = ForexV2ForwardEvidenceReport(tmp_path / "report")
    first = reporter.refresh(
        older_state,
        generated_at=AFTER_FREEZE + timedelta(hours=1),
    )
    saved = reporter.path.read_bytes()

    def fail_write(_report: object) -> None:
        raise OSError("simulated disk failure")

    monkeypatch.setattr(reporter, "_write_atomic", fail_write)
    blocked = reporter.refresh(
        newer_state,
        generated_at=AFTER_FREEZE + timedelta(hours=2),
    )

    assert first["status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert blocked["status"] == "BLOCKED_SOURCE_INVALID"
    assert "REPORT_PERSISTENCE_FAILED" in blocked["source_error"].upper()
    assert blocked["strategy_performance_validated"] is False
    assert blocked["paper_orders_sent"] is False
    assert blocked["live_orders_sent"] is False
    assert reporter.path.read_bytes() == saved


def test_exact_state_and_observation_contract_types_are_required(
    tmp_path: Path,
) -> None:
    valid_state = _state(
        tmp_path / "source",
        _record(
            AFTER_FREEZE,
            seed="exact-types",
            observation_id="forward-exact-types",
        ),
    )
    invalid_state_schema = deepcopy(valid_state)
    invalid_state_schema["schema_version"] = True

    blocked_state = build_forex_v2_forward_evidence_report(
        invalid_state_schema,
        generated_at=AFTER_FREEZE + timedelta(hours=1),
    )

    assert blocked_state["status"] == "BLOCKED_SOURCE_INVALID"
    assert blocked_state["source_state_valid"] is False

    mutations = (
        ("OBSERVATION_MODE_INVALID", lambda item: item.__setitem__("mode", None)),
        (
            "OBSERVATION_ID_INVALID",
            lambda item: item.__setitem__("observation_id", None),
        ),
        (
            "SOURCE_SCHEMA_INVALID",
            lambda item: item["source_evidence"].__setitem__(
                "schema_version", True
            ),
        ),
    )
    for expected_issue, mutate in mutations:
        state = deepcopy(valid_state)
        item = state["observations"][0]
        mutate(item)
        item["observation_hash"] = ForexObservationJournal._hash(item)

        report = build_forex_v2_forward_evidence_report(
            state,
            generated_at=AFTER_FREEZE + timedelta(hours=1),
        )

        assert report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
        assert report["invalid_issues"].get(expected_issue) == 1
        assert report["strategy_performance_validated"] is False


def test_content_hash_is_stable_for_the_same_source_cutoff(
    tmp_path: Path,
) -> None:
    state = _state(
        tmp_path,
        _record(
            AFTER_FREEZE,
            seed="stable-hash",
            observation_id="forward-stable-hash",
        ),
    )

    first = build_forex_v2_forward_evidence_report(
        state,
        generated_at=AFTER_FREEZE + timedelta(hours=1),
    )
    second = build_forex_v2_forward_evidence_report(
        state,
        generated_at=AFTER_FREEZE + timedelta(hours=2),
    )

    assert first["generated_at"] != second["generated_at"]
    assert first["content_sha256"] == second["content_sha256"]


def test_older_refresh_cannot_replace_a_newer_persisted_report(
    tmp_path: Path,
) -> None:
    journal = ForexObservationJournal(tmp_path / "source")
    journal.record(_record(
        AFTER_FREEZE,
        seed="monotonic-first",
        observation_id="forward-monotonic-first",
    ))
    older_state = journal.snapshot()
    journal.record(_record(
        AFTER_FREEZE + timedelta(minutes=15),
        seed="monotonic-second",
        observation_id="forward-monotonic-second",
    ))
    newer_state = journal.snapshot()
    reporter = ForexV2ForwardEvidenceReport(tmp_path / "report")
    newer = reporter.refresh(
        newer_state,
        generated_at=AFTER_FREEZE + timedelta(hours=1),
    )
    saved = reporter.path.read_bytes()

    regressed = reporter.refresh(
        older_state,
        generated_at=AFTER_FREEZE + timedelta(hours=2),
    )

    assert newer["source_cutoff_sequence"] == 2
    assert regressed["status"] == "BLOCKED_SOURCE_INVALID"
    assert "SOURCE_CUTOFF_REGRESSED" in regressed["source_error"].upper()
    assert reporter.path.read_bytes() == saved


def test_equal_cutoff_with_different_head_is_not_persisted(
    tmp_path: Path,
) -> None:
    first_state = _state(
        tmp_path / "first",
        _record(
            AFTER_FREEZE,
            seed="cutoff-first",
            observation_id="forward-cutoff-first",
        ),
    )
    conflicting_state = _state(
        tmp_path / "second",
        _record(
            AFTER_FREEZE,
            seed="cutoff-conflict",
            observation_id="forward-cutoff-conflict",
        ),
    )
    reporter = ForexV2ForwardEvidenceReport(tmp_path / "report")
    reporter.refresh(
        first_state,
        generated_at=AFTER_FREEZE + timedelta(hours=1),
    )
    saved = reporter.path.read_bytes()

    conflict = reporter.refresh(
        conflicting_state,
        generated_at=AFTER_FREEZE + timedelta(hours=2),
    )

    assert conflict["status"] == "BLOCKED_SOURCE_INVALID"
    assert "SOURCE_CUTOFF_CONFLICT" in conflict["source_error"].upper()
    assert reporter.path.read_bytes() == saved


def test_higher_cutoff_from_an_independent_chain_is_not_persisted(
    tmp_path: Path,
) -> None:
    first_state = _state(
        tmp_path / "first",
        _record(
            AFTER_FREEZE,
            seed="ancestry-first-1",
            observation_id="forward-ancestry-first-0001",
        ),
        _record(
            AFTER_FREEZE + timedelta(minutes=15),
            seed="ancestry-first-2",
            observation_id="forward-ancestry-first-0002",
        ),
    )
    independent_state = _state(
        tmp_path / "independent",
        _record(
            AFTER_FREEZE,
            seed="ancestry-other-1",
            observation_id="forward-ancestry-other-0001",
        ),
        _record(
            AFTER_FREEZE + timedelta(minutes=15),
            seed="ancestry-other-2",
            observation_id="forward-ancestry-other-0002",
        ),
        _record(
            AFTER_FREEZE + timedelta(minutes=30),
            seed="ancestry-other-3",
            observation_id="forward-ancestry-other-0003",
        ),
    )
    reporter = ForexV2ForwardEvidenceReport(tmp_path / "report")
    reporter.refresh(
        first_state,
        generated_at=AFTER_FREEZE + timedelta(hours=1),
    )
    saved = reporter.path.read_bytes()

    conflict = reporter.refresh(
        independent_state,
        generated_at=AFTER_FREEZE + timedelta(hours=2),
    )

    assert conflict["status"] == "BLOCKED_SOURCE_INVALID"
    assert "SOURCE_CHAIN_ANCESTRY_CONFLICT" in conflict["source_error"].upper()
    assert conflict["strategy_performance_validated"] is False
    assert reporter.path.read_bytes() == saved


def test_equal_source_cannot_hide_a_changed_report_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = _state(
        tmp_path / "source",
        _record(
            AFTER_FREEZE,
            seed="content-contract",
            observation_id="forward-content-contract",
        ),
    )
    reporter = ForexV2ForwardEvidenceReport(tmp_path / "report")
    first = reporter.refresh(
        state,
        generated_at=AFTER_FREEZE + timedelta(hours=1),
    )
    saved = reporter.path.read_bytes()
    monkeypatch.setattr(
        "app.trading.forex_forward_evidence."
        "expected_candidate_implementation_sha256",
        lambda: "f" * 64,
    )

    conflict = reporter.refresh(
        state,
        generated_at=AFTER_FREEZE + timedelta(hours=2),
    )

    assert first["status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert conflict["status"] == "BLOCKED_SOURCE_INVALID"
    assert "REPORT_CONTENT_CONFLICT" in conflict["source_error"].upper()
    assert reporter.path.read_bytes() == saved


def test_future_timestamp_blocks_and_complete_sample_needs_three_days(
    tmp_path: Path,
) -> None:
    future = _record(
        AFTER_FREEZE + timedelta(days=4),
        seed="future",
        observation_id="forward-observation-future",
    )
    future_report = build_forex_v2_forward_evidence_report(
        _state(tmp_path / "future", future),
        generated_at=AFTER_FREEZE,
    )
    assert future_report["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert future_report["invalid_issues"] == {
        "OBSERVATION_TIME_IN_FUTURE": 1,
    }

    records = []
    market_day_offsets = (0, 3, 4)
    for index in range(20):
        day = market_day_offsets[index // 7]
        minute = (index % 7) * 15
        observed_at = AFTER_FREEZE + timedelta(days=day, minutes=minute)
        records.append(_record(
            observed_at,
            seed=f"complete-{index}",
            observation_id=f"forward-complete-{index:04d}",
        ))
    complete = build_forex_v2_forward_evidence_report(
        _state(tmp_path / "complete", *records),
        generated_at=AFTER_FREEZE + timedelta(days=5),
    )
    assert complete["status"] == "FORWARD_OBSERVATION_SAMPLE_COMPLETE"
    assert complete["accepted_cycle_count"] == 20
    assert complete["accepted_market_day_count"] == 3
    assert complete["observation_sample_complete"] is True
    assert complete["strategy_performance_validated"] is False
    assert verify_forex_v2_forward_evidence_report(complete) is True
    assert verify_forex_v2_forward_evidence_report(
        complete,
        require_complete=True,
    ) is True

    forged = deepcopy(complete)
    forged["real_money_access"] = True
    forged["content_sha256"] = _object_fingerprint({
        key: value
        for key, value in forged.items()
        if key not in {"generated_at", "content_sha256"}
    })
    assert verify_forex_v2_forward_evidence_report(
        forged,
        require_complete=True,
    ) is False
