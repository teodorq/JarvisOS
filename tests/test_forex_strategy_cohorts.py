from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from app.trading.forex_candidate_v2 import ForexRegimeCandidatePolicy
from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_observation import ForexObservationJournal
from app.trading.forex_strategy_cohorts import ForexStrategyCohortReview


UTC = timezone.utc


def _open_fill(pair: str, at: str, *, side: str = "SHORT") -> dict:
    price = "0.800000" if pair == "USD_CHF" else "159.000000"
    stop = "0.801000" if pair == "USD_CHF" else "159.100000"
    target = "0.798000" if pair == "USD_CHF" else "158.800000"
    return {
        "fill_id": f"fill-open-{pair}",
        "action": f"OPEN_{side}",
        "pair": pair,
        "side": side,
        "units": "1000",
        "entry_price": price,
        "stop_loss": stop,
        "take_profit": target,
        "realized_pnl_pln": "0.00",
        "filled_at": at,
    }


def _instruction(fill: dict) -> dict:
    return {
        "action": fill["action"],
        "pair": fill["pair"],
        "units": fill["units"],
        "intended_price": fill["entry_price"],
        "stop_loss": fill["stop_loss"],
        "take_profit": fill["take_profit"],
        "mode": "FOREX_PAPER_ONLY",
    }


def _candidate(fill: dict, *, retained: bool, valid: bool = True) -> dict:
    policy = ForexRegimeCandidatePolicy()
    return {
        "candidate_id": policy.candidate_id,
        "policy_fingerprint_sha256": (
            policy.fingerprint_sha256 if valid else "invalid"
        ),
        "forward_eligible": True,
        "proposed_plan": {
            "instructions": [_instruction(fill)] if retained else [],
        },
        "execution": {"status": "NOT_EXECUTED"},
        "automatic_paper_promotion": False,
        "paper_orders_sent": False,
        "live_orders_sent": False,
    }


def _record_observation(
    journal: ForexObservationJournal,
    fill: dict,
    *,
    retained: bool,
    valid: bool = True,
    forward: bool = True,
) -> None:
    candidate = _candidate(fill, retained=retained, valid=valid)
    candidate["forward_eligible"] = forward
    stamp = "".join(
        character
        for character in str(fill["filled_at"])
        if character.isalnum()
    )
    journal.record({
        "status": "OBSERVATION_RECORDED",
        "mode": "FOREX_OBSERVATION_ONLY",
        "observation_id": f"observation-{fill['pair']}-{stamp}",
        "observed_at": fill["filled_at"],
        "proposed_plan": {"instructions": [_instruction(fill)]},
        "development_candidate_v2": candidate,
        "paper_orders_sent": False,
        "live_orders_sent": False,
    })


def _record_cycle(ledger: ForexPaperLedger, fill: dict) -> None:
    created_at = datetime.fromisoformat(str(fill["filled_at"])).astimezone(UTC)

    def operation(state: dict) -> None:
        state["fills"] = list(state.get("fills", [])) + [fill]
        if str(fill["action"]).startswith("CLOSE_"):
            state["balance_pln"] = str(
                Decimal(str(state["balance_pln"]))
                + Decimal(str(fill["realized_pnl_pln"]))
            )
        ledger.append_event(
            state,
            "FOREX_PAPER_CYCLE",
            {"executions": [fill], "balance_pln": state["balance_pln"]},
            created_at=created_at,
        )

    ledger.transaction(operation)


def test_review_groups_actual_v1_outcomes_by_frozen_v2_decision() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        paper = ForexPaperLedger(root)
        observations = ForexObservationJournal(root)
        retained_at = "2026-08-21T10:00:00+00:00"
        filtered_at = "2026-08-21T11:00:00+00:00"
        retained = _open_fill("USD_CHF", retained_at)
        filtered = _open_fill("USD_JPY", filtered_at)
        closed = {
            **retained,
            "fill_id": "fill-close-USD_CHF",
            "action": "CLOSE_SHORT",
            "realized_pnl_pln": "-10.00",
            "filled_at": "2026-08-21T10:15:00+00:00",
        }
        _record_observation(observations, retained, retained=True)
        _record_observation(observations, filtered, retained=False)
        _record_cycle(paper, retained)
        _record_cycle(paper, closed)
        _record_cycle(paper, filtered)

        review = ForexStrategyCohortReview(root).review()

    assert review["status"] == "READY"
    assert review["eligible_open_fill_count"] == 2
    assert review["attributed_close_fill_count"] == 1
    assert review["integrity"]["evidence_valid"] is True
    baseline = review["cohorts"]["V1_ALL"]
    retained_cohort = review["cohorts"]["V2_RETAINED"]
    filtered_cohort = review["cohorts"]["V2_FILTERED"]
    assert baseline["open_signal_count"] == 2
    assert baseline["closed_trade_count"] == 1
    assert baseline["current_open_position_count"] == 1
    assert baseline["net_realized_pnl_pln"] == "-10.00"
    assert retained_cohort["open_signal_count"] == 1
    assert retained_cohort["closed_trade_count"] == 1
    assert retained_cohort["net_realized_pnl_pln"] == "-10.00"
    assert filtered_cohort["open_signal_count"] == 1
    assert filtered_cohort["closed_trade_count"] == 0
    assert filtered_cohort["current_open_position_count"] == 1
    assert review["counterfactual_v2_portfolio_simulated"] is False
    assert review["strategy_performance_validated"] is False
    assert review["live_promotion_ready"] is False


def test_invalid_candidate_contract_blocks_attribution() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        fill = _open_fill("USD_CHF", "2026-08-21T10:00:00+00:00")
        _record_observation(
            ForexObservationJournal(root),
            fill,
            retained=True,
            valid=False,
        )
        _record_cycle(ForexPaperLedger(root), fill)

        review = ForexStrategyCohortReview(root).review()

    assert review["status"] == "BLOCKED_INVALID_EVIDENCE"
    assert review["integrity"]["issues"] == {
        "CANDIDATE_CONTRACT_INVALID": 1,
    }
    assert review["integrity"]["evidence_valid"] is False


def test_non_forward_open_is_excluded_without_invalidating_review() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        fill = _open_fill("USD_CHF", "2026-08-20T10:00:00+00:00")
        _record_observation(
            ForexObservationJournal(root),
            fill,
            retained=False,
            forward=False,
        )
        _record_cycle(ForexPaperLedger(root), fill)

        review = ForexStrategyCohortReview(root).review()

    assert review["status"] == "READY"
    assert review["eligible_open_fill_count"] == 0
    assert review["excluded_open_fill_count"] == 1
    assert review["integrity"]["exclusions"] == {
        "NOT_FORWARD_ELIGIBLE": 1,
    }
