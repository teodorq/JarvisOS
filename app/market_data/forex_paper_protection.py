"""Fast local stop-loss/take-profit guard for existing Forex PAPER positions."""

from __future__ import annotations

from datetime import datetime, timezone
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
        now: datetime | None = None,
    ) -> tuple[dict[str, ForexQuote], dict[str, tuple[ForexBar, ...]]]: ...


class ForexPaperProtectionRuntime:
    """Close an existing PAPER position on SL/TP; never create an entry."""

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
    ) -> dict[str, Any]:
        selected_id = str(cycle_id or "").strip()
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        if not self.settings.paper_autopilot_enabled:
            return self._blocked(selected_id, "PAPER_AUTOPILOT_NOT_ENABLED")
        if self.settings.primary_provider != "MT5_DEMO":
            return self._blocked(selected_id, "MT5_DEMO_PRIMARY_REQUIRED")
        try:
            positions = self.executor.positions()
            if not positions:
                return self._result(
                    "NO_OPEN_POSITIONS",
                    selected_id,
                    selected_now,
                    execution=None,
                    account=self.executor.status(now=selected_now),
                )
            requested_pairs = self._requested_pairs(positions.values())
            quotes, bars = self.source.fetch_market(
                requested_pairs,
                bar_count=31,
                now=selected_now,
            )
            if not mt5_market_snapshot_fresh(
                requested_pairs,
                quotes,
                bars,
                now=selected_now,
            ):
                return self._blocked(selected_id, "MT5_PROTECTION_DATA_STALE")
            rates = ForexRateBook(quotes.values(), now=selected_now)
            account = self.executor.status(
                quotes=quotes,
                rates=rates,
                now=selected_now,
            )
            plan = self.coordinator.plan(
                assessments=(),
                quotes=quotes,
                positions=positions,
                rates=rates,
                equity_pln=account.get("equity_pln", "0"),
                daily_pnl_pln=account.get("daily_pnl_pln", "0"),
                now=selected_now,
            )
            instructions = list(plan.get("instructions", []) or [])
            if any(
                not isinstance(item, dict)
                or item.get("action") != "CLOSE_POSITION"
                for item in instructions
            ):
                return self._blocked(selected_id, "PROTECTION_PLAN_NOT_CLOSE_ONLY")
            if not instructions:
                return self._result(
                    "NO_PROTECTION_TRIGGER",
                    selected_id,
                    selected_now,
                    execution=None,
                    account=account,
                )
            execution = self.executor.apply_plan(
                plan,
                quotes=quotes,
                rates=rates,
                cycle_id=selected_id,
                now=selected_now,
            )
            return self._result(
                "PAPER_PROTECTION_APPLIED",
                selected_id,
                selected_now,
                execution=execution,
                account=self.executor.status(now=selected_now),
            )
        except (OSError, RuntimeError, TradingValidationError) as error:
            return self._blocked(
                selected_id,
                str(error)[:160] or "PAPER_PROTECTION_FAILED",
            )

    @staticmethod
    def _requested_pairs(
        positions: Iterable[ForexPosition],
    ) -> tuple[ForexPair, ...]:
        unique = {position.pair.symbol: position.pair for position in positions}
        unique[USD_PLN_CONVERSION_PAIR.symbol] = USD_PLN_CONVERSION_PAIR
        return tuple(unique[symbol] for symbol in sorted(unique))

    @staticmethod
    def _result(
        status: str,
        cycle_id: str,
        now: datetime,
        *,
        execution: dict[str, Any] | None,
        account: dict[str, Any],
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
            "new_entries_allowed": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    @staticmethod
    def _blocked(cycle_id: str, reason: str) -> dict[str, Any]:
        return {
            "status": "PAPER_PROTECTION_BLOCKED",
            "mode": "FOREX_PAPER_POSITION_PROTECTION_ONLY",
            "cycle_id": cycle_id,
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
