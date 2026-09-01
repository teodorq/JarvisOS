"""Local MetaTrader 5 DEMO market data adapter with no order surface."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import importlib
import re
import time
from typing import Any, Iterable, Mapping

from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    ForexQuote,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.models import TradingValidationError, aware_utc


_SYMBOL_SUFFIX = re.compile(r"^[A-Za-z0-9._-]{0,12}$")
_LOCAL_TIME_SERVERS = frozenset({"OANDATMS-MT5"})
_MAX_READY_QUOTE_AGE_SECONDS = 10
_MAX_READY_CLOSED_BAR_AGE_SECONDS = 1_860


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


def mt5_market_snapshot_fresh(
    pairs: Iterable[ForexPair],
    quotes: Mapping[str, ForexQuote],
    bars: Mapping[str, Iterable[ForexBar]],
    *,
    now: datetime,
) -> bool:
    """Return true only for a complete, currently synchronized MT5 snapshot."""

    selected = tuple(pairs)
    selected_now = aware_utc(now, "now")
    if not selected or set(quotes) != {pair.symbol for pair in selected}:
        return False
    if set(bars) != {pair.symbol for pair in selected}:
        return False
    for pair in selected:
        quote = quotes.get(pair.symbol)
        series = tuple(bars.get(pair.symbol, ()))
        if quote is None or quote.pair != pair or not series:
            return False
        if series[-1].pair != pair:
            return False
        quote_age = (selected_now - quote.timestamp).total_seconds()
        bar_age = (selected_now - series[-1].timestamp).total_seconds()
        if not -2 <= quote_age <= _MAX_READY_QUOTE_AGE_SECONDS:
            return False
        if not -2 <= bar_age <= _MAX_READY_CLOSED_BAR_AGE_SECONDS:
            return False
    return True


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
        now: datetime | None = None,
    ) -> tuple[dict[str, ForexQuote], dict[str, tuple[ForexBar, ...]]]:
        selected = tuple(pairs)
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        symbols = tuple(pair.symbol for pair in selected)
        if (
            not symbols
            or len(set(symbols)) != len(symbols)
            or not 31 <= bar_count <= 499
            or any(
                not pair.tradable
                and pair.symbol != USD_PLN_CONVERSION_PAIR.symbol
                for pair in selected
            )
        ):
            raise TradingValidationError("mt5_demo: invalid_market_request")

        mt5 = self._load_module()
        initialized = False
        try:
            if not mt5.initialize(timeout=10_000):
                raise TradingValidationError("mt5_demo: terminal_unavailable")
            initialized = True
            server = self._validate_demo_session(mt5)
            quotes: dict[str, ForexQuote] = {}
            bars: dict[str, tuple[ForexBar, ...]] = {}
            terminal_symbols: dict[str, tuple[ForexPair, str]] = {}
            for pair in selected:
                terminal_symbol = pair.symbol.replace("_", "") + self.symbol_suffix
                if not mt5.symbol_select(terminal_symbol, True):
                    raise TradingValidationError("mt5_demo: symbol_unavailable")
                terminal_symbols[pair.symbol] = (pair, terminal_symbol)
            first_terminal_symbol = next(iter(terminal_symbols.values()))[1]
            offset_deadline = time.monotonic() + 8.0
            while True:
                try:
                    server_offset_seconds = self._server_time_offset(
                        mt5,
                        first_terminal_symbol,
                        server,
                        selected_now,
                    )
                    break
                except TradingValidationError as error:
                    if str(error) == "mt5_demo: unsupported_server_time_offset":
                        raise
                    if time.monotonic() >= offset_deadline:
                        raise TradingValidationError(
                            "mt5_demo: market_sync_timeout"
                        ) from error
                    time.sleep(0.2)
            pending = dict(terminal_symbols)
            deadline = time.monotonic() + 8.0
            last_sync_error: TradingValidationError | None = None
            while pending:
                for symbol, (pair, terminal_symbol) in tuple(pending.items()):
                    try:
                        quote = self._quote(
                            mt5,
                            pair,
                            terminal_symbol,
                            server_offset_seconds,
                        )
                        series = self._bars(
                            mt5,
                            pair,
                            terminal_symbol,
                            bar_count,
                            server_offset_seconds,
                        )
                    except TradingValidationError as error:
                        last_sync_error = error
                        continue
                    quotes[symbol] = quote
                    bars[symbol] = series
                    pending.pop(symbol)
                if not pending:
                    break
                if time.monotonic() >= deadline:
                    raise TradingValidationError(
                        "mt5_demo: market_sync_timeout"
                    ) from last_sync_error
                time.sleep(0.2)
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

    def fetch_history(
        self,
        pairs: Iterable[ForexPair],
        *,
        bar_count: int = 5_000,
        now: datetime | None = None,
    ) -> dict[str, tuple[ForexBar, ...]]:
        """Read closed M15 history after proving the terminal account is DEMO."""
        selected = tuple(pairs)
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        symbols = tuple(pair.symbol for pair in selected)
        if (
            not symbols
            or len(set(symbols)) != len(symbols)
            or type(bar_count) is not int
            or not 200 <= bar_count <= 50_000
            or any(
                not pair.tradable and pair.symbol != "USD_PLN"
                for pair in selected
            )
        ):
            raise TradingValidationError("mt5_demo: invalid_history_request")

        mt5 = self._load_module()
        initialized = False
        try:
            if not mt5.initialize(timeout=10_000):
                raise TradingValidationError("mt5_demo: terminal_unavailable")
            initialized = True
            server = self._validate_demo_session(mt5)
            terminal_symbols: dict[str, tuple[ForexPair, str]] = {}
            for pair in selected:
                terminal_symbol = pair.symbol.replace("_", "") + self.symbol_suffix
                if not mt5.symbol_select(terminal_symbol, True):
                    raise TradingValidationError("mt5_demo: symbol_unavailable")
                terminal_symbols[pair.symbol] = (pair, terminal_symbol)
            first_terminal_symbol = next(iter(terminal_symbols.values()))[1]
            server_offset_seconds = self._wait_for_server_offset(
                mt5,
                first_terminal_symbol,
                server,
                selected_now,
            )
            pending = dict(terminal_symbols)
            history: dict[str, tuple[ForexBar, ...]] = {}
            deadline = time.monotonic() + 15.0
            last_sync_error: TradingValidationError | None = None
            while pending:
                for symbol, (pair, terminal_symbol) in tuple(pending.items()):
                    try:
                        history[symbol] = self._bars(
                            mt5,
                            pair,
                            terminal_symbol,
                            bar_count,
                            server_offset_seconds,
                        )
                    except TradingValidationError as error:
                        last_sync_error = error
                        continue
                    pending.pop(symbol)
                if not pending:
                    break
                if time.monotonic() >= deadline:
                    raise TradingValidationError(
                        "mt5_demo: history_sync_timeout"
                    ) from last_sync_error
                time.sleep(0.2)
            return history
        except TradingValidationError:
            raise
        except Exception as error:
            raise TradingValidationError("mt5_demo: history_unavailable") from error
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
    def _validate_demo_session(mt5: Any) -> str:
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
        return str(getattr(account, "server", "") or "").strip().upper()

    @staticmethod
    def _raw_tick_seconds(tick: object) -> float:
        milliseconds = int(getattr(tick, "time_msc", 0) or 0)
        seconds = (
            milliseconds / 1000
            if milliseconds
            else int(getattr(tick, "time", 0) or 0)
        )
        if seconds <= 0:
            raise TradingValidationError("mt5_demo: invalid_tick_time")
        return seconds

    @classmethod
    def _server_time_offset(
        cls,
        mt5: Any,
        terminal_symbol: str,
        server: str,
        now: datetime,
    ) -> int:
        tick = mt5.symbol_info_tick(terminal_symbol)
        if tick is None:
            raise TradingValidationError("mt5_demo: quote_unavailable")
        raw_time = datetime.fromtimestamp(
            cls._raw_tick_seconds(tick), tz=timezone.utc
        )
        future_seconds = (raw_time - now).total_seconds()
        if future_seconds <= 2:
            return 0
        whole_hours = int(round(future_seconds / 3600))
        residual_seconds = abs(future_seconds - whole_hours * 3600)
        if (
            server not in _LOCAL_TIME_SERVERS
            or not 1 <= whole_hours <= 3
            or residual_seconds > 120
        ):
            raise TradingValidationError(
                "mt5_demo: unsupported_server_time_offset"
            )
        return whole_hours * 3600

    @classmethod
    def _wait_for_server_offset(
        cls,
        mt5: Any,
        terminal_symbol: str,
        server: str,
        now: datetime,
    ) -> int:
        deadline = time.monotonic() + 8.0
        while True:
            try:
                return cls._server_time_offset(
                    mt5,
                    terminal_symbol,
                    server,
                    now,
                )
            except TradingValidationError as error:
                if str(error) == "mt5_demo: unsupported_server_time_offset":
                    raise
                if time.monotonic() >= deadline:
                    raise TradingValidationError(
                        "mt5_demo: market_sync_timeout"
                    ) from error
                time.sleep(0.2)

    @classmethod
    def _quote(
        cls,
        mt5: Any,
        pair: ForexPair,
        terminal_symbol: str,
        server_offset_seconds: int,
    ) -> ForexQuote:
        tick = mt5.symbol_info_tick(terminal_symbol)
        if tick is None:
            raise TradingValidationError("mt5_demo: quote_unavailable")
        seconds = cls._raw_tick_seconds(tick) - server_offset_seconds
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
        server_offset_seconds: int,
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
                    (
                        int(_value(row, "time", "mt5_demo: invalid_bar"))
                        - server_offset_seconds
                    ),
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


__all__ = ["Mt5DemoReadOnlySource", "mt5_market_snapshot_fresh"]
