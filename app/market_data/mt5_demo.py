"""Local MetaTrader 5 DEMO market data adapter with no order surface."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import importlib
import re
from typing import Any, Iterable, Mapping

from app.trading.forex_models import ForexBar, ForexPair, ForexQuote
from app.trading.models import TradingValidationError


_SYMBOL_SUFFIX = re.compile(r"^[A-Za-z0-9._-]{0,12}$")


def _value(record: object, field: str, code: str) -> object:
    if isinstance(record, Mapping):
        if field not in record:
            raise TradingValidationError(code)
        return record[field]
    try:
        return record[field]  # type: ignore[index]
    except (IndexError, KeyError, TypeError):
        try:
            return getattr(record, field)
        except AttributeError as error:
            raise TradingValidationError(code) from error


class Mt5DemoReadOnlySource:
    """Read quotes and closed M15 bars only after proving the account is DEMO."""

    def __init__(self, *, symbol_suffix: str = "", module: object | None = None) -> None:
        suffix = str(symbol_suffix or "").strip()
        if not _SYMBOL_SUFFIX.fullmatch(suffix):
            raise TradingValidationError("mt5_demo: invalid_symbol_suffix")
        self.symbol_suffix = suffix
        self._module = module

    def fetch_market(
        self,
        pairs: Iterable[ForexPair],
        *,
        bar_count: int = 31,
    ) -> tuple[dict[str, ForexQuote], dict[str, tuple[ForexBar, ...]]]:
        selected = tuple(pairs)
        symbols = tuple(pair.symbol for pair in selected)
        if (
            not symbols
            or len(set(symbols)) != len(symbols)
            or not 31 <= bar_count <= 499
            or any(not pair.tradable for pair in selected)
        ):
            raise TradingValidationError("mt5_demo: invalid_market_request")

        mt5 = self._load_module()
        initialized = False
        try:
            if not mt5.initialize(timeout=10_000):
                raise TradingValidationError("mt5_demo: terminal_unavailable")
            initialized = True
            self._validate_demo_session(mt5)
            quotes: dict[str, ForexQuote] = {}
            bars: dict[str, tuple[ForexBar, ...]] = {}
            for pair in selected:
                terminal_symbol = pair.symbol.replace("_", "") + self.symbol_suffix
                if not mt5.symbol_select(terminal_symbol, True):
                    raise TradingValidationError("mt5_demo: symbol_unavailable")
                quotes[pair.symbol] = self._quote(mt5, pair, terminal_symbol)
                bars[pair.symbol] = self._bars(mt5, pair, terminal_symbol, bar_count)
            return quotes, bars
        except TradingValidationError:
            raise
        except Exception as error:
            raise TradingValidationError("mt5_demo: data_unavailable") from error
        finally:
            if initialized:
                try:
                    mt5.shutdown()
                except Exception:
                    pass

    def _load_module(self) -> Any:
        if self._module is not None:
            return self._module
        try:
            return importlib.import_module("MetaTrader5")
        except (ImportError, OSError) as error:
            raise TradingValidationError("mt5_demo: package_unavailable") from error

    @staticmethod
    def _validate_demo_session(mt5: Any) -> None:
        terminal = mt5.terminal_info()
        if terminal is None or getattr(terminal, "connected", False) is not True:
            raise TradingValidationError("mt5_demo: terminal_disconnected")
        account = mt5.account_info()
        if account is None:
            raise TradingValidationError("mt5_demo: account_unavailable")
        demo_mode = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
        if demo_mode is None or getattr(account, "trade_mode", None) != demo_mode:
            raise TradingValidationError("mt5_demo: real_or_non_demo_account_blocked")
        if int(getattr(account, "login", 0) or 0) <= 0:
            raise TradingValidationError("mt5_demo: invalid_demo_account")

    @staticmethod
    def _quote(mt5: Any, pair: ForexPair, terminal_symbol: str) -> ForexQuote:
        tick = mt5.symbol_info_tick(terminal_symbol)
        if tick is None:
            raise TradingValidationError("mt5_demo: quote_unavailable")
        milliseconds = int(getattr(tick, "time_msc", 0) or 0)
        seconds = milliseconds / 1000 if milliseconds else int(getattr(tick, "time", 0) or 0)
        if seconds <= 0:
            raise TradingValidationError("mt5_demo: invalid_tick_time")
        return ForexQuote.create(
            pair=pair,
            bid=Decimal(str(getattr(tick, "bid", 0))),
            ask=Decimal(str(getattr(tick, "ask", 0))),
            timestamp=datetime.fromtimestamp(seconds, tz=timezone.utc),
        )

    @staticmethod
    def _bars(
        mt5: Any,
        pair: ForexPair,
        terminal_symbol: str,
        count: int,
    ) -> tuple[ForexBar, ...]:
        timeframe = getattr(mt5, "TIMEFRAME_M15", None)
        if timeframe is None:
            raise TradingValidationError("mt5_demo: timeframe_unavailable")
        rows = mt5.copy_rates_from_pos(terminal_symbol, timeframe, 1, count)
        if rows is None or len(rows) < count:
            raise TradingValidationError("mt5_demo: incomplete_bars")
        bars = [
            ForexBar.create(
                pair=pair,
                timestamp=datetime.fromtimestamp(
                    int(_value(row, "time", "mt5_demo: invalid_bar")),
                    tz=timezone.utc,
                ),
                open=_value(row, "open", "mt5_demo: invalid_bar"),
                high=_value(row, "high", "mt5_demo: invalid_bar"),
                low=_value(row, "low", "mt5_demo: invalid_bar"),
                close=_value(row, "close", "mt5_demo: invalid_bar"),
                tick_volume=_value(row, "tick_volume", "mt5_demo: invalid_bar"),
            )
            for row in rows
        ]
        bars.sort(key=lambda item: item.timestamp)
        selected = tuple(bars[-count:])
        if len({bar.timestamp for bar in selected}) != count:
            raise TradingValidationError("mt5_demo: duplicate_bars")
        return selected


__all__ = ["Mt5DemoReadOnlySource"]
