"""Read-only attribution of actual V1 PAPER outcomes to frozen V2 cohorts."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.trading.forex_candidate_v2 import ForexRegimeCandidatePolicy
from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_models import MAJOR_FOREX_PAIRS
from app.trading.forex_observation import ForexObservationJournal
from app.trading.forex_paper_performance import ForexPaperPerformancePolicy


_MONEY = Decimal("0.01")
_PERCENT = Decimal("0.01")
_RATIO = Decimal("0.0001")


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite() or abs(result) > Decimal("1000000000000"):
        return None
    return result


def _text(value: Decimal, quantum: Decimal = _MONEY) -> str:
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


def _instructions(value: object) -> list[dict[str, Any]]:
    plan = dict(value) if isinstance(value, Mapping) else {}
    raw = plan.get("instructions", [])
    return [dict(item) for item in raw if isinstance(item, Mapping)] \
        if isinstance(raw, (list, tuple)) else []


def _same_number(left: object, right: object) -> bool:
    left_value = _decimal(left)
    right_value = _decimal(right)
    return (
        left_value is not None
        and right_value is not None
        and left_value == right_value
    )


def _matches_open(fill: Mapping[str, Any], instruction: Mapping[str, Any]) -> bool:
    if str(fill.get("action", "")) != str(instruction.get("action", "")):
        return False
    if str(fill.get("pair", "")) != str(instruction.get("pair", "")):
        return False
    for fill_key, instruction_key in (
        ("units", "units"),
        ("entry_price", "intended_price"),
        ("stop_loss", "stop_loss"),
        ("take_profit", "take_profit"),
    ):
        if not _same_number(fill.get(fill_key), instruction.get(instruction_key)):
            return False
    return True


def _cohort_summary(
    outcomes: Iterable[Decimal],
    *,
    open_signal_count: int,
    current_open_position_count: int,
) -> dict[str, Any]:
    values = tuple(outcomes)
    profits = tuple(value for value in values if value > 0)
    losses = tuple(value for value in values if value < 0)
    net = sum(values, Decimal("0"))
    gross_profit = sum(profits, Decimal("0"))
    gross_loss = abs(sum(losses, Decimal("0")))
    required = ForexPaperPerformancePolicy().minimum_closed_trades_for_review
    average = net / Decimal(len(values)) if values else Decimal("0")
    win_rate = (
        Decimal(len(profits)) * 100 / Decimal(len(values))
        if values
        else Decimal("0")
    )
    return {
        "open_signal_count": open_signal_count,
        "closed_trade_count": len(values),
        "current_open_position_count": current_open_position_count,
        "winning_trade_count": len(profits),
        "losing_trade_count": len(losses),
        "breakeven_trade_count": len(values) - len(profits) - len(losses),
        "win_rate_pct": _text(win_rate, _PERCENT),
        "net_realized_pnl_pln": _text(net),
        "average_trade_pnl_pln": _text(average),
        "profit_factor": (
            _text(gross_profit / gross_loss, _RATIO)
            if gross_loss > 0
            else None
        ),
        "minimum_closed_trades_for_review": required,
        "remaining_closed_trades_for_review": max(0, required - len(values)),
        "sample_size_sufficient_for_review": len(values) >= required,
        "performance_validated": False,
    }


def build_forex_strategy_cohort_review(
    paper_state: Mapping[str, Any],
    observation_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Group actual V1 outcomes by the frozen V2 entry decision."""

    policy = ForexRegimeCandidatePolicy()
    valid_pairs = {pair.symbol for pair in MAJOR_FOREX_PAIRS}
    issues: Counter[str] = Counter()
    exclusions: Counter[str] = Counter()
    paper_audit_valid = ForexPaperLedger.verify_audit(dict(paper_state))
    observation_audit_valid = ForexObservationJournal.verify(observation_state)

    observations_by_time: dict[str, dict[str, Any]] = {}
    for raw in list(observation_state.get("observations", []) or []):
        if not isinstance(raw, Mapping):
            issues.update(("INVALID_OBSERVATION_RECORD",))
            continue
        observation = dict(raw)
        if observation.get("status") != "OBSERVATION_RECORDED":
            continue
        observed_at = str(observation.get("observed_at", ""))
        if not observed_at:
            issues.update(("OBSERVATION_TIME_MISSING",))
        elif observed_at in observations_by_time:
            issues.update(("DUPLICATE_OBSERVATION_TIME",))
        else:
            observations_by_time[observed_at] = observation

    cohort_outcomes: dict[str, list[Decimal]] = {
        "V1_ALL": [],
        "V2_RETAINED": [],
        "V2_FILTERED": [],
    }
    open_signal_counts: Counter[str] = Counter()
    open_positions: dict[str, dict[str, Any]] = {}
    seen_fill_ids: set[str] = set()
    eligible_open_count = 0
    excluded_open_count = 0
    attributed_close_count = 0

    for raw in list(paper_state.get("fills", []) or []):
        if not isinstance(raw, Mapping):
            issues.update(("INVALID_FILL_RECORD",))
            continue
        fill = dict(raw)
        fill_id = str(fill.get("fill_id", ""))
        action = str(fill.get("action", "")).strip().upper()
        pair = str(fill.get("pair", "")).strip().upper()
        if not fill_id or fill_id in seen_fill_ids:
            issues.update(("DUPLICATE_OR_MISSING_FILL_ID",))
            continue
        seen_fill_ids.add(fill_id)
        if pair not in valid_pairs:
            issues.update(("INVALID_FILL_PAIR",))
            continue

        if action in {"OPEN_LONG", "OPEN_SHORT"}:
            if pair in open_positions:
                issues.update(("OVERLAPPING_PAIR_POSITION",))
                continue
            filled_at = str(fill.get("filled_at", ""))
            observation = observations_by_time.get(filled_at)
            if observation is None:
                issues.update(("OPEN_OBSERVATION_NOT_FOUND",))
                continue
            candidate = observation.get("development_candidate_v2")
            candidate = dict(candidate) if isinstance(candidate, Mapping) else {}
            if candidate.get("forward_eligible") is not True:
                open_positions[pair] = {"cohort": "EXCLUDED", "fill": fill}
                excluded_open_count += 1
                exclusions.update(("NOT_FORWARD_ELIGIBLE",))
                continue
            candidate_contract_valid = bool(
                candidate.get("candidate_id") == policy.candidate_id
                and candidate.get("policy_fingerprint_sha256")
                == policy.fingerprint_sha256
                and candidate.get("automatic_paper_promotion") is False
                and candidate.get("paper_orders_sent") is False
                and candidate.get("live_orders_sent") is False
                and isinstance(candidate.get("execution"), Mapping)
                and candidate["execution"].get("status") == "NOT_EXECUTED"
            )
            if not candidate_contract_valid:
                issues.update(("CANDIDATE_CONTRACT_INVALID",))
                continue
            base_matches = [
                instruction
                for instruction in _instructions(observation.get("proposed_plan"))
                if _matches_open(fill, instruction)
            ]
            if len(base_matches) != 1:
                issues.update(("BASE_OPEN_INSTRUCTION_MISMATCH",))
                continue
            candidate_matches = [
                instruction
                for instruction in _instructions(candidate.get("proposed_plan"))
                if _matches_open(fill, instruction)
            ]
            if len(candidate_matches) > 1:
                issues.update(("DUPLICATE_CANDIDATE_OPEN_INSTRUCTION",))
                continue
            cohort = "V2_RETAINED" if candidate_matches else "V2_FILTERED"
            open_positions[pair] = {"cohort": cohort, "fill": fill}
            eligible_open_count += 1
            open_signal_counts.update(("V1_ALL", cohort))
            continue

        if action in {"CLOSE_LONG", "CLOSE_SHORT"}:
            opened = open_positions.pop(pair, None)
            if opened is None:
                issues.update(("CLOSE_WITHOUT_ATTRIBUTED_OPEN",))
                continue
            expected_close = (
                "CLOSE_LONG"
                if opened["fill"].get("action") == "OPEN_LONG"
                else "CLOSE_SHORT"
            )
            if action != expected_close:
                issues.update(("CLOSE_SIDE_MISMATCH",))
                continue
            cohort = str(opened.get("cohort", ""))
            if cohort == "EXCLUDED":
                continue
            pnl = _decimal(fill.get("realized_pnl_pln"))
            if pnl is None:
                issues.update(("INVALID_CLOSE_PNL",))
                continue
            cohort_outcomes["V1_ALL"].append(pnl)
            cohort_outcomes[cohort].append(pnl)
            attributed_close_count += 1
            continue

        issues.update(("UNSUPPORTED_FILL_ACTION",))

    current_open_counts: Counter[str] = Counter()
    for opened in open_positions.values():
        cohort = str(opened.get("cohort", ""))
        if cohort in {"V2_RETAINED", "V2_FILTERED"}:
            current_open_counts.update(("V1_ALL", cohort))

    evidence_valid = bool(
        paper_audit_valid
        and observation_audit_valid
        and not issues
    )
    return {
        "status": "READY" if evidence_valid else "BLOCKED_INVALID_EVIDENCE",
        "mode": "FOREX_STRATEGY_COHORT_REVIEW_ONLY",
        "candidate_id": policy.candidate_id,
        "policy_fingerprint_sha256": policy.fingerprint_sha256,
        "comparison_scope": (
            "ACTUAL_V1_OUTCOMES_GROUPED_BY_FROZEN_V2_ENTRY_DECISION"
        ),
        "eligible_open_fill_count": eligible_open_count,
        "excluded_open_fill_count": excluded_open_count,
        "attributed_close_fill_count": attributed_close_count,
        "cohorts": {
            name: _cohort_summary(
                cohort_outcomes[name],
                open_signal_count=open_signal_counts[name],
                current_open_position_count=current_open_counts[name],
            )
            for name in ("V1_ALL", "V2_RETAINED", "V2_FILTERED")
        },
        "integrity": {
            "evidence_valid": evidence_valid,
            "paper_audit_valid": paper_audit_valid,
            "observation_audit_valid": observation_audit_valid,
            "issues": dict(sorted(issues.items())),
            "exclusions": dict(sorted(exclusions.items())),
        },
        "counterfactual_v2_portfolio_simulated": False,
        "strategy_performance_validated": False,
        "automatic_paper_strategy_change": False,
        "live_promotion_ready": False,
        "automatic_live_promotion": False,
    }


class ForexStrategyCohortReview:
    """Load both tamper-evident journals and build a read-only comparison."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.paper = ForexPaperLedger(project_root)
        self.observations = ForexObservationJournal(project_root)

    def review(self) -> dict[str, Any]:
        return build_forex_strategy_cohort_review(
            self.paper.snapshot(),
            self.observations.snapshot(),
        )


__all__ = [
    "ForexStrategyCohortReview",
    "build_forex_strategy_cohort_review",
]
