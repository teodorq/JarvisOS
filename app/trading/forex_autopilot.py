"""One fail-closed autonomous cycle for the local Forex paper environment."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
)
from app.trading.forex_risk import ForexPaperPolicy, ForexRateBook
from app.trading.forex_scanner import ForexMarketScanner
from app.trading.models import TradingValidationError, aware_utc


class ForexPaperAutopilot:
    """Scan, decide, recheck and persist; never contacts a broker."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: ForexPaperPolicy | None = None,
    ) -> None:
        self.policy = policy or ForexPaperPolicy()
        self.scanner = ForexMarketScanner(MAJOR_FOREX_PAIRS)
        self.coordinator = ForexPaperCoordinator(self.policy)
        self.executor = ForexPaperExecutionEngine(
            project_root,
            policy=self.policy,
        )

    def run_cycle(
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
        all_quotes: dict[str, ForexQuote] = dict(quotes)
        for quote in conversion_quotes:
            if quote.pair.symbol in all_quotes:
                return self._blocked("DUPLICATE_CONVERSION_QUOTE", selected_now)
            all_quotes[quote.pair.symbol] = quote
        try:
            rates = ForexRateBook(
                all_quotes.values(),
                now=selected_now,
                max_age_seconds=self.policy.max_conversion_age_seconds,
            )
            current_positions = self.executor.positions()
            sides = {
                symbol: position.side
                for symbol, position in current_positions.items()
            }
            assessments = self.scanner.scan(
                quotes=quotes,
                bars=bars,
                contexts=contexts,
                positions=sides,
                now=selected_now,
            )
            before = self.executor.status(quotes=quotes, rates=rates)
            plan = self.coordinator.plan(
                assessments=assessments,
                quotes=quotes,
                positions=current_positions,
                rates=rates,
                equity_pln=before["equity_pln"],
                daily_pnl_pln=before["daily_pnl_pln"],
                now=selected_now,
            )
            execution = self.executor.apply_plan(
                plan,
                quotes=quotes,
                rates=rates,
                cycle_id=cycle_id,
                now=selected_now,
            )
            after = self.executor.status(quotes=quotes, rates=rates)
        except TradingValidationError as error:
            return self._blocked(str(error), selected_now)
        return {
            "status": "CYCLE_COMPLETED",
            "mode": "FOREX_PAPER_ONLY",
            "cycle_id": str(cycle_id),
            "assessments": [item.as_dict() for item in assessments],
            "plan": plan,
            "execution": execution,
            "account": after,
            "live_orders_sent": False,
            "network_access": False,
        }

    @staticmethod
    def _blocked(code: str, now: datetime) -> dict[str, Any]:
        return {
            "status": "DATA_BLOCKED",
            "mode": "FOREX_PAPER_ONLY",
            "assessed_at": now.isoformat(),
            "reason": code,
            "live_orders_sent": False,
            "network_access": False,
        }


__all__ = ["ForexPaperAutopilot"]
