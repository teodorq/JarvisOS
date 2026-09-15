"""Strict, persistent forward-only signal evidence for frozen Forex V2."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Mapping

from app.core.exclusive_file_lock import exclusive_file_lock
from app.core.project_paths import resolve_project_root
from app.trading import forex_observation as observation_module
from app.trading.forex_candidate_v2 import (
    ForexRegimeCandidatePolicy,
    ForexRegimeFilteredScanner,
)
from app.trading.forex_models import ForexBar, MAJOR_FOREX_PAIRS
from app.trading.forex_observation import ForexObservationJournal
from app.trading.forex_sample_contract import build_forex_paper_sample_contract
from app.trading.forex_scanner import ForexMarketScanner
from app.trading.models import TradingValidationError, aware_utc


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
_EXPECTED_PAIRS = frozenset(pair.symbol for pair in MAJOR_FOREX_PAIRS)
_ALLOWED_ACTIONS = frozenset({
    "WAIT",
    "WATCH",
    "OPEN_LONG",
    "OPEN_SHORT",
    "CLOSE_LONG",
    "CLOSE_SHORT",
})
_NON_FORWARD_ORIGINS = {
    "MANUAL": "MANUAL_CAPTURE",
    "STARTUP_RECOVERY": "RECOVERY_CAPTURE",
    "RECOVERY": "RECOVERY_CAPTURE",
    "REPLAY": "REPLAY_CAPTURE",
    "IDEMPOTENT_REPLAY": "REPLAY_CAPTURE",
    "LEDGER_BACKFILL": "LEGACY_BACKFILL",
}
_MISSING = object()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _content_sha256(report: Mapping[str, Any]) -> str:
    return _canonical_sha256({
        key: value
        for key, value in report.items()
        if key not in {"generated_at", "content_sha256"}
    })


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TradingValidationError(
            f"forex_forward_evidence: invalid_{field}"
        )
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise TradingValidationError(
            f"forex_forward_evidence: invalid_{field}"
        ) from error
    return aware_utc(parsed, field)


def _fallback_candidate_implementation_sha256() -> str:
    """Match the observation module's public fingerprint during migration."""
    classes = (ForexRegimeFilteredScanner, ForexMarketScanner, ForexBar)
    module_names = sorted({item.__module__ for item in classes})
    digest = hashlib.sha256()
    for module_name in module_names:
        module = sys.modules.get(module_name)
        raw_path = getattr(module, "__file__", None)
        if not raw_path:
            raise TradingValidationError(
                "forex_forward_evidence: implementation_source_unavailable"
            )
        try:
            source = Path(raw_path).read_bytes().replace(b"\r\n", b"\n")
        except OSError as error:
            raise TradingValidationError(
                "forex_forward_evidence: implementation_source_unavailable"
            ) from error
        digest.update(module_name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source)
        digest.update(b"\0")
    return digest.hexdigest()


def expected_candidate_implementation_sha256() -> str:
    """Return the implementation identity written by observation schema 2."""
    factory = getattr(
        observation_module,
        "forex_candidate_implementation_sha256",
        None,
    )
    value = factory() if callable(factory) else _fallback_candidate_implementation_sha256()
    selected = str(value)
    if not _SHA256.fullmatch(selected):
        raise TradingValidationError(
            "forex_forward_evidence: invalid_implementation_fingerprint"
        )
    return selected


def _assessment_sets(
    value: object,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]] | None:
    if not isinstance(value, (list, tuple)) or len(value) != len(_EXPECTED_PAIRS):
        return None
    names: list[str] = []
    entries: set[tuple[str, str]] = set()
    exits: set[tuple[str, str]] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            return None
        pair = str(raw.get("pair", ""))
        action = str(raw.get("action", ""))
        if pair not in _EXPECTED_PAIRS or action not in _ALLOWED_ACTIONS:
            return None
        names.append(pair)
        if action.startswith("OPEN_"):
            entries.add((pair, action))
        elif action.startswith("CLOSE_"):
            exits.add((pair, action))
    if len(set(names)) != len(_EXPECTED_PAIRS) or set(names) != _EXPECTED_PAIRS:
        return None
    return entries, exits


def _source_evidence_issues(
    value: object,
    *,
    observed_at: datetime,
    captured_at: datetime,
    required_bar_count: int,
) -> tuple[list[str], str, str]:
    if not isinstance(value, Mapping):
        return ["SOURCE_EVIDENCE_MISSING"], "", ""
    source = dict(value)
    issues: list[str] = []
    if (
        type(source.get("schema_version")) is not int
        or source.get("schema_version") != 1
    ):
        issues.append("SOURCE_SCHEMA_INVALID")
    if source.get("timeframe") != "M15_CLOSED_BARS":
        issues.append("SOURCE_TIMEFRAME_INVALID")
    if source.get("pair_count") != len(_EXPECTED_PAIRS):
        issues.append("SOURCE_PAIR_COUNT_INVALID")
    if source.get("latest_bars_closed") is not True:
        issues.append("SOURCE_OPEN_BAR_DETECTED")
    if source.get("bars_strictly_ordered") is not True:
        issues.append("SOURCE_BAR_ORDER_INVALID")
    if source.get("recovery_replay") is not False:
        issues.append("SOURCE_RECOVERY_REPLAY_FLAG_INVALID")
    if source.get("idempotent_replay") is not False:
        issues.append("SOURCE_IDEMPOTENT_REPLAY_FLAG_INVALID")
    input_sha256 = str(source.get("input_sha256", ""))
    if not _SHA256.fullmatch(input_sha256):
        issues.append("SOURCE_INPUT_FINGERPRINT_INVALID")
    decision_input_sha256 = str(source.get("decision_input_sha256", ""))
    if not _SHA256.fullmatch(decision_input_sha256):
        issues.append("SOURCE_DECISION_FINGERPRINT_INVALID")
    component_fields = (
        "quote_snapshot_sha256",
        "context_snapshot_sha256",
        "position_snapshot_sha256",
        "account_snapshot_sha256",
        "diagnostics_snapshot_sha256",
    )
    for field in component_fields:
        if not _SHA256.fullmatch(str(source.get(field, ""))):
            issues.append("SOURCE_COMPONENT_FINGERPRINT_INVALID")
    if (
        _SHA256.fullmatch(input_sha256)
        and all(
            _SHA256.fullmatch(str(source.get(field, "")))
            for field in component_fields
        )
        and _SHA256.fullmatch(decision_input_sha256)
        and decision_input_sha256 != _canonical_sha256({
            "captured_at": captured_at.isoformat(),
            "bars_sha256": input_sha256,
            **{
                field: str(source[field])
                for field in component_fields
            },
        })
    ):
        issues.append("SOURCE_DECISION_FINGERPRINT_MISMATCH")

    raw_counts = source.get("bar_counts")
    counts = dict(raw_counts) if isinstance(raw_counts, Mapping) else {}
    if set(counts) != _EXPECTED_PAIRS or any(
        type(counts.get(pair)) is not int
        or int(counts[pair]) < required_bar_count
        for pair in _EXPECTED_PAIRS
    ):
        issues.append("SOURCE_BAR_COUNTS_INVALID")

    raw_source_counts = source.get("independent_source_counts")
    source_counts = (
        dict(raw_source_counts)
        if isinstance(raw_source_counts, Mapping)
        else {}
    )
    if set(source_counts) != _EXPECTED_PAIRS or any(
        type(source_counts.get(pair)) is not int
        or int(source_counts[pair]) < 2
        for pair in _EXPECTED_PAIRS
    ):
        issues.append("SOURCE_INDEPENDENT_CROSSCHECK_INVALID")

    raw_latest = source.get("latest_bar_open_at")
    latest = dict(raw_latest) if isinstance(raw_latest, Mapping) else {}
    if set(latest) != _EXPECTED_PAIRS:
        issues.append("SOURCE_LATEST_BAR_COVERAGE_INVALID")
    else:
        for pair in sorted(_EXPECTED_PAIRS):
            try:
                opened_at = _timestamp(latest[pair], "latest_bar_open_at")
            except TradingValidationError:
                issues.append("SOURCE_LATEST_BAR_TIME_INVALID")
                break
            if opened_at + timedelta(minutes=15) > observed_at:
                issues.append("SOURCE_LATEST_BAR_NOT_CLOSED")
                break
    return sorted(set(issues)), input_sha256, decision_input_sha256


def _candidate_contract_issues(
    observation: Mapping[str, Any],
    *,
    expected_implementation_sha256: str,
) -> tuple[list[str], dict[str, int]]:
    policy = ForexRegimeCandidatePolicy()
    sample = build_forex_paper_sample_contract()
    raw_candidate = observation.get("development_candidate_v2")
    if not isinstance(raw_candidate, Mapping):
        return ["CANDIDATE_PAYLOAD_MISSING"], {}
    candidate = dict(raw_candidate)
    issues: list[str] = []
    for invalid, code in (
        (
            candidate.get("status") != "FORWARD_OBSERVATION_RECORDED",
            "CANDIDATE_STATUS_INVALID",
        ),
        (
            candidate.get("candidate_id") != policy.candidate_id,
            "CANDIDATE_ID_MISMATCH",
        ),
        (
            candidate.get("policy_fingerprint_sha256")
            != policy.fingerprint_sha256,
            "CANDIDATE_POLICY_FINGERPRINT_MISMATCH",
        ),
        (
            candidate.get("implementation_sha256")
            != expected_implementation_sha256,
            "CANDIDATE_IMPLEMENTATION_MISMATCH",
        ),
        (
            candidate.get("paper_sample_contract_id")
            != sample["contract_id"],
            "PAPER_SAMPLE_CONTRACT_ID_MISMATCH",
        ),
        (
            candidate.get("paper_sample_contract_fingerprint_sha256")
            != sample["fingerprint_sha256"],
            "PAPER_SAMPLE_CONTRACT_FINGERPRINT_MISMATCH",
        ),
        (
            candidate.get("automatic_paper_promotion") is not False,
            "CANDIDATE_PROMOTION_FLAG_INVALID",
        ),
        (
            candidate.get("paper_orders_sent") is not False,
            "CANDIDATE_PAPER_ORDER_FLAG_INVALID",
        ),
        (
            candidate.get("live_orders_sent") is not False,
            "CANDIDATE_LIVE_ORDER_FLAG_INVALID",
        ),
    ):
        if invalid:
            issues.append(code)
    execution = candidate.get("execution")
    if not isinstance(execution, Mapping) or execution.get("status") != "NOT_EXECUTED":
        issues.append("CANDIDATE_EXECUTION_CONTRACT_INVALID")

    base_sets = _assessment_sets(observation.get("assessments"))
    candidate_sets = _assessment_sets(candidate.get("assessments"))
    if base_sets is None:
        issues.append("BASE_PAIR_COVERAGE_INVALID")
    if candidate_sets is None:
        issues.append("CANDIDATE_PAIR_COVERAGE_INVALID")
    if base_sets is None or candidate_sets is None:
        return sorted(set(issues)), {}
    base_entries, base_exits = base_sets
    candidate_entries, candidate_exits = candidate_sets
    if candidate_entries - base_entries:
        issues.append("CANDIDATE_ENTRY_NOT_SUBSET_OF_BASE")
    if candidate_exits != base_exits:
        issues.append("CANDIDATE_EXIT_PARITY_INVALID")
    return sorted(set(issues)), {
        "base_entry_signal_count": len(base_entries),
        "retained_entry_signal_count": len(candidate_entries),
        "filtered_entry_signal_count": len(base_entries - candidate_entries),
    }


def _observation_contract_issues(
    observation: Mapping[str, Any],
    *,
    observed_at: datetime,
    expected_implementation_sha256: str,
) -> tuple[list[str], str, str, str, dict[str, int]]:
    issues: list[str] = []
    if observation.get("mode") != "FOREX_OBSERVATION_ONLY":
        issues.append("OBSERVATION_MODE_INVALID")
    observation_id = observation.get("observation_id")
    if (
        not isinstance(observation_id, str)
        or not _IDENTIFIER.fullmatch(observation_id)
    ):
        issues.append("OBSERVATION_ID_INVALID")
    raw_attestation = observation.get("capture_attestation")
    attestation = (
        dict(raw_attestation) if isinstance(raw_attestation, Mapping) else {}
    )
    nonce_sha256 = str(attestation.get("nonce_sha256", ""))
    if (
        attestation.get("kind") != "LOCAL_WATCHDOG_ANCESTRY_NONCE_V1"
        or attestation.get("verified") is not True
        or attestation.get("trust_level") != "BEST_EFFORT_LOCAL_PROCESS"
        or attestation.get("verified_scope")
        != "WATCHDOG_ANCESTRY_AND_NONCE_FORMAT"
        or not _SHA256.fullmatch(nonce_sha256)
        or type(attestation.get("watchdog_process_id")) is not int
        or int(attestation["watchdog_process_id"]) <= 0
    ):
        issues.append("CAPTURE_ATTESTATION_INVALID")
    try:
        captured_at = _timestamp(observation.get("captured_at"), "captured_at")
    except TradingValidationError:
        captured_at = observed_at
        issues.append("CAPTURE_TIME_INVALID")
    else:
        delay = (captured_at - observed_at).total_seconds()
        if delay < 0 or delay > 300:
            issues.append("CAPTURE_TIME_NOT_FORWARD")

    raw_source_cycle_id = observation.get("source_cycle_id")
    source_cycle_id = (
        raw_source_cycle_id if isinstance(raw_source_cycle_id, str) else ""
    )
    if not _IDENTIFIER.fullmatch(source_cycle_id):
        issues.append("SOURCE_CYCLE_ID_INVALID")
    for invalid, code in (
        (observation.get("positions_unchanged") is not True, "POSITION_STATE_CHANGED"),
        (observation.get("order_network_access") is not False, "ORDER_NETWORK_FLAG_INVALID"),
        (observation.get("paper_orders_sent") is not False, "PAPER_ORDER_FLAG_INVALID"),
        (observation.get("live_orders_sent") is not False, "LIVE_ORDER_FLAG_INVALID"),
    ):
        if invalid:
            issues.append(code)
    raw_data = observation.get("data")
    data = dict(raw_data) if isinstance(raw_data, Mapping) else {}
    raw_cross_checked = data.get("cross_checked_pairs")
    cross_checked = (
        list(raw_cross_checked)
        if isinstance(raw_cross_checked, (list, tuple))
        else []
    )
    if (
        len(cross_checked) != len(_EXPECTED_PAIRS)
        or any(not isinstance(item, str) for item in cross_checked)
        or (
            all(isinstance(item, str) for item in cross_checked)
            and set(cross_checked) != _EXPECTED_PAIRS
        )
        or data.get("cross_checked_pair_count") != len(_EXPECTED_PAIRS)
    ):
        issues.append("CROSS_CHECK_EVIDENCE_INVALID")
    execution = observation.get("execution")
    if not isinstance(execution, Mapping) or execution.get("status") != "NOT_EXECUTED":
        issues.append("OBSERVATION_EXECUTION_CONTRACT_INVALID")

    source_issues, input_sha256, decision_input_sha256 = (
        _source_evidence_issues(
        observation.get("source_evidence"),
        observed_at=observed_at,
        captured_at=captured_at,
        required_bar_count=ForexRegimeCandidatePolicy().required_m15_bar_count,
        )
    )
    candidate_issues, signals = _candidate_contract_issues(
        observation,
        expected_implementation_sha256=expected_implementation_sha256,
    )
    return (
        sorted(set(issues + source_issues + candidate_issues)),
        input_sha256,
        decision_input_sha256,
        nonce_sha256,
        signals,
    )


def _safety_contract() -> dict[str, bool]:
    return {
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


def _blocked_source_report(
    generated_at: datetime,
    reason: str,
    *,
    implementation_sha256: str = "",
) -> dict[str, Any]:
    policy = ForexRegimeCandidatePolicy()
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "BLOCKED_SOURCE_INVALID",
        "mode": "FOREX_V2_FORWARD_SIGNAL_EVIDENCE_ONLY",
        "generated_at": generated_at.isoformat(),
        "source_state_valid": False,
        "source_error": str(reason)[:160],
        "source_cutoff_sequence": 0,
        "source_head_hash": "",
        "candidate_id": policy.candidate_id,
        "frozen_after": policy.frozen_after.isoformat(),
        "policy_fingerprint_sha256": policy.fingerprint_sha256,
        "implementation_sha256": implementation_sha256,
        "accepted_cycle_count": 0,
        "accepted_market_day_count": 0,
        "minimum_accepted_cycle_count": (
            ForexObservationJournal.MINIMUM_MARKET_OPEN_OBSERVATIONS
        ),
        "minimum_market_day_count": ForexObservationJournal.MINIMUM_MARKET_DAYS,
        "remaining_accepted_cycles": (
            ForexObservationJournal.MINIMUM_MARKET_OPEN_OBSERVATIONS
        ),
        "remaining_market_days": ForexObservationJournal.MINIMUM_MARKET_DAYS,
        "observation_sample_complete": False,
        "excluded_cycle_count": 0,
        "invalid_cycle_count": 0,
        "accepted_observations": [],
        "accepted_by_market_day": {},
        "exclusions": {},
        "invalid_issues": {"SOURCE_STATE_INVALID": 1},
        "signal_comparison": {
            "base_entry_signal_count": 0,
            "retained_entry_signal_count": 0,
            "filtered_entry_signal_count": 0,
        },
        "evidence_valid": False,
        **_safety_contract(),
    }
    report["content_sha256"] = _content_sha256(report)
    return report


def build_forex_v2_forward_evidence_report(
    observation_state: object,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a deterministic signal report from one strict journal cutoff."""
    selected_now = aware_utc(generated_at or datetime.now(timezone.utc), "generated_at")
    try:
        implementation_sha256 = expected_candidate_implementation_sha256()
    except TradingValidationError as error:
        return _blocked_source_report(selected_now, str(error))
    if not isinstance(observation_state, Mapping):
        return _blocked_source_report(
            selected_now,
            "forex_forward_evidence: state_mapping_required",
            implementation_sha256=implementation_sha256,
        )
    state = dict(observation_state)
    raw_observations = state.get("observations")
    state_valid = bool(
        type(state.get("schema_version")) is int
        and state.get("schema_version") == 1
        and state.get("mode") == "FOREX_OBSERVATION_ONLY"
        and set(state) == {"schema_version", "mode", "observations"}
        and isinstance(raw_observations, list)
        and len(raw_observations) <= ForexObservationJournal.MAX_OBSERVATIONS
        and all(isinstance(item, Mapping) for item in raw_observations or [])
    )
    try:
        state_valid = state_valid and ForexObservationJournal.verify(state)
    except (
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
        MemoryError,
        TradingValidationError,
    ):
        state_valid = False
    if not state_valid:
        return _blocked_source_report(
            selected_now,
            "forex_forward_evidence: observation_audit_invalid",
            implementation_sha256=implementation_sha256,
        )
    if len(raw_observations) >= ForexObservationJournal.MAX_OBSERVATIONS:
        return _blocked_source_report(
            selected_now,
            "forex_forward_evidence: observation_history_retention_boundary",
            implementation_sha256=implementation_sha256,
        )

    observations = [dict(item) for item in raw_observations]
    policy = ForexRegimeCandidatePolicy()
    exclusions: Counter[str] = Counter()
    invalid_issues: Counter[str] = Counter()
    excluded_cycle_count = 0
    invalid_cycle_count = 0
    accepted: list[dict[str, Any]] = []
    signal_totals: Counter[str] = Counter()
    seen_inputs: set[str] = set()
    seen_times: set[str] = set()
    seen_source_cycles: set[str] = set()
    seen_capture_nonces: set[str] = set()
    accepted_market_days: Counter[str] = Counter()
    latest_accepted_at: datetime | None = None

    def exclude(*codes: str) -> None:
        nonlocal excluded_cycle_count
        excluded_cycle_count += 1
        exclusions.update(codes)

    def invalidate(*codes: str) -> None:
        nonlocal invalid_cycle_count
        invalid_cycle_count += 1
        invalid_issues.update(codes)

    for observation in observations:
        if observation.get("observation_schema_version") != 2:
            exclude("LEGACY_SCHEMA")
            continue
        status = str(observation.get("status", ""))
        origin = str(observation.get("capture_origin", ""))
        raw_attestation = observation.get("capture_attestation")
        attestation = (
            dict(raw_attestation)
            if isinstance(raw_attestation, Mapping)
            else {}
        )
        declared_nonce = str(attestation.get("nonce_sha256", ""))
        if origin == "SCHEDULED_FORWARD" and _SHA256.fullmatch(
            declared_nonce
        ):
            if declared_nonce in seen_capture_nonces:
                exclude("DUPLICATE_CAPTURE_NONCE_REPLAY")
                continue
            seen_capture_nonces.add(declared_nonce)
        raw_source_evidence = observation.get("source_evidence")
        source_evidence = (
            dict(raw_source_evidence)
            if isinstance(raw_source_evidence, Mapping)
            else {}
        )
        if source_evidence.get("idempotent_replay") is True:
            exclude("IDEMPOTENT_REPLAY")
            continue
        if source_evidence.get("recovery_replay") is True:
            exclude("RECOVERY_REPLAY")
            continue
        if origin != "SCHEDULED_FORWARD":
            exclude(_NON_FORWARD_ORIGINS.get(
                origin,
                "UNSUPPORTED_CAPTURE_ORIGIN",
            ))
            continue
        if status == "DATA_BLOCKED":
            exclude("DATA_BLOCKED")
            continue
        if status != "OBSERVATION_RECORDED":
            invalidate("OBSERVATION_STATUS_INVALID")
            continue
        try:
            observed_at = _timestamp(observation.get("observed_at"), "observed_at")
        except TradingValidationError:
            invalidate("OBSERVATION_TIME_INVALID")
            continue
        if observed_at > selected_now:
            invalidate("OBSERVATION_TIME_IN_FUTURE")
            continue
        raw_candidate = observation.get("development_candidate_v2")
        candidate = dict(raw_candidate) if isinstance(raw_candidate, Mapping) else {}
        calculated_forward = policy.forward_eligible(observed_at)
        declared_forward = candidate.get("forward_eligible")
        if declared_forward is not calculated_forward:
            invalidate("FORWARD_ELIGIBILITY_MISMATCH")
            continue
        if not calculated_forward:
            exclude("PRE_FREEZE")
            continue
        if observation.get("market_open") is not True:
            exclude("MARKET_CLOSED")
            continue
        if observation.get("fully_cross_checked") is not True:
            exclude("CROSS_CHECK_INCOMPLETE")
            continue

        (
            issues,
            input_sha256,
            decision_input_sha256,
            nonce_sha256,
            signals,
        ) = _observation_contract_issues(
            observation,
            observed_at=observed_at,
            expected_implementation_sha256=implementation_sha256,
        )
        if issues:
            invalidate(*issues)
            continue
        observed_key = observed_at.isoformat()
        source_cycle_id = str(observation["source_cycle_id"])
        duplicate_codes = []
        if input_sha256 in seen_inputs:
            duplicate_codes.append("DUPLICATE_INPUT_REPLAY")
        if observed_key in seen_times:
            duplicate_codes.append("DUPLICATE_OBSERVED_AT_REPLAY")
        if source_cycle_id in seen_source_cycles:
            duplicate_codes.append("DUPLICATE_SOURCE_CYCLE_REPLAY")
        if duplicate_codes:
            exclude(*duplicate_codes)
            continue
        if latest_accepted_at is not None and observed_at <= latest_accepted_at:
            invalidate("NON_MONOTONIC_FORWARD_TIME")
            continue
        latest_accepted_at = observed_at
        seen_inputs.add(input_sha256)
        seen_times.add(observed_key)
        seen_source_cycles.add(source_cycle_id)
        signal_totals.update(signals)
        accepted_market_days.update((observed_at.date().isoformat(),))
        accepted.append({
            "sequence": int(observation["sequence"]),
            "observation_id": str(observation["observation_id"]),
            "observation_hash": str(observation["observation_hash"]),
            "observed_at": observed_key,
            "source_cycle_id": source_cycle_id,
            "bars_sha256": input_sha256,
            "decision_input_sha256": decision_input_sha256,
            "capture_nonce_sha256": nonce_sha256,
        })

    head_hash = str(observations[-1].get("observation_hash", "")) if observations else ""
    accepted_count = len(accepted)
    accepted_day_count = len(accepted_market_days)
    minimum_cycles = ForexObservationJournal.MINIMUM_MARKET_OPEN_OBSERVATIONS
    minimum_days = ForexObservationJournal.MINIMUM_MARKET_DAYS
    sample_complete = bool(
        not invalid_cycle_count
        and accepted_count >= minimum_cycles
        and accepted_day_count >= minimum_days
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": (
            "BLOCKED_INVALID_FORWARD_EVIDENCE"
            if invalid_cycle_count
            else "FORWARD_OBSERVATION_SAMPLE_COMPLETE"
            if sample_complete
            else "COLLECTING_FORWARD_EVIDENCE"
        ),
        "mode": "FOREX_V2_FORWARD_SIGNAL_EVIDENCE_ONLY",
        "generated_at": selected_now.isoformat(),
        "source_state_valid": True,
        "source_cutoff_sequence": len(observations),
        "source_head_hash": head_hash,
        "candidate_id": policy.candidate_id,
        "frozen_after": policy.frozen_after.isoformat(),
        "policy_fingerprint_sha256": policy.fingerprint_sha256,
        "implementation_sha256": implementation_sha256,
        "accepted_cycle_count": accepted_count,
        "accepted_market_day_count": accepted_day_count,
        "minimum_accepted_cycle_count": minimum_cycles,
        "minimum_market_day_count": minimum_days,
        "remaining_accepted_cycles": max(0, minimum_cycles - accepted_count),
        "remaining_market_days": max(0, minimum_days - accepted_day_count),
        "observation_sample_complete": sample_complete,
        "excluded_cycle_count": excluded_cycle_count,
        "invalid_cycle_count": invalid_cycle_count,
        "accepted_observations": accepted,
        "accepted_by_market_day": dict(sorted(accepted_market_days.items())),
        "exclusions": dict(sorted(exclusions.items())),
        "invalid_issues": dict(sorted(invalid_issues.items())),
        "signal_comparison": {
            key: signal_totals[key]
            for key in (
                "base_entry_signal_count",
                "retained_entry_signal_count",
                "filtered_entry_signal_count",
            )
        },
        "evidence_valid": bool(accepted_count and not invalid_cycle_count),
        **_safety_contract(),
    }
    report["content_sha256"] = _content_sha256(report)
    return report


class ForexV2ForwardEvidenceReport:
    """Strictly load and atomically persist the latest forward-only report."""

    MAX_SOURCE_BYTES = 100_000_000
    MAX_REPORT_BYTES = 25_000_000

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.observation_path = root / "data" / "trading" / "forex_observations.json"
        self.path = root / "data" / "trading" / "research" / "forward_v2_latest.json"
        self.lock_path = self.path.with_name(".forward_v2_latest.lock")

    def build(
        self,
        observation_state: object,
        *,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        return build_forex_v2_forward_evidence_report(
            observation_state,
            generated_at=generated_at,
        )

    def refresh(
        self,
        observation_state: object = _MISSING,
        *,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        selected_now = aware_utc(
            generated_at or datetime.now(timezone.utc),
            "generated_at",
        )
        if observation_state is _MISSING:
            try:
                state = self._load_strict()
            except (
                OSError,
                UnicodeError,
                json.JSONDecodeError,
                RecursionError,
                MemoryError,
                TradingValidationError,
            ) as error:
                try:
                    implementation = expected_candidate_implementation_sha256()
                except TradingValidationError:
                    implementation = ""
                return _blocked_source_report(
                    selected_now,
                    str(error),
                    implementation_sha256=implementation,
                )
        else:
            state = observation_state
        try:
            report = self.build(state, generated_at=selected_now)
        except (
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
            MemoryError,
            TradingValidationError,
        ) as error:
            return _blocked_source_report(
                selected_now,
                f"forex_forward_evidence: source_build_invalid: {error}",
            )
        if report.get("source_state_valid") is True:
            try:
                return self._persist_monotonic(
                    report,
                    observation_state=state,
                    generated_at=selected_now,
                )
            except (OSError, RuntimeError):
                return _blocked_source_report(
                    selected_now,
                    "forex_forward_evidence: report_persistence_failed",
                    implementation_sha256=str(
                        report.get("implementation_sha256", "")
                    ),
                )
        return report

    def review(
        self,
        *,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Build from the strict source without mutating the saved report."""
        selected_now = aware_utc(
            generated_at or datetime.now(timezone.utc),
            "generated_at",
        )
        try:
            state = self._load_strict()
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            RecursionError,
            MemoryError,
            TradingValidationError,
        ) as error:
            try:
                implementation = expected_candidate_implementation_sha256()
            except TradingValidationError:
                implementation = ""
            return _blocked_source_report(
                selected_now,
                str(error),
                implementation_sha256=implementation,
            )
        try:
            return self.build(state, generated_at=selected_now)
        except (
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
            MemoryError,
            TradingValidationError,
        ) as error:
            return _blocked_source_report(
                selected_now,
                f"forex_forward_evidence: source_build_invalid: {error}",
            )

    def _load_strict(self) -> object:
        if not self.observation_path.is_file():
            raise TradingValidationError(
                "forex_forward_evidence: observation_source_missing"
            )
        size = self.observation_path.stat().st_size
        if size <= 0 or size > self.MAX_SOURCE_BYTES:
            raise TradingValidationError(
                "forex_forward_evidence: observation_source_size_invalid"
            )
        return json.loads(self.observation_path.read_text(encoding="utf-8"))

    def _persist_monotonic(
        self,
        report: Mapping[str, Any],
        *,
        observation_state: object,
        generated_at: datetime,
    ) -> dict[str, Any]:
        selected = deepcopy(dict(report))
        with exclusive_file_lock(
            self.lock_path,
            timeout_message="Forex forward evidence report lock timeout",
        ):
            previous = self._load_saved_report()
            if previous is not None:
                previous_cutoff = int(previous["source_cutoff_sequence"])
                selected_cutoff = int(selected["source_cutoff_sequence"])
                if previous_cutoff > selected_cutoff:
                    return _blocked_source_report(
                        generated_at,
                        "forex_forward_evidence: source_cutoff_regressed",
                        implementation_sha256=str(
                            selected.get("implementation_sha256", "")
                        ),
                    )
                if previous_cutoff < selected_cutoff:
                    ancestor_head = self._source_head_at_cutoff(
                        observation_state,
                        previous_cutoff,
                    )
                    if ancestor_head != previous.get("source_head_hash"):
                        return _blocked_source_report(
                            generated_at,
                            "forex_forward_evidence: source_chain_ancestry_conflict",
                            implementation_sha256=str(
                                selected.get("implementation_sha256", "")
                            ),
                        )
                if previous_cutoff == selected_cutoff:
                    if previous.get("source_head_hash") == selected.get(
                        "source_head_hash"
                    ):
                        if previous.get("content_sha256") == selected.get(
                            "content_sha256"
                        ):
                            return deepcopy(previous)
                        return _blocked_source_report(
                            generated_at,
                            "forex_forward_evidence: report_content_conflict",
                            implementation_sha256=str(
                                selected.get("implementation_sha256", "")
                            ),
                        )
                    return _blocked_source_report(
                        generated_at,
                        "forex_forward_evidence: source_cutoff_conflict",
                        implementation_sha256=str(
                            selected.get("implementation_sha256", "")
                        ),
                    )
            self._write_atomic(selected)
        return selected

    @staticmethod
    def _source_head_at_cutoff(
        observation_state: object,
        cutoff: int,
    ) -> str | None:
        if cutoff == 0:
            return ""
        if not isinstance(observation_state, Mapping):
            return None
        observations = observation_state.get("observations")
        if not isinstance(observations, list) or len(observations) < cutoff:
            return None
        item = observations[cutoff - 1]
        if not isinstance(item, Mapping):
            return None
        head_hash = item.get("observation_hash")
        if not isinstance(head_hash, str) or not _SHA256.fullmatch(head_hash):
            return None
        return head_hash

    def _load_saved_report(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        try:
            size = self.path.stat().st_size
            if size <= 0 or size > self.MAX_REPORT_BYTES:
                return None
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            RecursionError,
            MemoryError,
        ):
            return None
        if not isinstance(value, Mapping):
            return None
        selected = dict(value)
        cutoff = selected.get("source_cutoff_sequence")
        head_hash = str(selected.get("source_head_hash", ""))
        content_sha256 = str(selected.get("content_sha256", ""))
        if (
            type(selected.get("schema_version")) is not int
            or selected.get("schema_version") != 1
            or selected.get("mode")
            != "FOREX_V2_FORWARD_SIGNAL_EVIDENCE_ONLY"
            or selected.get("source_state_valid") is not True
            or type(cutoff) is not int
            or int(cutoff) < 0
            or (int(cutoff) == 0 and head_hash != "")
            or (int(cutoff) > 0 and not _SHA256.fullmatch(head_hash))
            or not _SHA256.fullmatch(content_sha256)
            or content_sha256 != _content_sha256(selected)
            or any(selected.get(field) is not False for field in _safety_contract())
        ):
            return None
        return selected

    def _write_atomic(self, report: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".forward-v2-",
            suffix=".json",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise


__all__ = [
    "ForexV2ForwardEvidenceReport",
    "build_forex_v2_forward_evidence_report",
    "expected_candidate_implementation_sha256",
]
