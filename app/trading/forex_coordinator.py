"""Turn validated Forex assessments into paper-only portfolio instructions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

from app.trading.forex_models import ForexPosition, ForexQuote
from app.trading.forex_risk import (
    ForexPaperPolicy,
    ForexPortfolioRiskEngine,
    ForexRateBook,
)
from app.trading.forex_scanner import ForexPairAssessment
from app.trading.models import TradingValidationError, aware_utc
from app.trading.paper_broker import LiveTradingBlockedError


@dataclass(frozen=True, slots=True)
class ForexPaperInstruction:
    action: str
    pair: str
    units: Decimal
    intended_price: Decimal
    stop_loss: Decimal
    score: Decimal
    reason_codes: tuple[str, ...]
    take_profit: Decimal | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "pair": self.pair,
            "units": str(self.units),
            "intended_price": str(self.intended_price),
            "stop_loss": str(self.stop_loss),
            "take_profit": (
                str(self.take_profit) if self.take_profit is not None else ""
            ),
            "score": str(self.score),
            "reason_codes": list(self.reason_codes),
            "mode": "FOREX_PAPER_ONLY",
        }


class ForexPaperCoordinator:
    """Prioritize exits, then select only risk-approved paper entries."""

    MINIMUM_STOP_PIPS = Decimal("10")
    MAXIMUM_STOP_PIPS = Decimal("100")

    def __init__(self, policy: ForexPaperPolicy | None = None) -> None:
        self.policy = policy or ForexPaperPolicy()
        self.risk = ForexPortfolioRiskEngine(self.policy)

    def plan(
        self,
        *,
        assessments: Iterable[ForexPairAssessment],
        quotes: Mapping[str, ForexQuote],
        positions: Mapping[str, ForexPosition],
        rates: ForexRateBook,
        equity_pln: object,
        daily_pnl_pln: object,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        ordered = tuple(assessments)
        current = dict(positions)
        exits: list[ForexPaperInstruction] = []
        rejected: list[dict[str, Any]] = []
        exit_pairs: set[str] = set()
        assessment_by_pair = {
            assessment.pair.symbol: assessment for assessment in ordered
        }
        for symbol, position in current.items():
            assessment = assessment_by_pair.get(symbol)
            quote = quotes.get(symbol)
            if quote is None or quote.pair != position.pair:
                continue
            stop_hit = (
                position.side == "LONG" and quote.bid <= position.stop_loss
            ) or (
                position.side == "SHORT" and quote.ask >= position.stop_loss
            )
            target_hit = position.take_profit is not None and (
                (position.side == "LONG" and quote.bid >= position.take_profit)
                or (position.side == "SHORT" and quote.ask <= position.take_profit)
            )
            if not stop_hit and not target_hit:
                continue
            closing_price = quote.bid if position.side == "LONG" else quote.ask
            reason = "STOP_LOSS_TRIGGERED" if stop_hit else "TAKE_PROFIT_TRIGGERED"
            exits.append(ForexPaperInstruction(
                action="CLOSE_POSITION",
                pair=symbol,
                units=position.units,
                intended_price=closing_price,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                score=Decimal("100"),
                reason_codes=(reason,),
            ))
            exit_pairs.add(symbol)
        for assessment in ordered:
            if not assessment.should_close:
                continue
            if assessment.pair.symbol in exit_pairs:
                continue
            position = current.get(assessment.pair.symbol)
            quote = quotes.get(assessment.pair.symbol)
            if position is None or quote is None or quote.pair != assessment.pair:
                rejected.append({
                    "pair": assessment.pair.symbol,
                    "code": "CLOSE_STATE_MISMATCH",
                })
                continue
            closing_price = quote.bid if position.side == "LONG" else quote.ask
            exits.append(ForexPaperInstruction(
                action="CLOSE_POSITION",
                pair=assessment.pair.symbol,
                units=position.units,
                intended_price=closing_price,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                score=assessment.score,
                reason_codes=assessment.reason_codes,
            ))
            exit_pairs.add(assessment.pair.symbol)
        if exits:
            return self._result(
                "CLOSES_READY",
                ordered,
                exits,
                rejected,
                selected_now,
            )

        working = list(current.values())
        entries: list[ForexPaperInstruction] = []
        candidates = sorted(
            (assessment for assessment in ordered if assessment.can_open),
            key=lambda item: (-item.score, item.pair.symbol),
        )
        for assessment in candidates:
            quote = quotes.get(assessment.pair.symbol)
            if quote is None or quote.pair != assessment.pair:
                rejected.append({
                    "pair": assessment.pair.symbol,
                    "code": "OPEN_QUOTE_MISSING",
                })
                continue
            side = "LONG" if assessment.action == "OPEN_LONG" else "SHORT"
            entry = quote.ask if side == "LONG" else quote.bid
            volatility_distance = (
                assessment.volatility_pct / Decimal("100")
            ) * entry * Decimal("2")
            minimum = assessment.pair.pip_size * self.MINIMUM_STOP_PIPS
            maximum = assessment.pair.pip_size * self.MAXIMUM_STOP_PIPS
            stop_distance = min(max(volatility_distance, minimum), maximum)
            stop = entry - stop_distance if side == "LONG" else entry + stop_distance
            target_distance = stop_distance * self.policy.take_profit_reward_risk
            target = (
                entry + target_distance
                if side == "LONG"
                else entry - target_distance
            )
            decision = self.risk.evaluate_open(
                pair=assessment.pair,
                side=side,
                entry_price=entry,
                stop_loss=stop,
                equity_pln=equity_pln,
                daily_pnl_pln=daily_pnl_pln,
                positions=working,
                rates=rates,
                now=selected_now,
            )
            if not decision.allowed:
                rejected.append({
                    "pair": assessment.pair.symbol,
                    "code": decision.code,
                })
                continue
            instruction = ForexPaperInstruction(
                action=f"OPEN_{side}",
                pair=assessment.pair.symbol,
                units=decision.units,
                intended_price=entry,
                stop_loss=stop,
                take_profit=target,
                score=assessment.score,
                reason_codes=assessment.reason_codes + (decision.code,),
            )
            entries.append(instruction)
            working.append(ForexPosition(
                pair=assessment.pair,
                side=side,
                units=decision.units,
                entry_price=entry,
                current_price=entry,
                stop_loss=stop,
                opened_at=selected_now,
                take_profit=target,
            ))
            if len(working) >= self.policy.max_open_positions:
                break
        status = "ENTRIES_READY" if entries else "NO_ACTION"
        return self._result(
            status,
            ordered,
            entries,
            rejected,
            selected_now,
        )

    @staticmethod
    def _result(
        status: str,
        assessments: tuple[ForexPairAssessment, ...],
        instructions: list[ForexPaperInstruction],
        rejected: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "mode": "FOREX_PAPER_ONLY",
            "assessed_at": now.isoformat(),
            "pair_count": len(assessments),
            "instructions": [item.as_dict() for item in instructions],
            "rejected": rejected,
            "live_orders_sent": False,
            "network_access": False,
        }

    @staticmethod
    def submit_live_order(*_args: object, **_kwargs: object) -> None:
        raise LiveTradingBlockedError(
            "LIVE_TRADING_BLOCKED: koordynator Forex działa wyłącznie PAPER_ONLY."
        )


__all__ = ["ForexPaperCoordinator", "ForexPaperInstruction"]
