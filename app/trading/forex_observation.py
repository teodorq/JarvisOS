"""Tamper-evident Forex observation cycles that never execute an order."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import threading
from typing import TYPE_CHECKING, Any, Mapping

from app.core.exclusive_file_lock import exclusive_file_lock
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_candidate_v2 import ForexRegimeFilteredScanner
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_models import (
    MAJOR_FOREX_PAIRS,
    ForexBar,
    ForexPosition,
    ForexQuote,
    ForexSafetyContext,
)
from app.trading.forex_risk import ForexPaperPolicy, ForexRateBook
from app.trading.forex_sample_contract import build_forex_paper_sample_contract
from app.trading.forex_scanner import ForexMarketScanner
from app.trading.models import TradingValidationError, aware_utc

if TYPE_CHECKING:
    from app.market_data.forex_gateway import ForexReadOnlyDataGateway


_OBSERVATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,79}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OBSERVATION_SCHEMA_VERSION = 2
_CAPTURE_ORIGINS = frozenset({
    "MANUAL",
    "SCHEDULED_FORWARD",
    "STARTUP_RECOVERY",
    "REPLAY",
})
_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _shared_lock(path: Path) -> threading.RLock:
    key = str(path).casefold()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _safe_reason(error: Exception) -> str:
    raw = str(error or "DATA_SOURCE_FAILURE").upper()
    cleaned = re.sub(r"[^A-Z0-9_:.-]+", "_", raw).strip("_")
    return cleaned[:160] or "DATA_SOURCE_FAILURE"


def _capture_origin(value: object) -> str:
    selected = str(value or "").strip().upper()
    if selected not in _CAPTURE_ORIGINS:
        raise TradingValidationError("forex_observation: invalid_capture_origin")
    return selected


def _capture_attestation(value: object, *, origin: str) -> dict[str, Any]:
    if origin == "SCHEDULED_FORWARD":
        selected = dict(value) if isinstance(value, Mapping) else {}
        if (
            selected.get("kind") != "LOCAL_WATCHDOG_ANCESTRY_NONCE_V1"
            or selected.get("verified") is not True
            or selected.get("trust_level") != "BEST_EFFORT_LOCAL_PROCESS"
            or selected.get("verified_scope")
            != "WATCHDOG_ANCESTRY_AND_NONCE_FORMAT"
            or not _SHA256.fullmatch(str(selected.get("nonce_sha256", "")))
            or type(selected.get("watchdog_process_id")) is not int
            or int(selected["watchdog_process_id"]) <= 0
        ):
            raise TradingValidationError(
                "forex_observation: scheduled_attestation_invalid"
            )
        return {
            "kind": "LOCAL_WATCHDOG_ANCESTRY_NONCE_V1",
            "verified": True,
            "trust_level": "BEST_EFFORT_LOCAL_PROCESS",
            "verified_scope": "WATCHDOG_ANCESTRY_AND_NONCE_FORMAT",
            "nonce_sha256": str(selected["nonce_sha256"]),
            "watchdog_process_id": int(selected["watchdog_process_id"]),
        }
    if origin == "MANUAL":
        return {"kind": "MANUAL_DIRECT_V1", "verified": False}
    return {
        "kind": f"{origin}_DECLARATION_V1",
        "verified": False,
    }


def forex_candidate_implementation_sha256() -> str:
    """Fingerprint the exact frozen-candidate implementation source."""
    classes = (ForexRegimeFilteredScanner, ForexMarketScanner, ForexBar)
    module_names = sorted({item.__module__ for item in classes})
    digest = hashlib.sha256()
    for module_name in module_names:
        module = sys.modules.get(module_name)
        raw_path = getattr(module, "__file__", None)
        if not raw_path:
            raise TradingValidationError(
                "forex_observation: implementation_source_unavailable"
            )
        try:
            source = Path(raw_path).read_bytes().replace(b"\r\n", b"\n")
        except OSError as error:
            raise TradingValidationError(
                "forex_observation: implementation_source_unavailable"
            ) from error
        digest.update(module_name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source)
        digest.update(b"\0")
    return digest.hexdigest()


def _canonical_source_histories(
    value: object,
) -> dict[str, tuple[ForexBar, ...]]:
    if not isinstance(value, Mapping):
        raise TradingValidationError("forex_observation: source_bars_required")
    symbols = tuple(sorted(pair.symbol for pair in MAJOR_FOREX_PAIRS))
    if {str(key) for key in value} != set(symbols):
        raise TradingValidationError(
            "forex_observation: source_pair_coverage_invalid"
        )
    histories: dict[str, tuple[ForexBar, ...]] = {}
    for symbol in symbols:
        try:
            history = tuple(value[symbol])
        except (KeyError, TypeError) as error:
            raise TradingValidationError(
                "forex_observation: source_history_invalid"
            ) from error
        if not history:
            raise TradingValidationError(
                "forex_observation: source_history_empty"
            )
        if any(
            not isinstance(bar, ForexBar) or bar.pair.symbol != symbol
            for bar in history
        ):
            raise TradingValidationError(
                "forex_observation: source_history_invalid"
            )
        histories[symbol] = history
    return histories


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_evidence(
    histories: Mapping[str, tuple[ForexBar, ...]],
    *,
    quotes: Mapping[str, ForexQuote],
    conversion_quotes: tuple[ForexQuote, ...],
    contexts: Mapping[str, ForexSafetyContext],
    positions: Mapping[str, ForexPosition],
    account: Mapping[str, object],
    diagnostics: Mapping[str, object],
    captured_at: datetime,
) -> dict[str, Any]:
    symbols = set(histories)
    if set(quotes) != symbols or any(
        not isinstance(quote, ForexQuote)
        or quote.pair.symbol != symbol
        for symbol, quote in quotes.items()
    ):
        raise TradingValidationError(
            "forex_observation: source_quote_coverage_invalid"
        )
    if set(contexts) != symbols or any(
        not isinstance(context, ForexSafetyContext)
        for context in contexts.values()
    ):
        raise TradingValidationError(
            "forex_observation: source_context_coverage_invalid"
        )
    if not set(positions).issubset(symbols) or any(
        not isinstance(position, ForexPosition)
        or position.pair.symbol != symbol
        for symbol, position in positions.items()
    ):
        raise TradingValidationError(
            "forex_observation: source_position_state_invalid"
        )

    digest = hashlib.sha256()
    bar_counts: dict[str, int] = {}
    latest_bar_open_at: dict[str, str] = {}
    bars_strictly_ordered = True
    latest_bars_closed = True
    for symbol in sorted(histories):
        history = histories[symbol]
        bar_counts[symbol] = len(history)
        previous_at: datetime | None = None
        for bar in history:
            if previous_at is not None and bar.timestamp <= previous_at:
                bars_strictly_ordered = False
            previous_at = bar.timestamp
            row = {
                "pair": symbol,
                "timestamp": bar.timestamp.isoformat(),
                "open": str(bar.open),
                "high": str(bar.high),
                "low": str(bar.low),
                "close": str(bar.close),
                "tick_volume": str(bar.tick_volume),
            }
            digest.update(json.dumps(
                row,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"))
            digest.update(b"\n")
        latest = history[-1].timestamp
        latest_bar_open_at[symbol] = latest.isoformat()
        latest_bars_closed = latest_bars_closed and (
            latest + timedelta(minutes=15) <= captured_at
        )
    tagged_quotes = [
        *(("TRADABLE", quote) for quote in quotes.values()),
        *(("CONVERSION", quote) for quote in conversion_quotes),
    ]
    quote_rows = [
        {
            "pair": quote.pair.symbol,
            "bid": str(quote.bid),
            "ask": str(quote.ask),
            "timestamp": quote.timestamp.isoformat(),
            "role": role,
        }
        for role, quote in sorted(
            tagged_quotes,
            key=lambda item: (item[1].pair.symbol, item[0]),
        )
    ]
    if len({(item["pair"], item["role"]) for item in quote_rows}) != len(
        quote_rows
    ):
        raise TradingValidationError(
            "forex_observation: duplicate_source_quote"
        )
    context_rows = [
        {
            "pair": symbol,
            "observed_at": contexts[symbol].observed_at.isoformat(),
            "market_open": contexts[symbol].market_open,
            "calendar_ready": contexts[symbol].calendar_ready,
            "high_impact_event_blocked": (
                contexts[symbol].high_impact_event_blocked
            ),
            "conversion_to_pln_ready": (
                contexts[symbol].conversion_to_pln_ready
            ),
            "independent_source_count": (
                contexts[symbol].independent_source_count
            ),
        }
        for symbol in sorted(contexts)
    ]
    independent_source_counts = {
        symbol: contexts[symbol].independent_source_count
        for symbol in sorted(contexts)
    }
    position_rows = [
        {
            "pair": symbol,
            "side": positions[symbol].side,
            "units": str(positions[symbol].units),
            "entry_price": str(positions[symbol].entry_price),
            "current_price": str(positions[symbol].current_price),
            "stop_loss": str(positions[symbol].stop_loss),
            "take_profit": (
                ""
                if positions[symbol].take_profit is None
                else str(positions[symbol].take_profit)
            ),
            "opened_at": positions[symbol].opened_at.isoformat(),
        }
        for symbol in sorted(positions)
    ]
    account_input = {
        "equity_pln": str(account.get("equity_pln", "")),
        "daily_pnl_pln": str(account.get("daily_pnl_pln", "")),
    }
    input_sha256 = digest.hexdigest()
    quote_snapshot_sha256 = _canonical_sha256(quote_rows)
    context_snapshot_sha256 = _canonical_sha256(context_rows)
    position_snapshot_sha256 = _canonical_sha256(position_rows)
    account_snapshot_sha256 = _canonical_sha256(account_input)
    diagnostics_snapshot_sha256 = _canonical_sha256(dict(diagnostics))
    decision_input_sha256 = _canonical_sha256({
        "captured_at": captured_at.isoformat(),
        "bars_sha256": input_sha256,
        "quote_snapshot_sha256": quote_snapshot_sha256,
        "context_snapshot_sha256": context_snapshot_sha256,
        "position_snapshot_sha256": position_snapshot_sha256,
        "account_snapshot_sha256": account_snapshot_sha256,
        "diagnostics_snapshot_sha256": diagnostics_snapshot_sha256,
    })
    return {
        "schema_version": 1,
        "timeframe": "M15_CLOSED_BARS",
        "pair_count": len(histories),
        "bar_counts": bar_counts,
        "latest_bar_open_at": latest_bar_open_at,
        "latest_bars_closed": latest_bars_closed,
        "bars_strictly_ordered": bars_strictly_ordered,
        "independent_source_counts": independent_source_counts,
        "input_sha256": input_sha256,
        "quote_snapshot_sha256": quote_snapshot_sha256,
        "context_snapshot_sha256": context_snapshot_sha256,
        "position_snapshot_sha256": position_snapshot_sha256,
        "account_snapshot_sha256": account_snapshot_sha256,
        "diagnostics_snapshot_sha256": diagnostics_snapshot_sha256,
        "decision_input_sha256": decision_input_sha256,
        "recovery_replay": False,
        "idempotent_replay": False,
    }


class ForexObservationJournal:
    """Store bounded observation evidence separately from the paper ledger."""

    MAX_OBSERVATIONS = 10_000
    MAX_SOURCE_BYTES = 100_000_000
    MINIMUM_MARKET_OPEN_OBSERVATIONS = 20
    MINIMUM_MARKET_DAYS = 3

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.path = root / "data" / "trading" / "forex_observations.json"
        self.store = JsonStore(self.path, self._default)
        self._lock = _shared_lock(self.path)
        self.lock_path = self.path.with_name(".forex_observations.lock")

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mode": "FOREX_OBSERVATION_ONLY",
            "observations": [],
        }

    def record(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        raw_observation_id = observation.get("observation_id")
        if (
            not isinstance(raw_observation_id, str)
            or not _OBSERVATION_ID.fullmatch(raw_observation_id)
        ):
            raise TradingValidationError("forex_observation: invalid_id")
        observation_id = raw_observation_id
        selected = deepcopy(dict(observation))
        if selected.get("mode") != "FOREX_OBSERVATION_ONLY":
            raise TradingValidationError("forex_observation: invalid_mode")
        if bool(selected.get("paper_orders_sent")) or bool(
            selected.get("live_orders_sent")
        ):
            raise TradingValidationError("forex_observation: order_flag_forbidden")
        with self._lock, exclusive_file_lock(
            self.lock_path,
            timeout_message="Forex observation journal lock timeout",
        ):
            state = self._normalized(self._load_strict())
            if not self.verify(state):
                raise TradingValidationError("forex_observation: audit_chain_invalid")
            for previous in state["observations"]:
                if previous.get("observation_id") == observation_id:
                    replay = deepcopy(previous)
                    replay["idempotent_replay"] = True
                    return replay
            observations = list(state["observations"])
            selected["sequence"] = len(observations) + 1
            selected["previous_hash"] = (
                str(observations[-1].get("observation_hash", ""))
                if observations else ""
            )
            selected["observation_hash"] = self._hash(selected)
            observations.append(selected)
            if len(observations) > self.MAX_OBSERVATIONS:
                observations = self._rehash(
                    observations[-self.MAX_OBSERVATIONS:]
                )
            state["observations"] = observations
            self.store.save(state)
            saved = deepcopy(observations[-1])
            saved["idempotent_replay"] = False
            return saved

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._normalized(self._load_strict()))

    def summary(self) -> dict[str, Any]:
        review = self.review()
        return {
            "status": "BLOCKED" if review["status"] == "BLOCKED" else "READY",
            "mode": "FOREX_OBSERVATION_ONLY",
            "observation_count": review["observation_count"],
            "completed_count": review["completed_count"],
            "blocked_count": review["blocked_count"],
            "qualified_market_open_count": review[
                "qualified_market_open_count"
            ],
            "qualified_market_day_count": review["qualified_market_day_count"],
            "minimum_market_open_observations": (
                self.MINIMUM_MARKET_OPEN_OBSERVATIONS
            ),
            "minimum_market_days": self.MINIMUM_MARKET_DAYS,
            "paper_promotion_ready": review["owner_review_ready"],
            "automatic_promotion": False,
            "audit_chain_valid": review["audit_chain_valid"],
            "latest_observation_id": review["latest_observation_id"],
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }

    def review(self) -> dict[str, Any]:
        """Build a read-only evidence review without enabling PAPER execution."""
        state = self.snapshot()
        observations = list(state["observations"])
        audit_valid = self.verify(state)
        completed = [
            item for item in observations
            if item.get("status") == "OBSERVATION_RECORDED"
        ]
        statuses = Counter(
            str(item.get("status", "UNKNOWN")) or "UNKNOWN"
            for item in observations
        )
        market_days: Counter[str] = Counter()
        opening_blocks: Counter[str] = Counter()
        assessment_actions: Counter[str] = Counter()
        instruction_actions: Counter[str] = Counter()
        instruction_pairs: Counter[str] = Counter()
        assessed_pairs: Counter[str] = Counter()
        execution_statuses: Counter[str] = Counter()
        observed_times: list[datetime] = []
        expected_pairs = {pair.symbol for pair in MAJOR_FOREX_PAIRS}
        expected_candidate = ForexRegimeFilteredScanner(MAJOR_FOREX_PAIRS)
        expected_candidate_implementation = (
            forex_candidate_implementation_sha256()
        )
        expected_sample_contract = build_forex_paper_sample_contract(
            scanner_policy=expected_candidate.policy,
            paper_policy=ForexPaperPolicy(),
            universe=expected_candidate.universe,
        )
        candidate_forward_seen_count = 0
        candidate_forward_expected_count = 0
        candidate_forward_count = 0
        candidate_invalid_forward_count = 0
        candidate_market_days: Counter[str] = Counter()
        candidate_assessment_actions: Counter[str] = Counter()
        candidate_instruction_actions: Counter[str] = Counter()
        candidate_exclusion_reasons: Counter[str] = Counter()
        candidate_contract_issues: Counter[str] = Counter()
        candidate_filter_reasons: Counter[str] = Counter()
        candidate_entry_pairs: Counter[str] = Counter()
        candidate_base_entry_signal_count = 0
        candidate_retained_entry_signal_count = 0
        candidate_filtered_entry_signal_count = 0
        qualified_pair_coverage_complete = True
        qualified_count = 0
        schema_issue_detected = False
        for item in observations:
            item_status = str(item.get("status", ""))
            is_qualified = (
                item_status == "OBSERVATION_RECORDED"
                and item.get("market_open") is True
                and item.get("fully_cross_checked") is True
            )
            schema_issue_detected = schema_issue_detected or (
                item_status not in {"OBSERVATION_RECORDED", "DATA_BLOCKED"}
                or item.get("mode") != "FOREX_OBSERVATION_ONLY"
                or type(item.get("market_open")) is not bool
                or type(item.get("fully_cross_checked")) is not bool
            )
            try:
                observed_at = datetime.fromisoformat(
                    str(item.get("observed_at", "")).replace("Z", "+00:00")
                )
                observed_at = aware_utc(observed_at, "observed_at")
            except (TypeError, ValueError, TradingValidationError):
                schema_issue_detected = True
            else:
                observed_times.append(observed_at)
                if is_qualified:
                    qualified_count += 1
                    market_days.update((observed_at.date().isoformat(),))

                raw_candidate = item.get("development_candidate_v2")
                is_post_freeze = (
                    expected_candidate.candidate_policy.forward_eligible(
                        observed_at
                    )
                )
                candidate_expected = is_qualified and is_post_freeze
                if candidate_expected:
                    candidate_forward_expected_count += 1
                candidate_forward = (
                    isinstance(raw_candidate, Mapping)
                    and raw_candidate.get("forward_eligible") is True
                )
                if candidate_expected and not candidate_forward:
                    candidate_invalid_forward_count += 1
                    candidate_contract_issues.update((
                        "CANDIDATE_PAYLOAD_MISSING",
                    ))
                if candidate_forward:
                    candidate_forward_seen_count += 1
                    candidate = dict(raw_candidate)
                    raw_candidate_assessments = candidate.get(
                        "assessments", []
                    )
                    candidate_assessments = (
                        list(raw_candidate_assessments)
                        if isinstance(raw_candidate_assessments, (list, tuple))
                        else []
                    )
                    candidate_plan = candidate.get("proposed_plan", {})
                    candidate_instructions = list(
                        candidate_plan.get("instructions", []) or []
                    ) if isinstance(candidate_plan, Mapping) else []
                    candidate_pair_names = [
                        str(assessment.get("pair", ""))
                        for assessment in candidate_assessments
                        if isinstance(assessment, Mapping)
                        and assessment.get("pair")
                    ]
                    candidate_pairs = set(candidate_pair_names)
                    raw_base_assessments = item.get("assessments", [])
                    base_assessments = (
                        list(raw_base_assessments)
                        if isinstance(raw_base_assessments, (list, tuple))
                        else []
                    )
                    base_pair_names = [
                        str(assessment.get("pair", ""))
                        for assessment in base_assessments
                        if isinstance(assessment, Mapping)
                        and assessment.get("pair")
                    ]
                    base_pairs = set(base_pair_names)
                    candidate_execution = candidate.get("execution", {})
                    candidate_entries = {
                        (
                            str(assessment.get("pair", "")),
                            str(assessment.get("action", "")),
                        )
                        for assessment in candidate_assessments
                        if isinstance(assessment, Mapping)
                        and str(assessment.get("action", "")).startswith(
                            "OPEN_"
                        )
                    }
                    base_entries = {
                        (
                            str(assessment.get("pair", "")),
                            str(assessment.get("action", "")),
                        )
                        for assessment in base_assessments
                        if isinstance(assessment, Mapping)
                        and str(assessment.get("action", "")).startswith(
                            "OPEN_"
                        )
                    }
                    candidate_exits = {
                        (
                            str(assessment.get("pair", "")),
                            str(assessment.get("action", "")),
                        )
                        for assessment in candidate_assessments
                        if isinstance(assessment, Mapping)
                        and str(assessment.get("action", "")).startswith(
                            "CLOSE_"
                        )
                    }
                    base_exits = {
                        (
                            str(assessment.get("pair", "")),
                            str(assessment.get("action", "")),
                        )
                        for assessment in base_assessments
                        if isinstance(assessment, Mapping)
                        and str(assessment.get("action", "")).startswith(
                            "CLOSE_"
                        )
                    }
                    contract_issues: list[str] = []
                    if not is_post_freeze:
                        contract_issues.append(
                            "FORWARD_ELIGIBILITY_MISMATCH"
                        )
                    has_v2_provenance = (
                        item.get("observation_schema_version") == 2
                    )
                    for invalid, code in (
                        (
                            candidate.get("candidate_id")
                            != expected_candidate.candidate_policy.candidate_id,
                            "CANDIDATE_ID_MISMATCH",
                        ),
                        (
                            candidate.get("policy_fingerprint_sha256")
                            != expected_candidate.candidate_policy.fingerprint_sha256,
                            "POLICY_FINGERPRINT_MISMATCH",
                        ),
                        (
                            has_v2_provenance
                            and candidate.get("implementation_sha256")
                            != expected_candidate_implementation,
                            "IMPLEMENTATION_FINGERPRINT_MISMATCH",
                        ),
                        (
                            has_v2_provenance
                            and candidate.get("paper_sample_contract_id")
                            != expected_sample_contract["contract_id"],
                            "PAPER_SAMPLE_CONTRACT_ID_MISMATCH",
                        ),
                        (
                            has_v2_provenance
                            and candidate.get(
                                "paper_sample_contract_fingerprint_sha256"
                            )
                            != expected_sample_contract["fingerprint_sha256"],
                            "PAPER_SAMPLE_CONTRACT_FINGERPRINT_MISMATCH",
                        ),
                        (
                            not isinstance(
                                raw_candidate_assessments, (list, tuple)
                            )
                            or candidate_pairs != expected_pairs
                            or len(candidate_pair_names) != len(expected_pairs),
                            "CANDIDATE_PAIR_COVERAGE_INVALID",
                        ),
                        (
                            not isinstance(candidate_execution, Mapping)
                            or candidate_execution.get("status")
                            != "NOT_EXECUTED",
                            "CANDIDATE_EXECUTION_CONTRACT_INVALID",
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
                        (
                            bool(candidate_entries - base_entries),
                            "CANDIDATE_ENTRY_NOT_SUBSET_OF_BASE",
                        ),
                        (
                            candidate_exits != base_exits,
                            "CANDIDATE_EXIT_PARITY_INVALID",
                        ),
                    ):
                        if invalid:
                            contract_issues.append(code)
                    if contract_issues:
                        candidate_invalid_forward_count += 1
                        candidate_contract_issues.update(set(contract_issues))
                    elif not is_qualified:
                        candidate_exclusion_reasons.update((
                            "BASE_OBSERVATION_NOT_QUALIFIED",
                        ))
                    elif (
                        base_pairs != expected_pairs
                        or len(base_pair_names) != len(expected_pairs)
                    ):
                        candidate_exclusion_reasons.update((
                            "BASE_PAIR_COVERAGE_INCOMPLETE",
                        ))
                    else:
                        candidate_forward_count += 1
                        candidate_market_days.update(
                            (observed_at.date().isoformat(),)
                        )
                        candidate_base_entry_signal_count += len(base_entries)
                        candidate_retained_entry_signal_count += len(
                            candidate_entries
                        )
                        filtered_entries = base_entries - candidate_entries
                        candidate_filtered_entry_signal_count += len(
                            filtered_entries
                        )
                        candidate_entry_pairs.update(
                            pair for pair, _action in candidate_entries
                        )
                        candidate_by_pair = {
                            str(assessment.get("pair", "")): assessment
                            for assessment in candidate_assessments
                            if isinstance(assessment, Mapping)
                        }
                        for pair, _action in filtered_entries:
                            assessment = candidate_by_pair.get(pair, {})
                            raw_reasons = assessment.get("reason_codes", [])
                            if isinstance(raw_reasons, (list, tuple)):
                                candidate_filter_reasons.update(
                                    str(code)
                                    for code in raw_reasons
                                    if str(code)
                                )
                        for assessment in candidate_assessments:
                            if isinstance(assessment, Mapping):
                                candidate_assessment_actions.update((str(
                                    assessment.get("action", "UNKNOWN")
                                ),))
                        for instruction in candidate_instructions:
                            if isinstance(instruction, Mapping):
                                candidate_instruction_actions.update((str(
                                    instruction.get("action", "UNKNOWN")
                                ),))

            raw_blocks = item.get("opening_blocks", [])
            if isinstance(raw_blocks, (list, tuple)):
                opening_blocks.update(
                    str(code) for code in raw_blocks if str(code)
                )
            else:
                schema_issue_detected = True
            raw_execution = item.get("execution", {})
            execution = (
                dict(raw_execution) if isinstance(raw_execution, Mapping) else {}
            )
            if not isinstance(raw_execution, Mapping):
                schema_issue_detected = True
            execution_statuses.update((str(execution.get("status", "MISSING")),))
            raw_assessments = item.get("assessments", [])
            assessments = (
                list(raw_assessments)
                if isinstance(raw_assessments, (list, tuple))
                else []
            )
            if not isinstance(raw_assessments, (list, tuple)):
                schema_issue_detected = True
            observed_pairs = {
                str(assessment.get("pair", ""))
                for assessment in assessments
                if isinstance(assessment, dict) and assessment.get("pair")
            }
            for assessment in assessments:
                if not isinstance(assessment, dict):
                    continue
                pair = str(assessment.get("pair", ""))
                action = str(assessment.get("action", "UNKNOWN")) or "UNKNOWN"
                if pair:
                    assessed_pairs.update((pair,))
                assessment_actions.update((action,))
            if is_qualified and observed_pairs != expected_pairs:
                qualified_pair_coverage_complete = False
            raw_plan = item.get("proposed_plan", {})
            plan = dict(raw_plan) if isinstance(raw_plan, Mapping) else {}
            if not isinstance(raw_plan, Mapping):
                schema_issue_detected = True
            raw_instructions = plan.get("instructions", [])
            instructions = (
                list(raw_instructions)
                if isinstance(raw_instructions, (list, tuple))
                else []
            )
            if not isinstance(raw_instructions, (list, tuple)):
                schema_issue_detected = True
            for instruction in instructions:
                if not isinstance(instruction, dict):
                    continue
                action = str(instruction.get("action", "UNKNOWN")) or "UNKNOWN"
                pair = str(instruction.get("pair", ""))
                instruction_actions.update((action,))
                if pair:
                    instruction_pairs.update((pair,))

        paper_order_detected = any(
            item.get("paper_orders_sent") is not False for item in observations
        )
        live_order_detected = any(
            item.get("live_orders_sent") is not False for item in observations
        )
        order_network_detected = any(
            item.get("order_network_access") is not False for item in observations
        )
        position_change_detected = any(
            item.get("positions_unchanged") is not True for item in observations
        )
        execution_detected = (
            execution_statuses.get("NOT_EXECUTED", 0) != len(observations)
        )
        day_count = len(market_days)
        gate_ready = (
            audit_valid
            and qualified_count >= self.MINIMUM_MARKET_OPEN_OBSERVATIONS
            and day_count >= self.MINIMUM_MARKET_DAYS
        )
        critical_issues: list[str] = []
        for detected, code in (
            (not audit_valid, "AUDIT_CHAIN_INVALID"),
            (paper_order_detected, "PAPER_ORDER_FLAG_DETECTED"),
            (live_order_detected, "LIVE_ORDER_FLAG_DETECTED"),
            (order_network_detected, "ORDER_NETWORK_ACCESS_DETECTED"),
            (position_change_detected, "POSITION_STATE_CHANGED"),
            (execution_detected, "EXECUTION_STATUS_INVALID"),
            (schema_issue_detected, "OBSERVATION_SCHEMA_INVALID"),
            (
                not qualified_pair_coverage_complete,
                "QUALIFIED_PAIR_COVERAGE_INCOMPLETE",
            ),
        ):
            if detected:
                critical_issues.append(code)
        pending: list[str] = []
        if qualified_count < self.MINIMUM_MARKET_OPEN_OBSERVATIONS:
            pending.append("MINIMUM_QUALIFIED_OBSERVATIONS_PENDING")
        if day_count < self.MINIMUM_MARKET_DAYS:
            pending.append("MINIMUM_MARKET_DAYS_PENDING")
        owner_review_ready = gate_ready and not critical_issues
        status = (
            "BLOCKED"
            if critical_issues
            else "READY_FOR_OWNER_REVIEW"
            if owner_review_ready
            else "COLLECTING_EVIDENCE"
        )
        return {
            "status": status,
            "mode": "FOREX_OBSERVATION_REVIEW_ONLY",
            "review_only": True,
            "audit_chain_valid": audit_valid,
            "observation_count": len(observations),
            "completed_count": len(completed),
            "blocked_count": len(observations) - len(completed),
            "qualified_market_open_count": qualified_count,
            "qualified_market_day_count": day_count,
            "minimum_market_open_observations": (
                self.MINIMUM_MARKET_OPEN_OBSERVATIONS
            ),
            "minimum_market_days": self.MINIMUM_MARKET_DAYS,
            "remaining_qualified_observations": max(
                0, self.MINIMUM_MARKET_OPEN_OBSERVATIONS - qualified_count
            ),
            "remaining_market_days": max(0, self.MINIMUM_MARKET_DAYS - day_count),
            "first_observed_at": (
                min(observed_times).isoformat() if observed_times else ""
            ),
            "last_observed_at": (
                max(observed_times).isoformat() if observed_times else ""
            ),
            "latest_observation_id": (
                str(observations[-1].get("observation_id", ""))
                if observations else ""
            ),
            "distributions": {
                "observation_statuses": dict(sorted(statuses.items())),
                "qualified_by_market_day": dict(sorted(market_days.items())),
                "opening_blocks": dict(sorted(opening_blocks.items())),
                "assessment_actions": dict(sorted(assessment_actions.items())),
                "proposed_instruction_actions": dict(
                    sorted(instruction_actions.items())
                ),
                "proposed_instruction_pairs": dict(sorted(instruction_pairs.items())),
                "assessed_pairs": dict(sorted(assessed_pairs.items())),
            },
            "development_candidate_v2": {
                "candidate_id": expected_candidate.candidate_policy.candidate_id,
                "policy_fingerprint_sha256": (
                    expected_candidate.candidate_policy.fingerprint_sha256
                ),
                "frozen_after": (
                    expected_candidate.candidate_policy.frozen_after.isoformat()
                ),
                "expected_forward_observation_count": (
                    candidate_forward_expected_count
                ),
                "seen_forward_observation_count": candidate_forward_seen_count,
                "valid_forward_observation_count": candidate_forward_count,
                "excluded_forward_observation_count": sum(
                    candidate_exclusion_reasons.values()
                ),
                "invalid_forward_observation_count": (
                    candidate_invalid_forward_count
                ),
                "valid_forward_market_day_count": len(candidate_market_days),
                "evidence_valid": bool(
                    candidate_forward_expected_count
                    and not candidate_contract_issues
                ),
                "exclusion_reasons": dict(sorted(
                    candidate_exclusion_reasons.items()
                )),
                "contract_issues": dict(sorted(
                    candidate_contract_issues.items()
                )),
                "assessment_actions": dict(sorted(
                    candidate_assessment_actions.items()
                )),
                "proposed_instruction_actions": dict(sorted(
                    candidate_instruction_actions.items()
                )),
                "signal_comparison": {
                    "base_entry_signal_count": (
                        candidate_base_entry_signal_count
                    ),
                    "retained_entry_signal_count": (
                        candidate_retained_entry_signal_count
                    ),
                    "filtered_entry_signal_count": (
                        candidate_filtered_entry_signal_count
                    ),
                    "entry_signal_retention_pct": round(
                        candidate_retained_entry_signal_count
                        * 100
                        / candidate_base_entry_signal_count,
                        2,
                    ) if candidate_base_entry_signal_count else 0.0,
                    "retained_entry_pairs": dict(sorted(
                        candidate_entry_pairs.items()
                    )),
                    "filter_reasons": dict(sorted(
                        candidate_filter_reasons.items()
                    )),
                },
                "strategy_performance_validated": False,
                "automatic_paper_promotion": False,
                "paper_execution_enabled": False,
                "live_execution_enabled": False,
            },
            "safety": {
                "all_positions_unchanged": not position_change_detected,
                "qualified_pair_coverage_complete": qualified_pair_coverage_complete,
                "paper_orders_detected": paper_order_detected,
                "live_orders_detected": live_order_detected,
                "order_network_access_detected": order_network_detected,
                "execution_detected": execution_detected,
                "execution_statuses": dict(sorted(execution_statuses.items())),
            },
            "issues": critical_issues + pending,
            "observation_thresholds_met": gate_ready,
            "paper_promotion_ready": owner_review_ready,
            "owner_review_ready": owner_review_ready,
            "automatic_promotion": False,
            "paper_execution_enabled": False,
            "live_execution_enabled": False,
        }

    @classmethod
    def verify(cls, state: Mapping[str, Any]) -> bool:
        if (
            type(state.get("schema_version")) is not int
            or state.get("schema_version") != 1
            or state.get("mode") != "FOREX_OBSERVATION_ONLY"
        ):
            return False
        previous_hash = ""
        for sequence, raw in enumerate(list(state.get("observations", []) or []), 1):
            item = dict(raw or {})
            if (
                type(item.get("sequence")) is not int
                or item["sequence"] != sequence
            ):
                return False
            if str(item.get("previous_hash", "")) != previous_hash:
                return False
            try:
                expected = cls._hash(item)
            except (
                TypeError,
                ValueError,
                OverflowError,
                RecursionError,
                MemoryError,
            ):
                return False
            if str(item.get("observation_hash", "")) != expected:
                return False
            previous_hash = expected
        return True

    @classmethod
    def _rehash(cls, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        previous_hash = ""
        for sequence, raw in enumerate(observations, 1):
            item = deepcopy(raw)
            item["sequence"] = sequence
            item["previous_hash"] = previous_hash
            item["observation_hash"] = cls._hash(item)
            previous_hash = item["observation_hash"]
            result.append(item)
        return result

    @staticmethod
    def _hash(observation: Mapping[str, Any]) -> str:
        payload = {
            key: value
            for key, value in dict(observation).items()
            if key not in {"observation_hash", "idempotent_replay"}
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _normalized(self, value: object) -> dict[str, Any]:
        state = self._default()
        if isinstance(value, dict):
            state["schema_version"] = value.get("schema_version")
            state["mode"] = str(value.get("mode", ""))
            state["observations"] = [
                dict(item) for item in list(value.get("observations", []) or [])
                if isinstance(item, dict)
            ]
        return state

    def _load_strict(self) -> object:
        """Never turn a damaged evidence journal into a valid empty journal."""
        if not self.path.exists():
            return self._default()
        try:
            size = self.path.stat().st_size
            if size <= 0 or size > self.MAX_SOURCE_BYTES:
                raise TradingValidationError(
                    "forex_observation: journal_size_invalid"
                )
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise TradingValidationError(
                    "forex_observation: journal_schema_invalid"
                )
            observations = value.get("observations")
            if (
                type(value.get("schema_version")) is not int
                or value.get("schema_version") != 1
                or value.get("mode") != "FOREX_OBSERVATION_ONLY"
                or set(value) != {"schema_version", "mode", "observations"}
                or not isinstance(observations, list)
                or len(observations) > self.MAX_OBSERVATIONS
                or any(not isinstance(item, dict) for item in observations)
            ):
                raise TradingValidationError(
                    "forex_observation: journal_schema_invalid"
                )
            return value
        except TradingValidationError:
            raise
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            RecursionError,
            MemoryError,
        ) as error:
            raise TradingValidationError(
                "forex_observation: journal_source_invalid"
            ) from error


class ForexObservationService:
    """Collect, assess and plan once, stopping before execution."""

    def __init__(
        self,
        project_root: str | Path | None,
        *,
        gateway: ForexReadOnlyDataGateway,
        policy: ForexPaperPolicy | None = None,
        journal: ForexObservationJournal | None = None,
        executor: ForexPaperExecutionEngine | None = None,
    ) -> None:
        self.policy = policy or ForexPaperPolicy()
        self.gateway = gateway
        self.journal = journal or ForexObservationJournal(project_root)
        self.executor = executor or ForexPaperExecutionEngine(
            project_root, policy=self.policy
        )
        self.scanner = ForexMarketScanner(MAJOR_FOREX_PAIRS)
        self.development_scanner = ForexRegimeFilteredScanner(MAJOR_FOREX_PAIRS)
        self.coordinator = ForexPaperCoordinator(self.policy)

    def observe_once(
        self,
        *,
        observation_id: object,
        now: datetime | None = None,
        bundle: Any | None = None,
        capture_origin: object = "MANUAL",
        capture_attestation: object = None,
    ) -> dict[str, Any]:
        selected_id = str(observation_id or "").strip()
        if not _OBSERVATION_ID.fullmatch(selected_id):
            raise TradingValidationError("forex_observation: invalid_id")
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        selected_origin = _capture_origin(capture_origin)
        selected_attestation = _capture_attestation(
            capture_attestation,
            origin=selected_origin,
        )
        positions_before = self.executor.positions()
        try:
            bundle = bundle or self.gateway.collect(now=selected_now)
            source_histories = _canonical_source_histories(bundle.bars)
            sample_contract = build_forex_paper_sample_contract(
                scanner_policy=self.scanner.policy,
                paper_policy=self.policy,
                universe=self.scanner.universe,
            )
            implementation_sha256 = (
                forex_candidate_implementation_sha256()
            )
            all_quotes: dict[str, ForexQuote] = dict(bundle.quotes)
            for quote in bundle.conversion_quotes:
                if quote.pair.symbol in all_quotes:
                    raise TradingValidationError(
                        "forex_observation: duplicate_conversion_quote"
                    )
                all_quotes[quote.pair.symbol] = quote
            rates = ForexRateBook(
                all_quotes.values(),
                now=selected_now,
                max_age_seconds=self.policy.max_conversion_age_seconds,
            )
            positions = positions_before
            diagnostics = self._diagnostics(bundle.diagnostics)
            account = self.executor.status(
                quotes=bundle.quotes,
                rates=rates,
                now=selected_now,
            )
            source_evidence = _source_evidence(
                source_histories,
                quotes=bundle.quotes,
                conversion_quotes=tuple(bundle.conversion_quotes),
                contexts=bundle.contexts,
                positions=positions,
                account=account,
                diagnostics=diagnostics,
                captured_at=selected_now,
            )
            assessments = self.scanner.scan(
                quotes=bundle.quotes,
                bars=source_histories,
                contexts=bundle.contexts,
                positions={
                    symbol: position.side
                    for symbol, position in positions.items()
                },
                now=selected_now,
            )
            plan = self.coordinator.plan(
                assessments=assessments,
                quotes=bundle.quotes,
                positions=positions,
                rates=rates,
                equity_pln=account["equity_pln"],
                daily_pnl_pln=account["daily_pnl_pln"],
                now=selected_now,
            )
            development_assessments = self.development_scanner.scan(
                quotes=bundle.quotes,
                bars=source_histories,
                contexts=bundle.contexts,
                positions={
                    symbol: position.side
                    for symbol, position in positions.items()
                },
                now=selected_now,
            )
            development_plan = self.coordinator.plan(
                assessments=development_assessments,
                quotes=bundle.quotes,
                positions=positions,
                rates=rates,
                equity_pln=account["equity_pln"],
                daily_pnl_pln=account["daily_pnl_pln"],
                now=selected_now,
            )
            development_instructions = list(
                development_plan.get("instructions", []) or []
            )
            market_open = bool(bundle.contexts) and all(
                context.market_open for context in bundle.contexts.values()
            )
            opening_blocks = sorted({
                code
                for context in bundle.contexts.values()
                for code in context.opening_blocks
            })
            opening_blocks_by_pair = {
                pair.symbol: list(bundle.contexts[pair.symbol].opening_blocks)
                for pair in MAJOR_FOREX_PAIRS
                if bundle.contexts[pair.symbol].opening_blocks
            }
            instructions = list(plan.get("instructions", []) or [])
            positions_after = self.executor.positions()
            record = {
                "status": "OBSERVATION_RECORDED",
                "mode": "FOREX_OBSERVATION_ONLY",
                "observation_schema_version": _OBSERVATION_SCHEMA_VERSION,
                "observation_id": selected_id,
                "observed_at": selected_now.isoformat(),
                "capture_origin": selected_origin,
                "capture_attestation": selected_attestation,
                "captured_at": selected_now.isoformat(),
                "source_cycle_id": selected_id,
                "source_evidence": source_evidence,
                "market_open": market_open,
                "fully_cross_checked": (
                    len(diagnostics["cross_checked_pairs"])
                    == len(MAJOR_FOREX_PAIRS)
                    and set(diagnostics["cross_checked_pairs"])
                    == {pair.symbol for pair in MAJOR_FOREX_PAIRS}
                    and all(
                        context.independent_source_count >= 2
                        for context in bundle.contexts.values()
                    )
                ),
                "opening_blocks": opening_blocks,
                "opening_blocks_by_pair": opening_blocks_by_pair,
                "data": diagnostics,
                "assessments": [item.as_dict() for item in assessments],
                "proposed_plan": plan,
                "development_candidate_v2": {
                    "status": "FORWARD_OBSERVATION_RECORDED",
                    "candidate_id": (
                        self.development_scanner.candidate_policy.candidate_id
                    ),
                    "policy_fingerprint_sha256": (
                        self.development_scanner.candidate_policy.fingerprint_sha256
                    ),
                    "implementation_sha256": implementation_sha256,
                    "paper_sample_contract_id": sample_contract["contract_id"],
                    "paper_sample_contract_fingerprint_sha256": (
                        sample_contract["fingerprint_sha256"]
                    ),
                    "forward_eligible": (
                        self.development_scanner.candidate_policy.forward_eligible(
                            selected_now
                        )
                    ),
                    "audit": self.development_scanner.audit(),
                    "assessments": [
                        item.as_dict() for item in development_assessments
                    ],
                    "proposed_plan": development_plan,
                    "proposed_instruction_count": len(
                        development_instructions
                    ),
                    "would_open_count": sum(
                        str(item.get("action", "")).startswith("OPEN_")
                        for item in development_instructions
                    ),
                    "would_close_count": sum(
                        item.get("action") == "CLOSE_POSITION"
                        for item in development_instructions
                    ),
                    "execution": {
                        "status": "NOT_EXECUTED",
                        "reason": "DEVELOPMENT_OBSERVATION_ONLY",
                    },
                    "automatic_paper_promotion": False,
                    "paper_orders_sent": False,
                    "live_orders_sent": False,
                },
                "proposed_instruction_count": len(instructions),
                "would_open_count": sum(
                    str(item.get("action", "")).startswith("OPEN_")
                    for item in instructions
                ),
                "would_close_count": sum(
                    item.get("action") == "CLOSE_POSITION"
                    for item in instructions
                ),
                "execution": {
                    "status": "NOT_EXECUTED",
                    "reason": "OBSERVATION_ONLY",
                },
                "position_count_before": len(positions_before),
                "position_count_after": len(positions_after),
                "positions_unchanged": positions_before == positions_after,
                "paper_orders_sent": False,
                "live_orders_sent": False,
                "order_network_access": False,
                "market_data_network_access": True,
            }
        except Exception as error:
            if not isinstance(error, (TradingValidationError, OSError, RuntimeError)):
                raise
            positions_after = self.executor.positions()
            record = self._blocked(
                selected_id,
                selected_now,
                _safe_reason(error),
                capture_origin=selected_origin,
                capture_attestation=selected_attestation,
                before=len(positions_before),
                after=len(positions_after),
                unchanged=positions_before == positions_after,
            )
        if not record["positions_unchanged"]:
            raise TradingValidationError("forex_observation: position_state_changed")
        return self.journal.record(record)

    @staticmethod
    def _diagnostics(value: Mapping[str, object]) -> dict[str, object]:
        cross_checked = tuple(
            str(item)
            for item in list(value.get("cross_checked_pairs", ()) or ())
        )
        return {
            "primary_provider": str(value.get("primary_provider", "")),
            "primary_pair_count": int(value.get("primary_pair_count", 0) or 0),
            "primary_closed_bar_count": int(
                value.get("primary_closed_bar_count", 0) or 0
            ),
            "cross_checked_pair_count": len(cross_checked),
            "cross_checked_pairs": list(cross_checked),
            "calendar_ready": bool(value.get("calendar_ready")),
            "high_impact_event_count": int(
                value.get("high_impact_event_count", 0) or 0
            ),
            "nbp_effective_date": str(value.get("nbp_effective_date", "")),
            "pln_conversion_ready": bool(value.get("pln_conversion_ready")),
        }

    @staticmethod
    def _blocked(
        observation_id: str,
        now: datetime,
        reason: str,
        *,
        capture_origin: str,
        capture_attestation: Mapping[str, Any],
        before: int,
        after: int,
        unchanged: bool,
    ) -> dict[str, Any]:
        return {
            "status": "DATA_BLOCKED",
            "mode": "FOREX_OBSERVATION_ONLY",
            "observation_schema_version": _OBSERVATION_SCHEMA_VERSION,
            "observation_id": observation_id,
            "observed_at": now.isoformat(),
            "capture_origin": capture_origin,
            "capture_attestation": dict(capture_attestation),
            "captured_at": now.isoformat(),
            "source_cycle_id": observation_id,
            "market_open": False,
            "fully_cross_checked": False,
            "opening_blocks": [reason],
            "opening_blocks_by_pair": {},
            "data": {},
            "assessments": [],
            "proposed_plan": {},
            "proposed_instruction_count": 0,
            "would_open_count": 0,
            "would_close_count": 0,
            "execution": {"status": "NOT_EXECUTED", "reason": reason},
            "position_count_before": before,
            "position_count_after": after,
            "positions_unchanged": unchanged,
            "paper_orders_sent": False,
            "live_orders_sent": False,
            "order_network_access": False,
            "market_data_network_access": True,
        }


__all__ = [
    "ForexObservationJournal",
    "ForexObservationService",
    "forex_candidate_implementation_sha256",
]
