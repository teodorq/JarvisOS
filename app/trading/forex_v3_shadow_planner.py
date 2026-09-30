"""Read-only planner for an initialized, isolated Forex V3 shadow cohort."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from app.trading.forex_candidate_v3 import ForexStrengthFilteredScanner
from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_models import (
    ForexBar,
    ForexPosition,
    ForexQuote,
    ForexSafetyContext,
    major_pair,
)
from app.trading.forex_risk import ForexPaperPolicy, ForexRateBook
from app.trading.forex_sample_contract import (
    build_forex_v3_shadow_sample_contract,
)
from app.trading.forex_v3_shadow import ForexV3ShadowReadiness
from app.trading.forex_v3_shadow_ledger import ForexV3ShadowLedger
from app.trading.models import TradingValidationError, aware_utc
from app.trading.paper_broker import LiveTradingBlockedError


_CYCLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,79}$")


class ForexV3ShadowPlanner:
    """Build non-executable V3 plans without modifying either PAPER ledger."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: ForexPaperPolicy | None = None,
        readiness: Any | None = None,
        ledger: ForexV3ShadowLedger | None = None,
    ) -> None:
        self.policy = policy or ForexPaperPolicy()
        self.scanner = ForexStrengthFilteredScanner()
        self.coordinator = ForexPaperCoordinator(self.policy)
        self.sample_contract = build_forex_v3_shadow_sample_contract(
            paper_policy=self.policy,
            universe=self.scanner.universe,
        )
        self.readiness = readiness or ForexV3ShadowReadiness(project_root)
        self.ledger = ledger or ForexV3ShadowLedger(
            project_root,
            sample_contract=self.sample_contract,
        )

    def plan(
        self,
        *,
        quotes: Mapping[str, ForexQuote],
        bars: Mapping[str, Iterable[ForexBar]],
        contexts: Mapping[str, ForexSafetyContext],
        conversion_quotes: Iterable[ForexQuote],
        cycle_id: object,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        selected_cycle = str(cycle_id or "").strip()
        if not _CYCLE_ID.fullmatch(selected_cycle):
            return self._blocked("INVALID_CYCLE_ID", selected_now)
        readiness = self.readiness.status()
        if (
            readiness.get("status") != "SHADOW_INITIALIZED_INACTIVE"
            or readiness.get("shadow_ledger_initialized") is not True
            or readiness.get("shadow_execution_enabled") is not False
        ):
            return self._blocked(
                str(readiness.get("status", "SHADOW_NOT_INITIALIZED")),
                selected_now,
            )
        state = self.ledger.snapshot()
        initialization = dict(state.get("initialization", {}) or {})
        if (
            state.get("mode") != "FOREX_V3_SHADOW_PAPER_ONLY"
            or initialization.get("status")
            != "INITIALIZED_SHADOW_INACTIVE"
            or initialization.get("execution_enabled") is not False
            or not self.ledger.verify_audit(state)
        ):
            return self._blocked("SHADOW_LEDGER_INVALID", selected_now)
        all_quotes = dict(quotes)
        for quote in conversion_quotes:
            if quote.pair.symbol in all_quotes:
                return self._blocked(
                    "DUPLICATE_CONVERSION_QUOTE",
                    selected_now,
                )
            all_quotes[quote.pair.symbol] = quote
        try:
            rates = ForexRateBook(
                all_quotes.values(),
                now=selected_now,
                max_age_seconds=self.policy.max_conversion_age_seconds,
            )
            positions = self._positions(state)
            assessments = self.scanner.scan(
                quotes=quotes,
                bars=bars,
                contexts=contexts,
                positions={
                    symbol: position.side
                    for symbol, position in positions.items()
                },
                now=selected_now,
            )
            balance = self._decimal(state.get("balance_pln"), "balance_pln")
            equity = balance + self._unrealized_pln(
                positions,
                quotes,
                rates,
            )
            plan = self.coordinator.plan(
                assessments=assessments,
                quotes=quotes,
                positions=positions,
                rates=rates,
                equity_pln=equity,
                daily_pnl_pln=state.get("daily_pnl_pln", "0"),
                now=selected_now,
            )
        except (TradingValidationError, ValueError, TypeError) as error:
            return self._blocked(str(error), selected_now)
        instructions = []
        for raw in list(plan.get("instructions", []) or []):
            instruction = dict(raw)
            instruction["mode"] = "FOREX_V3_SHADOW_PLAN_ONLY"
            instruction["executable"] = False
            instructions.append(instruction)
        audit = list(state.get("audit", []) or [])
        result = {
            "status": "SHADOW_PLAN_COMPUTED",
            "decision_status": str(plan.get("status", "NO_ACTION")),
            "mode": "FOREX_V3_SHADOW_PLAN_ONLY",
            "cycle_id": selected_cycle,
            "assessed_at": selected_now.isoformat(),
            "candidate_id": state["candidate_id"],
            "sample_contract": deepcopy(self.sample_contract),
            "shadow_ledger_audit_head": (
                str(audit[-1].get("event_hash", "")) if audit else ""
            ),
            "shadow_position_count": len(positions),
            "assessment_count": len(assessments),
            "assessments": [item.as_dict() for item in assessments],
            "instructions": instructions,
            "rejected": [
                dict(item) for item in list(plan.get("rejected", []) or [])
                if isinstance(item, Mapping)
            ],
            "executable": False,
            "shadow_execution_enabled": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }
        result["plan_sha256"] = self._fingerprint(result)
        return result

    @staticmethod
    def submit_live_order(*_args: object, **_kwargs: object) -> None:
        raise LiveTradingBlockedError(
            "LIVE_TRADING_BLOCKED: V3 SHADOW planner nie wykonuje zleceń."
        )

    @staticmethod
    def _positions(state: Mapping[str, Any]) -> dict[str, ForexPosition]:
        result: dict[str, ForexPosition] = {}
        for symbol, raw in dict(state.get("positions", {}) or {}).items():
            value = dict(raw or {})
            pair = major_pair(symbol)
            target = value.get("take_profit")
            result[pair.symbol] = ForexPosition(
                pair=pair,
                side=value.get("side", ""),
                units=ForexV3ShadowPlanner._decimal(value.get("units"), "units"),
                entry_price=ForexV3ShadowPlanner._decimal(
                    value.get("entry_price"),
                    "entry_price",
                ),
                current_price=ForexV3ShadowPlanner._decimal(
                    value.get("current_price"),
                    "current_price",
                ),
                stop_loss=ForexV3ShadowPlanner._decimal(
                    value.get("stop_loss"),
                    "stop_loss",
                ),
                opened_at=datetime.fromisoformat(
                    str(value.get("opened_at", ""))
                ),
                take_profit=(
                    None
                    if target in (None, "")
                    else ForexV3ShadowPlanner._decimal(
                        target,
                        "take_profit",
                    )
                ),
            )
        return result

    def _unrealized_pln(
        self,
        positions: Mapping[str, ForexPosition],
        quotes: Mapping[str, ForexQuote],
        rates: ForexRateBook,
    ) -> Decimal:
        total = Decimal("0")
        for symbol, position in positions.items():
            quote = quotes.get(symbol)
            current = (
                quote.bid if position.side == "LONG" else quote.ask
            ) if quote is not None and quote.pair == position.pair else (
                position.current_price
            )
            direction = Decimal("1") if position.side == "LONG" else Decimal("-1")
            pnl_quote = (
                current - position.entry_price
            ) * position.units * direction
            total += rates.convert(
                pnl_quote,
                position.pair.quote_currency,
                self.policy.account_currency,
            )
        return total

    @staticmethod
    def _decimal(value: object, field: str) -> Decimal:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise TradingValidationError(
                f"forex_v3_shadow_planner: invalid_{field}"
            ) from error
        if not number.is_finite():
            raise TradingValidationError(
                f"forex_v3_shadow_planner: invalid_{field}"
            )
        return number

    @staticmethod
    def _fingerprint(value: Mapping[str, Any]) -> str:
        encoded = json.dumps(
            dict(value),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _blocked(reason: str, now: datetime) -> dict[str, Any]:
        return {
            "status": "BLOCKED_SHADOW_PLAN",
            "mode": "FOREX_V3_SHADOW_PLAN_ONLY",
            "assessed_at": now.isoformat(),
            "reason": str(reason or "SHADOW_PLAN_BLOCKED")[:160],
            "instructions": [],
            "executable": False,
            "shadow_execution_enabled": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        }


__all__ = ["ForexV3ShadowPlanner"]
