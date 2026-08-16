"""Local paper broker with no network or live-order transport."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from app.trading.ledger import PaperTradingLedger
from app.trading.models import MarketQuote, PaperOrder, aware_utc
from app.trading.policy import PaperTradingPolicy
from app.trading.risk import PreTradeRiskEngine, account_metrics


_CENTS = Decimal("0.01")
_PRICE = Decimal("0.0001")
_QUANTITY = Decimal("0.00000001")


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception:
        return Decimal("0")
    return result if result.is_finite() else Decimal("0")


def _money(value: Decimal) -> str:
    return str(value.quantize(_CENTS, rounding=ROUND_HALF_UP))


def _price(value: Decimal) -> str:
    return str(value.quantize(_PRICE, rounding=ROUND_HALF_UP))


def _quantity(value: Decimal) -> str:
    return str(value.quantize(_QUANTITY, rounding=ROUND_HALF_UP).normalize())


class LiveTradingBlockedError(RuntimeError):
    """Raised unconditionally when any caller asks for live execution."""


class PaperTradingEngine:
    """Simulate fills locally while enforcing the policy before every order."""

    RELEASE_CONFIRMATION = "PAPER ONLY ODBLOKUJ"

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: PaperTradingPolicy | None = None,
        ledger: PaperTradingLedger | None = None,
    ) -> None:
        self.policy = policy or PaperTradingPolicy()
        self.ledger = ledger or PaperTradingLedger(project_root, policy=self.policy)
        self.risk = PreTradeRiskEngine(self.policy)

    def submit(
        self,
        order: PaperOrder,
        quote: MarketQuote,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")

        def operation(state: dict[str, Any]) -> dict[str, Any]:
            existing = dict(
                dict(state.get("processed_orders", {}) or {}).get(
                    order.client_order_id, {}
                ) or {}
            )
            if existing:
                existing["idempotent_replay"] = True
                return existing

            self._roll_session(state, selected_now, quote)
            decision = self.risk.evaluate(order, quote, state, now=selected_now)
            if not decision.allowed:
                outcome = {
                    "status": "REJECTED",
                    "mode": "PAPER_ONLY",
                    "client_order_id": order.client_order_id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": _quantity(order.quantity),
                    "risk_code": decision.code,
                    "reason": decision.reason,
                    "live_order_sent": False,
                    "idempotent_replay": False,
                }
                self._remember_outcome(state, order.client_order_id, outcome)
                state["rejections"] = list(state.get("rejections", []) or []) + [
                    deepcopy(outcome) | {"created_at": selected_now.isoformat()}
                ]
                self.ledger.append_event(
                    state,
                    "ORDER_REJECTED",
                    {
                        "client_order_id": order.client_order_id,
                        "symbol": order.symbol,
                        "side": order.side,
                        "quantity": _quantity(order.quantity),
                        "risk_code": decision.code,
                    },
                    created_at=selected_now,
                )
                return outcome

            fill_id = f"paper-fill-{uuid4().hex}"
            fill_price = decision.estimated_price
            notional = decision.estimated_notional
            fee = decision.estimated_fee
            positions = dict(state.get("positions", {}) or {})
            previous = dict(positions.get(order.symbol, {}) or {})
            held = _decimal(previous.get("quantity"))
            average_cost = _decimal(previous.get("average_cost"))
            realized = Decimal("0")
            cash = _decimal(state.get("cash"))

            if order.side == "BUY":
                new_quantity = held + order.quantity
                new_cost = held * average_cost + notional + fee
                positions[order.symbol] = {
                    "quantity": _quantity(new_quantity),
                    "average_cost": _price(new_cost / new_quantity),
                    "last_price": _price(fill_price),
                    "currency": quote.currency,
                    "updated_at": selected_now.isoformat(),
                }
                cash -= notional + fee
            else:
                new_quantity = held - order.quantity
                realized = (fill_price - average_cost) * order.quantity - fee
                cash += notional - fee
                if new_quantity > 0:
                    positions[order.symbol] = {
                        **previous,
                        "quantity": _quantity(new_quantity),
                        "last_price": _price(fill_price),
                        "updated_at": selected_now.isoformat(),
                    }
                else:
                    positions.pop(order.symbol, None)

            state["positions"] = positions
            state["cash"] = _money(cash)
            state["realized_pnl_total"] = _money(
                _decimal(state.get("realized_pnl_total")) + realized
            )
            state["orders_today"] = int(state.get("orders_today", 0) or 0) + 1
            fill = {
                "fill_id": fill_id,
                "client_order_id": order.client_order_id,
                "strategy_id": order.strategy_id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": _quantity(order.quantity),
                "price": _price(fill_price),
                "notional": _money(notional),
                "fee": _money(fee),
                "realized_pnl": _money(realized),
                "currency": quote.currency,
                "filled_at": selected_now.isoformat(),
                "mode": "PAPER_ONLY",
            }
            state["fills"] = list(state.get("fills", []) or []) + [fill]
            outcome = {
                "status": "FILLED",
                "mode": "PAPER_ONLY",
                "fill": deepcopy(fill),
                "live_order_sent": False,
                "idempotent_replay": False,
            }
            self._remember_outcome(state, order.client_order_id, outcome)
            self.ledger.append_event(
                state,
                "PAPER_FILL",
                {
                    "fill_id": fill_id,
                    "client_order_id": order.client_order_id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": fill["quantity"],
                    "price": fill["price"],
                    "fee": fill["fee"],
                },
                created_at=selected_now,
            )
            return outcome

        return self.ledger.transaction(operation)

    def status(
        self,
        quotes: Mapping[str, MarketQuote] | None = None,
    ) -> dict[str, Any]:
        state = self.ledger.snapshot()
        for symbol, quote in dict(quotes or {}).items():
            if symbol in state["positions"] and quote.symbol == symbol:
                state["positions"][symbol]["last_price"] = _price(quote.midpoint)
        metrics = account_metrics(state)
        return {
            "status": "READY" if state.get("mode") == "PAPER_ONLY" else "BLOCKED",
            "mode": str(state.get("mode", "")),
            "base_currency": str(state.get("base_currency", "")),
            "cash": _money(metrics["cash"]),
            "market_value": _money(metrics["market_value"]),
            "gross_exposure": _money(metrics["gross_exposure"]),
            "equity": _money(metrics["equity"]),
            "realized_pnl_total": _money(_decimal(state.get("realized_pnl_total"))),
            "position_count": len(dict(state.get("positions", {}) or {})),
            "fill_count": len(list(state.get("fills", []) or [])),
            "rejection_count": len(list(state.get("rejections", []) or [])),
            "orders_today": int(state.get("orders_today", 0) or 0),
            "kill_switch_active": bool(
                dict(state.get("kill_switch", {}) or {}).get("active")
            ),
            "audit_chain_valid": self.ledger.verify_audit(state),
            "live_trading_enabled": False,
            "network_access": False,
        }

    def activate_kill_switch(self, reason: object) -> dict[str, Any]:
        selected_reason = " ".join(str(reason or "").split())[:240]
        if not selected_reason:
            selected_reason = "Ręczne zatrzymanie właściciela"
        now = datetime.now(timezone.utc)

        def operation(state: dict[str, Any]) -> dict[str, Any]:
            state["kill_switch"] = {
                "active": True,
                "reason": selected_reason,
                "changed_at": now.isoformat(),
            }
            self.ledger.append_event(
                state,
                "KILL_SWITCH_ACTIVATED",
                {"reason": selected_reason},
                created_at=now,
            )
            return {
                "status": "KILL_SWITCH_ACTIVE",
                "mode": "PAPER_ONLY",
                "reason": selected_reason,
                "live_order_sent": False,
            }

        return self.ledger.transaction(operation)

    def release_kill_switch(self, confirmation: object) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != self.RELEASE_CONFIRMATION:
            return {
                "status": "CONFIRMATION_REQUIRED",
                "mode": "PAPER_ONLY",
                "live_order_sent": False,
            }
        now = datetime.now(timezone.utc)

        def operation(state: dict[str, Any]) -> dict[str, Any]:
            state["kill_switch"] = {
                "active": False,
                "reason": "",
                "changed_at": now.isoformat(),
            }
            self.ledger.append_event(
                state,
                "KILL_SWITCH_RELEASED",
                {"paper_only_confirmation": True},
                created_at=now,
            )
            return {
                "status": "KILL_SWITCH_RELEASED",
                "mode": "PAPER_ONLY",
                "live_order_sent": False,
            }

        return self.ledger.transaction(operation)

    @staticmethod
    def submit_live_order(*_args: object, **_kwargs: object) -> None:
        raise LiveTradingBlockedError(
            "LIVE_TRADING_BLOCKED: ten etap obsługuje wyłącznie PAPER_ONLY."
        )

    def _roll_session(
        self,
        state: dict[str, Any],
        now: datetime,
        quote: MarketQuote,
    ) -> None:
        session_date = now.date().isoformat()
        if str(state.get("session_date", "")) == session_date:
            return
        metrics = account_metrics(state, current_quote=quote)
        state["session_date"] = session_date
        state["orders_today"] = 0
        state["day_start_equity"] = _money(metrics["equity"])

    @staticmethod
    def _remember_outcome(
        state: dict[str, Any],
        order_id: str,
        outcome: dict[str, Any],
    ) -> None:
        processed = dict(state.get("processed_orders", {}) or {})
        processed[order_id] = deepcopy(outcome)
        state["processed_orders"] = processed


__all__ = ["LiveTradingBlockedError", "PaperTradingEngine"]
