"""Persistent local executor for Forex PAPER_ONLY instructions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import uuid4

from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_models import ForexPosition, ForexQuote, major_pair
from app.trading.forex_risk import (
    ForexPaperPolicy,
    ForexPortfolioRiskEngine,
    ForexRateBook,
)
from app.trading.models import TradingValidationError, aware_utc, decimal_value
from app.trading.paper_broker import LiveTradingBlockedError


_CYCLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,79}$")
_MONEY = Decimal("0.01")
_PRICE = Decimal("0.000001")


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception:
        return Decimal("0")
    return result if result.is_finite() else Decimal("0")


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return _decimal(value)


def _text(value: Decimal, quantum: Decimal = _MONEY) -> str:
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


class ForexPaperExecutionEngine:
    """Apply a validated paper plan and independently recheck every entry."""

    RELEASE_CONFIRMATION = "FOREX PAPER ODBLOKUJ"

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: ForexPaperPolicy | None = None,
        ledger: ForexPaperLedger | None = None,
    ) -> None:
        self.policy = policy or ForexPaperPolicy()
        self.ledger = ledger or ForexPaperLedger(project_root)
        self.risk = ForexPortfolioRiskEngine(self.policy)

    def apply_plan(
        self,
        plan: Mapping[str, Any],
        *,
        quotes: Mapping[str, ForexQuote],
        rates: ForexRateBook,
        cycle_id: object,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        selected_cycle = str(cycle_id or "").strip()
        if not _CYCLE_ID.fullmatch(selected_cycle):
            raise TradingValidationError("forex_cycle: invalid_id")
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        rates_age = abs((selected_now - rates.now).total_seconds())
        if rates_age > self.policy.max_conversion_age_seconds:
            raise TradingValidationError("forex_execution: stale_rate_book")
        for quote in quotes.values():
            age = (selected_now - quote.timestamp).total_seconds()
            if age < -2 or age > self.policy.max_conversion_age_seconds:
                raise TradingValidationError("forex_execution: stale_quote")
            if quote not in rates.quotes:
                raise TradingValidationError("forex_execution: rate_book_mismatch")
        if str(plan.get("mode", "")) != "FOREX_PAPER_ONLY":
            raise TradingValidationError("forex_plan: paper_mode_required")
        if bool(plan.get("live_orders_sent")):
            raise TradingValidationError("forex_plan: live_flag_forbidden")
        raw_instructions = [
            dict(item) for item in list(plan.get("instructions", []) or [])
            if isinstance(item, Mapping)
        ]
        instructions = sorted(
            raw_instructions,
            key=lambda item: 0 if item.get("action") == "CLOSE_POSITION" else 1,
        )

        def operation(state: dict[str, Any]) -> dict[str, Any]:
            previous = dict(
                dict(state.get("processed_cycles", {}) or {}).get(
                    selected_cycle, {}
                ) or {}
            )
            if previous:
                previous["idempotent_replay"] = True
                return previous
            if state.get("mode") != "FOREX_PAPER_ONLY":
                return self._remember_blocked(
                    state, selected_cycle, "MODE_NOT_PAPER", selected_now
                )
            if not self.ledger.verify_audit(state):
                return self._remember_blocked(
                    state, selected_cycle, "AUDIT_CHAIN_INVALID", selected_now
                )
            self._roll_session(state, selected_now)
            self._mark_positions(state, quotes, selected_now)
            executions: list[dict[str, Any]] = []
            rejections: list[dict[str, str]] = []
            for instruction in instructions:
                action = str(instruction.get("action", "")).strip().upper()
                pair_name = str(instruction.get("pair", "")).strip().upper()
                try:
                    pair = major_pair(pair_name)
                except TradingValidationError:
                    rejections.append({"pair": pair_name, "code": "PAIR_NOT_ALLOWED"})
                    continue
                quote = quotes.get(pair.symbol)
                if quote is None or quote.pair != pair:
                    rejections.append({"pair": pair.symbol, "code": "QUOTE_MISSING"})
                    continue
                if action == "CLOSE_POSITION":
                    result = self._close(
                        state,
                        pair.symbol,
                        quote,
                        rates,
                        selected_now,
                        instruction,
                    )
                elif action in {"OPEN_LONG", "OPEN_SHORT"}:
                    if bool(dict(state.get("kill_switch", {}) or {}).get("active")):
                        result = {"status": "REJECTED", "code": "KILL_SWITCH_ACTIVE"}
                    else:
                        result = self._open(
                            state,
                            instruction,
                            quote,
                            rates,
                            selected_now,
                        )
                else:
                    result = {"status": "REJECTED", "code": "UNKNOWN_ACTION"}
                if result["status"] == "EXECUTED":
                    executions.append(result)
                else:
                    rejections.append({
                        "pair": pair.symbol,
                        "code": str(result.get("code", "REJECTED")),
                    })
            if rejections:
                state["rejections"] = list(state.get("rejections", []) or []) + [
                    {**item, "cycle_id": selected_cycle, "created_at": selected_now.isoformat()}
                    for item in rejections
                ]
            outcome = {
                "status": "APPLIED" if executions else "NO_EXECUTION",
                "mode": "FOREX_PAPER_ONLY",
                "cycle_id": selected_cycle,
                "executions": executions,
                "rejections": rejections,
                "live_orders_sent": False,
                "network_access": False,
                "idempotent_replay": False,
            }
            cycles = dict(state.get("processed_cycles", {}) or {})
            cycles[selected_cycle] = deepcopy(outcome)
            state["processed_cycles"] = cycles
            self.ledger.append_event(
                state,
                "FOREX_PAPER_CYCLE",
                {
                    "cycle_id": selected_cycle,
                    "execution_count": len(executions),
                    "rejection_count": len(rejections),
                    "executions": [
                        dict(item.get("fill", {})) for item in executions
                    ],
                    "rejections": deepcopy(rejections),
                    "balance_pln": str(state.get("balance_pln", "")),
                },
                created_at=selected_now,
            )
            return outcome

        return self.ledger.transaction(operation)

    def _open(
        self,
        state: dict[str, Any],
        instruction: Mapping[str, Any],
        quote: ForexQuote,
        rates: ForexRateBook,
        now: datetime,
    ) -> dict[str, Any]:
        positions = self._positions(state)
        if quote.pair.symbol in positions:
            return {"status": "REJECTED", "code": "PAIR_ALREADY_OPEN"}
        action = str(instruction.get("action", "")).upper()
        side = "LONG" if action == "OPEN_LONG" else "SHORT"
        entry = quote.ask if side == "LONG" else quote.bid
        requested_units = decimal_value(instruction.get("units"), "units")
        stop = decimal_value(instruction.get("stop_loss"), "stop_loss")
        raw_target = instruction.get("take_profit")
        if raw_target is None or str(raw_target).strip() == "":
            return {"status": "REJECTED", "code": "TAKE_PROFIT_REQUIRED"}
        target = decimal_value(raw_target, "take_profit")
        if (side == "LONG" and stop >= entry) or (
            side == "SHORT" and stop <= entry
        ):
            return {"status": "REJECTED", "code": "INVALID_STOP"}
        stop_pips = abs(entry - stop) / quote.pair.pip_size
        if not (
            ForexPaperCoordinator.MINIMUM_STOP_PIPS
            <= stop_pips
            <= ForexPaperCoordinator.MAXIMUM_STOP_PIPS
        ):
            return {
                "status": "REJECTED",
                "code": "STOP_DISTANCE_POLICY_MISMATCH",
            }
        if (side == "LONG" and target <= entry) or (
            side == "SHORT" and target >= entry
        ):
            return {"status": "REJECTED", "code": "INVALID_TAKE_PROFIT"}
        expected_target_distance = (
            abs(entry - stop) * self.policy.take_profit_reward_risk
        )
        if abs(abs(target - entry) - expected_target_distance) > (
            quote.pair.pip_size / Decimal("1000")
        ):
            return {
                "status": "REJECTED",
                "code": "TAKE_PROFIT_POLICY_MISMATCH",
            }
        balance = _decimal(state.get("balance_pln"))
        equity = balance + self._unrealized_pln(positions, {}, rates)
        decision = self.risk.evaluate_open(
            pair=quote.pair,
            side=side,
            entry_price=entry,
            stop_loss=stop,
            equity_pln=equity,
            daily_pnl_pln=state.get("daily_pnl_pln", "0"),
            positions=positions.values(),
            rates=rates,
            now=now,
        )
        if not decision.allowed:
            return {"status": "REJECTED", "code": decision.code}
        if requested_units < self.policy.minimum_units or requested_units > decision.units:
            return {"status": "REJECTED", "code": "EXECUTION_RISK_RECHECK"}
        position = ForexPosition(
            pair=quote.pair,
            side=side,
            units=requested_units,
            entry_price=entry,
            current_price=entry,
            stop_loss=stop,
            opened_at=now,
            take_profit=target,
        )
        stored = {
            "pair": position.pair.symbol,
            "side": position.side,
            "units": str(position.units),
            "entry_price": _text(position.entry_price, _PRICE),
            "current_price": _text(position.current_price, _PRICE),
            "stop_loss": _text(position.stop_loss, _PRICE),
            "take_profit": _text(target, _PRICE),
            "opened_at": position.opened_at.isoformat(),
        }
        raw_positions = dict(state.get("positions", {}) or {})
        raw_positions[position.pair.symbol] = stored
        state["positions"] = raw_positions
        fill = {
            "fill_id": f"forex-paper-{uuid4().hex}",
            "action": f"OPEN_{side}",
            **stored,
            "realized_pnl_pln": "0.00",
            "filled_at": now.isoformat(),
        }
        state["fills"] = list(state.get("fills", []) or []) + [fill]
        return {"status": "EXECUTED", "fill": deepcopy(fill)}

    def _close(
        self,
        state: dict[str, Any],
        pair_name: str,
        quote: ForexQuote,
        rates: ForexRateBook,
        now: datetime,
        instruction: Mapping[str, Any],
    ) -> dict[str, Any]:
        positions = self._positions(state)
        position = positions.get(pair_name)
        if position is None:
            return {"status": "REJECTED", "code": "POSITION_NOT_FOUND"}
        exit_price = quote.bid if position.side == "LONG" else quote.ask
        direction = Decimal("1") if position.side == "LONG" else Decimal("-1")
        pnl_quote = (exit_price - position.entry_price) * position.units * direction
        pnl_pln = rates.convert(
            pnl_quote,
            position.pair.quote_currency,
            self.policy.account_currency,
        )
        state["balance_pln"] = _text(_decimal(state.get("balance_pln")) + pnl_pln)
        state["daily_pnl_pln"] = _text(
            _decimal(state.get("daily_pnl_pln")) + pnl_pln
        )
        raw_positions = dict(state.get("positions", {}) or {})
        raw_positions.pop(pair_name, None)
        state["positions"] = raw_positions
        fill = {
            "fill_id": f"forex-paper-{uuid4().hex}",
            "action": f"CLOSE_{position.side}",
            "pair": pair_name,
            "side": position.side,
            "units": str(position.units),
            "entry_price": _text(position.entry_price, _PRICE),
            "exit_price": _text(exit_price, _PRICE),
            "stop_loss": _text(position.stop_loss, _PRICE),
            "take_profit": (
                _text(position.take_profit, _PRICE)
                if position.take_profit is not None
                else ""
            ),
            "reason_codes": [
                str(value)[:80]
                for value in list(instruction.get("reason_codes", []) or [])[:8]
            ],
            "realized_pnl_pln": _text(pnl_pln),
            "filled_at": now.isoformat(),
        }
        state["fills"] = list(state.get("fills", []) or []) + [fill]
        return {"status": "EXECUTED", "fill": deepcopy(fill)}

    def positions(self) -> dict[str, ForexPosition]:
        return self._positions(self.ledger.snapshot())

    def status(
        self,
        *,
        quotes: Mapping[str, ForexQuote] | None = None,
        rates: ForexRateBook | None = None,
    ) -> dict[str, Any]:
        state = self.ledger.snapshot()
        positions = self._positions(state)
        fills = list(state.get("fills", []) or [])
        closed_fills = [
            dict(item)
            for item in fills
            if str(dict(item or {}).get("action", "")).startswith("CLOSE_")
        ]
        realized = sum(
            (_decimal(item.get("realized_pnl_pln")) for item in closed_fills),
            Decimal("0"),
        )
        winning_trades = sum(
            _decimal(item.get("realized_pnl_pln")) > 0 for item in closed_fills
        )
        losing_trades = sum(
            _decimal(item.get("realized_pnl_pln")) < 0 for item in closed_fills
        )
        breakeven_trades = len(closed_fills) - winning_trades - losing_trades
        win_rate = (
            Decimal(winning_trades) * Decimal("100") / Decimal(len(closed_fills))
            if closed_fills
            else Decimal("0")
        )
        processed_cycles = dict(state.get("processed_cycles", {}) or {})
        latest_cycle_id = next(reversed(processed_cycles), "")
        latest_outcome = dict(processed_cycles.get(latest_cycle_id, {}) or {})
        latest_created_at = ""
        for event in reversed(list(state.get("audit", []) or [])):
            details = dict(dict(event or {}).get("details", {}) or {})
            if (
                event.get("event_type") == "FOREX_PAPER_CYCLE"
                and details.get("cycle_id") == latest_cycle_id
            ):
                latest_created_at = str(event.get("created_at", ""))
                break
        unrealized = (
            self._unrealized_pln(positions, dict(quotes or {}), rates)
            if rates is not None
            else Decimal("0")
        )
        balance = _decimal(state.get("balance_pln"))
        return {
            "status": "READY" if state.get("mode") == "FOREX_PAPER_ONLY" else "BLOCKED",
            "mode": str(state.get("mode", "")),
            "balance_pln": _text(balance),
            "unrealized_pnl_pln": _text(unrealized),
            "equity_pln": _text(balance + unrealized),
            "daily_pnl_pln": _text(_decimal(state.get("daily_pnl_pln"))),
            "realized_pnl_pln": _text(realized),
            "position_count": len(positions),
            "open_positions": [
                {
                    "pair": position.pair.symbol,
                    "side": position.side,
                    "units": str(position.units),
                    "entry_price": _text(position.entry_price, _PRICE),
                    "current_price": _text(position.current_price, _PRICE),
                    "stop_loss": _text(position.stop_loss, _PRICE),
                    "take_profit": (
                        _text(position.take_profit, _PRICE)
                        if position.take_profit is not None
                        else ""
                    ),
                    "opened_at": position.opened_at.isoformat(),
                }
                for position in sorted(
                    positions.values(), key=lambda item: item.pair.symbol
                )
            ],
            "take_profit_protected_position_count": sum(
                position.take_profit is not None for position in positions.values()
            ),
            "legacy_position_without_take_profit_count": sum(
                position.take_profit is None for position in positions.values()
            ),
            "fill_count": len(fills),
            "closed_trade_count": len(closed_fills),
            "winning_trade_count": winning_trades,
            "losing_trade_count": losing_trades,
            "breakeven_trade_count": breakeven_trades,
            "win_rate_pct": _text(win_rate),
            "processed_cycle_count": len(processed_cycles),
            "rejection_count": len(list(state.get("rejections", []) or [])),
            "last_cycle": {
                "cycle_id": latest_cycle_id,
                "status": str(latest_outcome.get("status", "")),
                "created_at": latest_created_at,
                "execution_count": len(
                    list(latest_outcome.get("executions", []) or [])
                ),
                "rejection_codes": [
                    str(dict(item or {}).get("code", ""))
                    for item in list(latest_outcome.get("rejections", []) or [])
                    if str(dict(item or {}).get("code", ""))
                ],
            },
            "kill_switch_active": bool(
                dict(state.get("kill_switch", {}) or {}).get("active")
            ),
            "audit_chain_valid": self.ledger.verify_audit(state),
            "live_trading_enabled": False,
            "network_access": False,
        }

    def activate_kill_switch(self, reason: object) -> None:
        selected_reason = " ".join(str(reason or "").split())[:240] or "Ręczne zatrzymanie"
        now = datetime.now(timezone.utc)

        def operation(state: dict[str, Any]) -> None:
            state["kill_switch"] = {
                "active": True,
                "reason": selected_reason,
                "changed_at": now.isoformat(),
            }
            self.ledger.append_event(
                state, "FOREX_KILL_SWITCH", {"reason": selected_reason}, created_at=now
            )

        self.ledger.transaction(operation)

    def release_kill_switch(self, confirmation: object) -> bool:
        if str(confirmation or "").strip().upper() != self.RELEASE_CONFIRMATION:
            return False
        now = datetime.now(timezone.utc)

        def operation(state: dict[str, Any]) -> None:
            state["kill_switch"] = {
                "active": False,
                "reason": "",
                "changed_at": now.isoformat(),
            }
            self.ledger.append_event(
                state,
                "FOREX_KILL_SWITCH_RELEASED",
                {"paper_only_confirmation": True},
                created_at=now,
            )

        self.ledger.transaction(operation)
        return True

    @staticmethod
    def submit_live_order(*_args: object, **_kwargs: object) -> None:
        raise LiveTradingBlockedError(
            "LIVE_TRADING_BLOCKED: wykonanie Forex działa wyłącznie PAPER_ONLY."
        )

    def _positions(self, state: Mapping[str, Any]) -> dict[str, ForexPosition]:
        result: dict[str, ForexPosition] = {}
        for symbol, raw in dict(state.get("positions", {}) or {}).items():
            value = dict(raw or {})
            pair = major_pair(symbol)
            result[pair.symbol] = ForexPosition(
                pair=pair,
                side=value.get("side", ""),
                units=_decimal(value.get("units")),
                entry_price=_decimal(value.get("entry_price")),
                current_price=_decimal(value.get("current_price")),
                stop_loss=_decimal(value.get("stop_loss")),
                opened_at=datetime.fromisoformat(str(value.get("opened_at", ""))),
                take_profit=_optional_decimal(value.get("take_profit")),
            )
        return result

    def _unrealized_pln(
        self,
        positions: Mapping[str, ForexPosition],
        quotes: Mapping[str, ForexQuote],
        rates: ForexRateBook | None,
    ) -> Decimal:
        if rates is None:
            return Decimal("0")
        total = Decimal("0")
        for symbol, position in positions.items():
            quote = quotes.get(symbol)
            current = (
                quote.bid if position.side == "LONG" else quote.ask
            ) if quote is not None and quote.pair == position.pair else position.current_price
            direction = Decimal("1") if position.side == "LONG" else Decimal("-1")
            pnl_quote = (current - position.entry_price) * position.units * direction
            total += rates.convert(
                pnl_quote,
                position.pair.quote_currency,
                self.policy.account_currency,
            )
        return total

    @staticmethod
    def _mark_positions(
        state: dict[str, Any],
        quotes: Mapping[str, ForexQuote],
        now: datetime,
    ) -> None:
        positions = dict(state.get("positions", {}) or {})
        for symbol, raw in list(positions.items()):
            quote = quotes.get(symbol)
            if quote is None or quote.pair.symbol != symbol:
                continue
            value = dict(raw or {})
            value["current_price"] = _text(quote.midpoint, _PRICE)
            value["marked_at"] = now.isoformat()
            positions[symbol] = value
        state["positions"] = positions

    @staticmethod
    def _roll_session(state: dict[str, Any], now: datetime) -> None:
        session_date = now.date().isoformat()
        if state.get("session_date") == session_date:
            return
        state["session_date"] = session_date
        state["daily_pnl_pln"] = "0"

    @staticmethod
    def _remember_blocked(
        state: dict[str, Any], cycle_id: str, code: str, now: datetime
    ) -> dict[str, Any]:
        outcome = {
            "status": "BLOCKED",
            "mode": "FOREX_PAPER_ONLY",
            "cycle_id": cycle_id,
            "executions": [],
            "rejections": [{"pair": "", "code": code}],
            "live_orders_sent": False,
            "network_access": False,
            "idempotent_replay": False,
        }
        cycles = dict(state.get("processed_cycles", {}) or {})
        cycles[cycle_id] = deepcopy(outcome)
        state["processed_cycles"] = cycles
        state["rejections"] = list(state.get("rejections", []) or []) + [{
            "pair": "", "code": code, "cycle_id": cycle_id,
            "created_at": now.isoformat(),
        }]
        return outcome


__all__ = ["ForexPaperExecutionEngine"]
