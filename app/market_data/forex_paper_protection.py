"""Fast local stop-loss/take-profit guard for existing Forex PAPER positions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
from pathlib import Path
from typing import Any, Iterable, Protocol

from app.market_data.forex_environment import ForexDataSettings
from app.market_data.mt5_demo import (
    Mt5DemoReadOnlySource,
    mt5_market_snapshot_fresh,
)
from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    ForexPosition,
    ForexQuote,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.forex_risk import ForexRateBook
from app.trading.models import TradingValidationError, aware_utc


class _QuoteSource(Protocol):
    def fetch_market(
        self,
        pairs: Iterable[ForexPair],
        *,
        bar_count: int = 31,
        timeframe_minutes: int = 15,
        now: datetime | None = None,
    ) -> tuple[dict[str, ForexQuote], dict[str, tuple[ForexBar, ...]]]: ...


class ForexPaperProtectionRuntime:
    """Close an existing PAPER position on SL/TP; never create an entry."""

    RECOVERY_TIMEFRAME_MINUTES = 1
    MAX_RECOVERY_BAR_COUNT = 10_080

    def __init__(
        self,
        project_root: str | Path | None,
        *,
        settings: ForexDataSettings,
        source: _QuoteSource | None = None,
        executor: ForexPaperExecutionEngine | None = None,
    ) -> None:
        self.project_root = project_root
        self.settings = settings
        self.source = source or Mt5DemoReadOnlySource(
            symbol_suffix=settings.mt5_symbol_suffix
        )
        self.executor = executor or ForexPaperExecutionEngine(project_root)
        self.coordinator = ForexPaperCoordinator(policy=self.executor.policy)

    def run_once(
        self,
        *,
        cycle_id: object,
        now: datetime | None = None,
        recovery_since: datetime | None = None,
    ) -> dict[str, Any]:
        selected_id = str(cycle_id or "").strip()
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        if not self.settings.paper_autopilot_enabled:
            return self._blocked(
                selected_id,
                "PAPER_AUTOPILOT_NOT_ENABLED",
                selected_now,
            )
        if self.settings.primary_provider != "MT5_DEMO":
            return self._blocked(
                selected_id,
                "MT5_DEMO_PRIMARY_REQUIRED",
                selected_now,
            )
        try:
            positions = self.executor.positions()
            if not positions:
                return self._result(
                    "NO_OPEN_POSITIONS",
                    selected_id,
                    selected_now,
                    execution=None,
                    account=self.executor.status(now=selected_now),
                    recovery_replay={
                        "status": "NO_OPEN_POSITIONS",
                        "timeframe": "M1_CLOSED_BARS",
                        "historical_exit_count": 0,
                        "coverage_complete": True,
                    },
                )
            checkpoint = self._recovery_checkpoint(
                recovery_since,
                selected_now,
            )
            effective_start = min(
                max(position.opened_at, checkpoint)
                if checkpoint is not None
                else position.opened_at
                for position in positions.values()
            )
            bar_count = self._recovery_bar_count(
                effective_start,
                selected_now,
            )
            requested_pairs = self._requested_pairs(positions.values())
            quotes, bars = self.source.fetch_market(
                requested_pairs,
                bar_count=bar_count,
                timeframe_minutes=self.RECOVERY_TIMEFRAME_MINUTES,
                now=selected_now,
            )
            if any(
                len(tuple(bars.get(pair.symbol, ()))) != bar_count
                for pair in requested_pairs
            ):
                return self._blocked(
                    selected_id,
                    "MT5_PROTECTION_HISTORY_INCOMPLETE",
                    selected_now,
                )
            if not mt5_market_snapshot_fresh(
                requested_pairs,
                quotes,
                bars,
                now=selected_now,
            ):
                return self._blocked(
                    selected_id,
                    "MT5_PROTECTION_DATA_STALE",
                    selected_now,
                )
            rates = ForexRateBook(quotes.values(), now=selected_now)
            account = self.executor.status(
                quotes=quotes,
                rates=rates,
                now=selected_now,
            )
            (
                replay_instructions,
                replay_quotes,
                recovery_replay,
            ) = self._recovery_instructions(
                positions=positions,
                quotes=quotes,
                bars=bars,
                checkpoint=checkpoint,
                effective_start=effective_start,
                requested_bar_count=bar_count,
                now=selected_now,
            )
            replay_pairs = {
                str(item.get("pair", "")) for item in replay_instructions
            }
            current_plan = self.coordinator.plan(
                assessments=(),
                quotes=quotes,
                positions={
                    symbol: position
                    for symbol, position in positions.items()
                    if symbol not in replay_pairs
                },
                rates=rates,
                equity_pln=account.get("equity_pln", "0"),
                daily_pnl_pln=account.get("daily_pnl_pln", "0"),
                now=selected_now,
            )
            current_instructions = list(
                current_plan.get("instructions", []) or []
            )
            instructions = replay_instructions + current_instructions
            plan = {
                **current_plan,
                "status": "CLOSES_READY" if instructions else "NO_ACTION",
                "instructions": instructions,
            }
            if any(
                not isinstance(item, dict)
                or item.get("action") != "CLOSE_POSITION"
                for item in instructions
            ):
                return self._blocked(
                    selected_id,
                    "PROTECTION_PLAN_NOT_CLOSE_ONLY",
                    selected_now,
                )
            if not instructions:
                return self._result(
                    "NO_PROTECTION_TRIGGER",
                    selected_id,
                    selected_now,
                    execution=None,
                    account=account,
                    recovery_replay=recovery_replay,
                )
            execution_quotes = dict(quotes)
            execution_quotes.update(replay_quotes)
            execution_rates = ForexRateBook(
                execution_quotes.values(),
                now=selected_now,
            )
            execution = self.executor.apply_plan(
                plan,
                quotes=execution_quotes,
                rates=execution_rates,
                cycle_id=selected_id,
                now=selected_now,
            )
            return self._result(
                "PAPER_PROTECTION_APPLIED",
                selected_id,
                selected_now,
                execution=execution,
                account=self.executor.status(now=selected_now),
                recovery_replay=recovery_replay,
            )
        except (OSError, RuntimeError, TradingValidationError) as error:
            return self._blocked(
                selected_id,
                str(error)[:160] or "PAPER_PROTECTION_FAILED",
                selected_now,
            )

    @staticmethod
    def _requested_pairs(
        positions: Iterable[ForexPosition],
    ) -> tuple[ForexPair, ...]:
        unique = {position.pair.symbol: position.pair for position in positions}
        unique[USD_PLN_CONVERSION_PAIR.symbol] = USD_PLN_CONVERSION_PAIR
        return tuple(unique[symbol] for symbol in sorted(unique))

    @staticmethod
    def _recovery_checkpoint(
        recovery_since: datetime | None,
        now: datetime,
    ) -> datetime | None:
        if recovery_since is None:
            return None
        checkpoint = aware_utc(recovery_since, "recovery_since")
        if (checkpoint - now).total_seconds() > 2:
            raise TradingValidationError(
                "forex_protection: recovery_checkpoint_in_future"
            )
        return checkpoint

    @classmethod
    def _recovery_bar_count(cls, start: datetime, now: datetime) -> int:
        elapsed = max(0, (now - start).total_seconds())
        requested = max(2, math.ceil(elapsed / 60) + 2)
        if requested > cls.MAX_RECOVERY_BAR_COUNT:
            raise TradingValidationError(
                "forex_protection: recovery_window_exceeded"
            )
        return requested

    def _recovery_instructions(
        self,
        *,
        positions: dict[str, ForexPosition],
        quotes: dict[str, ForexQuote],
        bars: dict[str, tuple[ForexBar, ...]],
        checkpoint: datetime | None,
        effective_start: datetime,
        requested_bar_count: int,
        now: datetime,
    ) -> tuple[list[dict[str, Any]], dict[str, ForexQuote], dict[str, Any]]:
        instructions: list[dict[str, Any]] = []
        execution_quotes: dict[str, ForexQuote] = {}
        evidence: list[dict[str, Any]] = []
        examined_bars = 0
        for symbol, position in sorted(positions.items()):
            quote = quotes.get(symbol)
            series = tuple(bars.get(symbol, ()))
            if quote is None or quote.pair != position.pair:
                raise TradingValidationError(
                    "forex_protection: recovery_quote_missing"
                )
            start = (
                max(position.opened_at, checkpoint)
                if checkpoint is not None
                else position.opened_at
            )
            trigger, examined = self._find_recovery_exit(
                position=position,
                quote=quote,
                bars=series,
                start=start,
                now=now,
            )
            examined_bars += examined
            if trigger is None:
                continue
            instructions.append({
                "action": "CLOSE_POSITION",
                "pair": symbol,
                "units": str(position.units),
                "intended_price": str(trigger["exit_price"]),
                "stop_loss": str(position.stop_loss),
                "take_profit": (
                    str(position.take_profit)
                    if position.take_profit is not None
                    else ""
                ),
                "score": "100",
                "reason_codes": list(trigger["reason_codes"]),
                "protection_replay": {
                    "timeframe": "M1_CLOSED_BARS",
                    "bar_timestamp": trigger["bar_timestamp"].isoformat(),
                    "trigger": trigger["trigger"],
                    "ambiguous_bar": trigger["ambiguous_bar"],
                    "spread_policy": "CURRENT_MT5_SPREAD",
                },
                "mode": "FOREX_PAPER_ONLY",
            })
            execution_quotes[symbol] = self._execution_quote(
                position,
                quote,
                trigger["exit_price"],
                now,
            )
            evidence.append({
                "pair": symbol,
                "bar_timestamp": trigger["bar_timestamp"].isoformat(),
                "exit_price": str(trigger["exit_price"]),
                "trigger": trigger["trigger"],
                "ambiguous_bar": trigger["ambiguous_bar"],
            })
        return instructions, execution_quotes, {
            "status": (
                "RECOVERY_REPLAY_APPLIED"
                if instructions
                else "RECOVERY_REPLAY_CLEAR"
            ),
            "timeframe": "M1_CLOSED_BARS",
            "checkpoint_at": checkpoint.isoformat() if checkpoint else "",
            "effective_start_at": effective_start.isoformat(),
            "requested_bar_count": requested_bar_count,
            "examined_position_count": len(positions),
            "examined_bar_count": examined_bars,
            "historical_exit_count": len(instructions),
            "ambiguous_bar_count": sum(
                item["ambiguous_bar"] is True for item in evidence
            ),
            "ambiguous_bar_policy": "STOP_FIRST_CONSERVATIVE",
            "spread_policy": "CURRENT_MT5_SPREAD",
            "evidence": evidence,
            "coverage_complete": True,
        }

    @staticmethod
    def _find_recovery_exit(
        *,
        position: ForexPosition,
        quote: ForexQuote,
        bars: tuple[ForexBar, ...],
        start: datetime,
        now: datetime,
    ) -> tuple[dict[str, Any] | None, int]:
        if any(bar.pair != position.pair for bar in bars) or any(
            right.timestamp <= left.timestamp
            for left, right in zip(bars, bars[1:])
        ):
            raise TradingValidationError(
                "forex_protection: invalid_recovery_bars"
            )
        spread = max(Decimal("0"), quote.ask - quote.bid)
        examined = 0
        for bar in bars:
            if bar.timestamp >= now:
                continue
            if bar.timestamp < position.opened_at:
                continue
            if bar.timestamp + timedelta(minutes=1) <= start:
                continue
            examined += 1
            executable_open = (
                bar.open if position.side == "LONG" else bar.open + spread
            )
            executable_low = (
                bar.low if position.side == "LONG" else bar.low + spread
            )
            executable_high = (
                bar.high if position.side == "LONG" else bar.high + spread
            )
            stop_gap = (
                executable_open <= position.stop_loss
                if position.side == "LONG"
                else executable_open >= position.stop_loss
            )
            target_gap = position.take_profit is not None and (
                executable_open >= position.take_profit
                if position.side == "LONG"
                else executable_open <= position.take_profit
            )
            if stop_gap:
                return ({
                    "exit_price": executable_open,
                    "trigger": "STOP_LOSS_GAP",
                    "reason_codes": (
                        "STOP_LOSS_TRIGGERED",
                        "STOP_LOSS_GAP",
                        "RECOVERY_M1_REPLAY",
                    ),
                    "bar_timestamp": bar.timestamp,
                    "ambiguous_bar": False,
                }, examined)
            if target_gap:
                return ({
                    "exit_price": position.take_profit,
                    "trigger": "TAKE_PROFIT_GAP",
                    "reason_codes": (
                        "TAKE_PROFIT_TRIGGERED",
                        "TAKE_PROFIT_GAP",
                        "RECOVERY_M1_REPLAY",
                    ),
                    "bar_timestamp": bar.timestamp,
                    "ambiguous_bar": False,
                }, examined)
            stop_hit = (
                executable_low <= position.stop_loss
                if position.side == "LONG"
                else executable_high >= position.stop_loss
            )
            target_hit = position.take_profit is not None and (
                executable_high >= position.take_profit
                if position.side == "LONG"
                else executable_low <= position.take_profit
            )
            if not stop_hit and not target_hit:
                continue
            if stop_hit:
                ambiguous = bool(target_hit)
                reason_codes = ["STOP_LOSS_TRIGGERED"]
                if ambiguous:
                    reason_codes.append("STOP_LOSS_AMBIGUOUS_BAR")
                reason_codes.append("RECOVERY_M1_REPLAY")
                return ({
                    "exit_price": position.stop_loss,
                    "trigger": (
                        "STOP_LOSS_AMBIGUOUS_BAR"
                        if ambiguous
                        else "STOP_LOSS_TRIGGERED"
                    ),
                    "reason_codes": tuple(reason_codes),
                    "bar_timestamp": bar.timestamp,
                    "ambiguous_bar": ambiguous,
                }, examined)
            return ({
                "exit_price": position.take_profit,
                "trigger": "TAKE_PROFIT_TRIGGERED",
                "reason_codes": (
                    "TAKE_PROFIT_TRIGGERED",
                    "RECOVERY_M1_REPLAY",
                ),
                "bar_timestamp": bar.timestamp,
                "ambiguous_bar": False,
            }, examined)
        return None, examined

    @staticmethod
    def _execution_quote(
        position: ForexPosition,
        current: ForexQuote,
        exit_price: Decimal,
        now: datetime,
    ) -> ForexQuote:
        spread = max(Decimal("0"), current.ask - current.bid)
        bid = exit_price if position.side == "LONG" else exit_price - spread
        ask = exit_price + spread if position.side == "LONG" else exit_price
        if bid <= 0 or ask <= 0:
            raise TradingValidationError(
                "forex_protection: invalid_recovery_exit_price"
            )
        return ForexQuote.create(
            pair=position.pair,
            bid=bid,
            ask=ask,
            timestamp=now,
        )

    @staticmethod
    def _result(
        status: str,
        cycle_id: str,
        now: datetime,
        *,
        execution: dict[str, Any] | None,
        account: dict[str, Any],
        recovery_replay: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "mode": "FOREX_PAPER_POSITION_PROTECTION_ONLY",
            "cycle_id": cycle_id,
            "observed_at": now.isoformat(),
            "paper": {
                "mode": "FOREX_PAPER_ONLY",
                "new_entries_allowed": False,
                "execution": execution or {
                    "status": "NO_EXECUTION",
                    "executions": [],
                    "rejections": [],
                    "live_orders_sent": False,
                    "network_access": False,
                },
                "account": account,
                "live_orders_sent": False,
                "network_access": False,
            },
            "market_data_source": "LOCAL_MT5_DEMO",
            "external_market_data_requests": False,
            "recovery_replay": recovery_replay or {
                "status": "NOT_REQUESTED",
                "historical_exit_count": 0,
                "coverage_complete": True,
            },
            "new_entries_allowed": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    @staticmethod
    def _blocked(
        cycle_id: str,
        reason: str,
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "status": "PAPER_PROTECTION_BLOCKED",
            "mode": "FOREX_PAPER_POSITION_PROTECTION_ONLY",
            "cycle_id": cycle_id,
            "observed_at": now.isoformat(),
            "reason": reason,
            "market_data_source": "LOCAL_MT5_DEMO",
            "external_market_data_requests": False,
            "new_entries_allowed": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
            "network_access": False,
        }


__all__ = ["ForexPaperProtectionRuntime"]
