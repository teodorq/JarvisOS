from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib

from app.trading.forex_forward_evidence import (
    _content_sha256,
    build_forex_v3_forward_evidence_report,
    verify_forex_v3_forward_evidence_report,
)
from app.trading.forex_v3_shadow import ForexV3ShadowReadiness


UTC = timezone.utc
NOW = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)


class StaticEvidence:
    def __init__(self, report: dict) -> None:
        self.report = deepcopy(report)

    def review(self) -> dict:
        return deepcopy(self.report)


def _empty_report() -> dict:
    return build_forex_v3_forward_evidence_report(
        {
            "schema_version": 1,
            "mode": "FOREX_OBSERVATION_ONLY",
            "observations": [],
        },
        generated_at=NOW,
    )


def _fingerprint(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _complete_report() -> dict:
    report = _empty_report()
    accepted = []
    by_day: dict[str, int] = {}
    for index in range(20):
        observed_at = datetime(
            2026,
            9,
            30,
            8,
            0,
            tzinfo=UTC,
        ) + timedelta(days=index // 7, minutes=15 * (index % 7))
        day = observed_at.date().isoformat()
        by_day[day] = by_day.get(day, 0) + 1
        accepted.append({
            "sequence": index + 1,
            "observation_id": f"shadow-observation-{index:04d}",
            "observation_hash": _fingerprint(f"observation-{index}"),
            "observed_at": observed_at.isoformat(),
            "source_cycle_id": f"shadow-source-cycle-{index:04d}",
            "bars_sha256": _fingerprint(f"bars-{index}"),
            "decision_input_sha256": _fingerprint(f"decision-{index}"),
            "capture_nonce_sha256": _fingerprint(f"nonce-{index}"),
        })
    report.update({
        "status": "FORWARD_OBSERVATION_SAMPLE_COMPLETE",
        "generated_at": datetime(2026, 10, 3, 12, 0, tzinfo=UTC).isoformat(),
        "source_cutoff_sequence": 20,
        "source_head_hash": accepted[-1]["observation_hash"],
        "accepted_cycle_count": 20,
        "accepted_market_day_count": 3,
        "remaining_accepted_cycles": 0,
        "remaining_market_days": 0,
        "observation_sample_complete": True,
        "excluded_cycle_count": 0,
        "invalid_cycle_count": 0,
        "accepted_observations": accepted,
        "accepted_by_market_day": by_day,
        "exclusions": {},
        "invalid_issues": {},
        "evidence_valid": True,
    })
    report["content_sha256"] = _content_sha256(report)
    assert verify_forex_v3_forward_evidence_report(
        report,
        require_complete=True,
    )
    return report


def test_shadow_waits_without_creating_a_ledger(tmp_path) -> None:
    readiness = ForexV3ShadowReadiness(
        tmp_path,
        forward_evidence=StaticEvidence(_empty_report()),
    )

    status = readiness.status()

    assert status["status"] == "WAITING_FOR_FORWARD_SAMPLE"
    assert status["remaining_accepted_cycles"] == 20
    assert status["remaining_market_days"] == 3
    assert status["shadow_initialization_ready"] is False
    assert status["shadow_ledger_initialized"] is False
    assert status["shadow_execution_enabled"] is False
    assert status["current_paper_strategy_changed"] is False
    assert status["paper_orders_sent"] is False
    assert status["live_orders_sent"] is False
    assert not readiness.ledger_path.exists()


def test_blocked_source_report_is_not_treated_as_waiting(tmp_path) -> None:
    report = _empty_report()
    report["source_state_valid"] = False
    report["status"] = "BLOCKED_SOURCE_INVALID"
    report["source_error"] = "missing"
    report["invalid_issues"] = {"SOURCE_STATE_INVALID": 1}
    report["content_sha256"] = _content_sha256(report)
    assert verify_forex_v3_forward_evidence_report(report)

    status = ForexV3ShadowReadiness(
        tmp_path,
        forward_evidence=StaticEvidence(report),
    ).status()

    assert status["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert status["reason"] == "FORWARD_EVIDENCE_SOURCE_INVALID"
    assert status["shadow_initialization_ready"] is False
    assert status["shadow_execution_enabled"] is False


def test_complete_sample_only_arms_manual_shadow_initialization(tmp_path) -> None:
    readiness = ForexV3ShadowReadiness(
        tmp_path,
        forward_evidence=StaticEvidence(_complete_report()),
    )

    status = readiness.status()

    assert status["status"] == "READY_FOR_MANUAL_SHADOW_INITIALIZATION"
    assert status["forward_sample_complete"] is True
    assert status["shadow_initialization_ready"] is True
    assert status["manual_initialization_required"] is True
    assert status["shadow_ledger_initialized"] is False
    assert status["shadow_execution_enabled"] is False
    assert not readiness.ledger_path.exists()


def test_tampered_evidence_and_unexpected_ledger_fail_closed(tmp_path) -> None:
    tampered = _empty_report()
    tampered["accepted_cycle_count"] = 1
    invalid = ForexV3ShadowReadiness(
        tmp_path,
        forward_evidence=StaticEvidence(tampered),
    ).status()
    assert invalid["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert invalid["reason"] == "FORWARD_EVIDENCE_INVALID"
    assert invalid["shadow_execution_enabled"] is False

    readiness = ForexV3ShadowReadiness(
        tmp_path,
        forward_evidence=StaticEvidence(_empty_report()),
    )
    readiness.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    readiness.ledger_path.write_text("{}", encoding="utf-8")
    unexpected = readiness.status()
    assert unexpected["status"] == "BLOCKED_INVALID_FORWARD_EVIDENCE"
    assert unexpected["reason"] == "UNEXPECTED_SHADOW_LEDGER_PRESENT"
    assert readiness.ledger_path.read_text(encoding="utf-8") == "{}"
