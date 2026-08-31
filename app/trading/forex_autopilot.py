"""One fail-closed autonomous cycle for the local Forex paper environment."""

from __future__ import annotations

from copy import deepcopy
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
from app.trading.forex_sample_contract import build_forex_paper_sample_contract
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
        self.sample_contract = build_forex_paper_sample_contract(
            scanner_policy=self.scanner.policy,
            paper_policy=self.policy,
            universe=self.scanner.universe,
        )
        self.executor = ForexPaperExecutionEngine(
            project_root,
            policy=self.policy,
            sample_contract=self.sample_contract,
        )

    def run_cycle(
        self,
        *,
        quotes: Mapping[str, ForexQuote],
        bars: Mapping[str, Iterable[ForexBar]],
        contexts: Mapping[str, ForexSafetyContext],
        conversion_quotes: Iterable[ForexQuote],
        cycle_id: object,
        allow_new_entries: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        if type(allow_new_entries) is not bool:
            return self._blocked("INVALID_ENTRY_PERMISSION", selected_now)
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
            before = self.executor.status(
                quotes=quotes,
                rates=rates,
                now=selected_now,
            )
            plan = self.coordinator.plan(
                assessments=assessments,
                quotes=quotes,
                positions=current_positions,
                rates=rates,
                equity_pln=before["equity_pln"],
                daily_pnl_pln=before["daily_pnl_pln"],
                now=selected_now,
            )
            plan["sample_contract"] = deepcopy(self.sample_contract)
            if not allow_new_entries:
                plan = self._without_entries(plan)
            execution = self.executor.apply_plan(
                plan,
                quotes=quotes,
                rates=rates,
                cycle_id=cycle_id,
                now=selected_now,
            )
            after = self.executor.status(
                quotes=quotes,
                rates=rates,
                now=selected_now,
            )
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
            "new_entries_allowed": allow_new_entries,
            "live_orders_sent": False,
            "network_access": False,
        }

    @staticmethod
    def _without_entries(plan: Mapping[str, Any]) -> dict[str, Any]:
        """Keep verified closes while making any new entry unexecutable."""

        value = dict(plan)
        raw_instructions = value.get("instructions", [])
        instructions = [
            dict(item)
            for item in raw_instructions
            if isinstance(item, Mapping)
            and str(item.get("action", "")).upper() == "CLOSE_POSITION"
        ] if isinstance(raw_instructions, (list, tuple)) else []
        dropped = (
            len(raw_instructions) - len(instructions)
            if isinstance(raw_instructions, (list, tuple))
            else 0
        )
        rejected = [
            dict(item)
            for item in value.get("rejected", [])
            if isinstance(item, Mapping)
        ]
        if dropped:
            rejected.append({
                "pair": "PORTFOLIO",
                "code": "NEW_ENTRIES_BLOCKED_BY_DATA_GATE",
            })
        value["status"] = "CLOSES_READY" if instructions else "NO_ACTION"
        value["instructions"] = instructions
        value["rejected"] = rejected
        value["new_entries_allowed"] = False
        value["live_orders_sent"] = False
        value["network_access"] = False
        return value

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
