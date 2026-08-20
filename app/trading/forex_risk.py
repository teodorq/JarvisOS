"""Portfolio-level currency exposure and risk gates for Forex paper plans."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Iterable, Mapping

from app.trading.forex_models import ForexPair, ForexPosition, ForexQuote
from app.trading.models import (
    TradingValidationError,
    aware_utc,
    decimal_value,
    normalized_currency,
)


@dataclass(frozen=True, slots=True)
class ForexPaperPolicy:
    account_currency: str = "PLN"
    risk_per_trade_pct: Decimal = Decimal("0.0025")
    max_total_open_risk_pct: Decimal = Decimal("0.005")
    max_daily_loss_pct: Decimal = Decimal("0.01")
    max_currency_gross_exposure_pct: Decimal = Decimal("0.10")
    max_open_positions: int = 2
    minimum_units: Decimal = Decimal("100")
    maximum_units: Decimal = Decimal("10000")
    max_conversion_age_seconds: int = 30
    take_profit_reward_risk: Decimal = Decimal("2")
    live_trading_enabled: bool = field(default=False, init=False)
    leverage_enabled: bool = field(default=False, init=False)
    martingale_enabled: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "account_currency", normalized_currency(self.account_currency)
        )
        for name, value, maximum in (
            ("risk_per_trade_pct", self.risk_per_trade_pct, Decimal("0.005")),
            (
                "max_total_open_risk_pct",
                self.max_total_open_risk_pct,
                Decimal("0.01"),
            ),
            ("max_daily_loss_pct", self.max_daily_loss_pct, Decimal("0.02")),
            (
                "max_currency_gross_exposure_pct",
                self.max_currency_gross_exposure_pct,
                Decimal("0.25"),
            ),
        ):
            if not isinstance(value, Decimal) or not Decimal("0.0001") <= value <= maximum:
                raise TradingValidationError(f"forex_policy: unsafe_{name}")
        if self.max_total_open_risk_pct < self.risk_per_trade_pct:
            raise TradingValidationError("forex_policy: total_risk_below_trade_risk")
        if not 1 <= self.max_open_positions <= 5:
            raise TradingValidationError("forex_policy: unsafe_position_count")
        if not (
            isinstance(self.minimum_units, Decimal)
            and isinstance(self.maximum_units, Decimal)
            and Decimal("1") <= self.minimum_units <= self.maximum_units <= Decimal("100000")
        ):
            raise TradingValidationError("forex_policy: unsafe_unit_limits")
        if not 1 <= self.max_conversion_age_seconds <= 300:
            raise TradingValidationError("forex_policy: unsafe_conversion_age")
        if not (
            isinstance(self.take_profit_reward_risk, Decimal)
            and Decimal("1") <= self.take_profit_reward_risk <= Decimal("5")
        ):
            raise TradingValidationError("forex_policy: unsafe_take_profit_reward_risk")


class ForexRateBook:
    """Convert currencies through fresh quote midpoints without network calls."""

    def __init__(
        self,
        quotes: Iterable[ForexQuote],
        *,
        now: datetime | None = None,
        max_age_seconds: int = 30,
    ) -> None:
        self.now = aware_utc(now or datetime.now(timezone.utc), "now")
        self.max_age_seconds = max_age_seconds
        self.quotes = tuple(quotes)
        if len({quote.pair.symbol for quote in self.quotes}) != len(self.quotes):
            raise TradingValidationError("forex_rates: duplicate_pair")
        for quote in self.quotes:
            age = (self.now - quote.timestamp).total_seconds()
            if age < -2 or age > self.max_age_seconds:
                raise TradingValidationError("forex_rates: stale_quote")

    def rate(self, source: object, target: object) -> Decimal:
        source_currency = normalized_currency(source)
        target_currency = normalized_currency(target)
        if source_currency == target_currency:
            return Decimal("1")
        graph: dict[str, list[tuple[str, Decimal]]] = defaultdict(list)
        for quote in self.quotes:
            midpoint = quote.midpoint
            graph[quote.pair.base_currency].append(
                (quote.pair.quote_currency, midpoint)
            )
            graph[quote.pair.quote_currency].append(
                (quote.pair.base_currency, Decimal("1") / midpoint)
            )
        queue: deque[tuple[str, Decimal, int]] = deque(
            [(source_currency, Decimal("1"), 0)]
        )
        visited = {source_currency}
        while queue:
            currency, accumulated, depth = queue.popleft()
            if depth >= 3:
                continue
            for neighbor, edge_rate in graph.get(currency, []):
                if neighbor == target_currency:
                    return accumulated * edge_rate
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, accumulated * edge_rate, depth + 1))
        raise TradingValidationError(
            f"forex_rates: no_conversion_{source_currency}_{target_currency}"
        )

    def convert(self, amount: object, source: object, target: object) -> Decimal:
        value = Decimal(str(amount))
        if not value.is_finite():
            raise TradingValidationError("forex_rates: invalid_amount")
        return value * self.rate(source, target)


@dataclass(frozen=True, slots=True)
class ForexRiskDecision:
    allowed: bool
    code: str
    reason: str
    units: Decimal = Decimal("0")
    risk_pln: Decimal = Decimal("0")
    projected_currency_exposure_pln: Mapping[str, Decimal] = field(
        default_factory=dict
    )


class ForexPortfolioRiskEngine:
    """Size one paper candidate and enforce aggregate currency risk."""

    def __init__(self, policy: ForexPaperPolicy | None = None) -> None:
        self.policy = policy or ForexPaperPolicy()

    def evaluate_open(
        self,
        *,
        pair: ForexPair,
        side: str,
        entry_price: object,
        stop_loss: object,
        equity_pln: object,
        daily_pnl_pln: object,
        positions: Iterable[ForexPosition],
        rates: ForexRateBook,
        now: datetime | None = None,
    ) -> ForexRiskDecision:
        aware_utc(now or datetime.now(timezone.utc), "now")
        normalized_side = str(side or "").strip().upper()
        if normalized_side not in {"LONG", "SHORT"}:
            return self._deny("INVALID_SIDE", "Kierunek musi być LONG albo SHORT.")
        entry = decimal_value(entry_price, "entry_price")
        stop = decimal_value(stop_loss, "stop_loss")
        if normalized_side == "LONG" and stop >= entry:
            return self._deny("INVALID_STOP", "Stop LONG musi być poniżej wejścia.")
        if normalized_side == "SHORT" and stop <= entry:
            return self._deny("INVALID_STOP", "Stop SHORT musi być powyżej wejścia.")
        equity = decimal_value(equity_pln, "equity_pln")
        daily_pnl = Decimal(str(daily_pnl_pln))
        if not daily_pnl.is_finite():
            return self._deny("INVALID_DAILY_PNL", "Dzienny wynik jest nieprawidłowy.")
        current = tuple(positions)
        if daily_pnl <= -(equity * self.policy.max_daily_loss_pct):
            return self._deny("DAILY_LOSS_LIMIT", "Osiągnięto dzienny limit straty.")
        if len(current) >= self.policy.max_open_positions:
            return self._deny("POSITION_COUNT_LIMIT", "Osiągnięto limit otwartych pozycji.")
        if any(position.pair.symbol == pair.symbol for position in current):
            return self._deny("PAIR_ALREADY_OPEN", "Ta para ma już otwartą pozycję.")

        per_unit_risk_quote = abs(entry - stop)
        per_unit_risk_pln = abs(rates.convert(
            per_unit_risk_quote,
            pair.quote_currency,
            self.policy.account_currency,
        ))
        if per_unit_risk_pln <= 0:
            return self._deny("INVALID_RISK", "Nie można obliczyć ryzyka jednostki.")
        risk_budget = equity * self.policy.risk_per_trade_pct
        units_by_risk = (risk_budget / per_unit_risk_pln).to_integral_value(
            rounding=ROUND_DOWN
        )
        existing_exposure = self.currency_gross_exposure_pln(current, rates)
        exposure_cap = equity * self.policy.max_currency_gross_exposure_pct
        base_per_unit = abs(rates.convert(
            Decimal("1"), pair.base_currency, self.policy.account_currency
        ))
        quote_per_unit = abs(rates.convert(
            entry, pair.quote_currency, self.policy.account_currency
        ))
        base_room = max(
            Decimal("0"),
            exposure_cap - existing_exposure.get(pair.base_currency, Decimal("0")),
        )
        quote_room = max(
            Decimal("0"),
            exposure_cap - existing_exposure.get(pair.quote_currency, Decimal("0")),
        )
        units_by_exposure = min(
            (base_room / base_per_unit).to_integral_value(rounding=ROUND_DOWN),
            (quote_room / quote_per_unit).to_integral_value(rounding=ROUND_DOWN),
        )
        units = min(
            units_by_risk,
            units_by_exposure,
            self.policy.maximum_units,
        )
        if units < self.policy.minimum_units:
            return self._deny(
                "EXPOSURE_LIMIT",
                "Brak miejsca na minimalną pozycję w limicie walutowym.",
            )
        proposed = ForexPosition(
            pair=pair,
            side=normalized_side,
            units=units,
            entry_price=entry,
            current_price=entry,
            stop_loss=stop,
            opened_at=rates.now,
        )
        projected = current + (proposed,)
        total_risk = sum(
            (self.position_risk_pln(position, rates) for position in projected),
            Decimal("0"),
        )
        if total_risk > equity * self.policy.max_total_open_risk_pct:
            return self._deny("TOTAL_RISK_LIMIT", "Łączne ryzyko pozycji jest za duże.")
        projected_exposure = self.currency_gross_exposure_pln(projected, rates)
        if any(value > exposure_cap for value in projected_exposure.values()):
            return self._deny("CURRENCY_EXPOSURE_LIMIT", "Przekroczono ekspozycję waluty.")
        return ForexRiskDecision(
            allowed=True,
            code="ALLOWED",
            reason="Wszystkie portfelowe limity PAPER ONLY zostały spełnione.",
            units=units,
            risk_pln=per_unit_risk_pln * units,
            projected_currency_exposure_pln=projected_exposure,
        )

    def position_risk_pln(
        self, position: ForexPosition, rates: ForexRateBook
    ) -> Decimal:
        risk_quote = abs(position.entry_price - position.stop_loss) * position.units
        return abs(rates.convert(
            risk_quote,
            position.pair.quote_currency,
            self.policy.account_currency,
        ))

    def currency_gross_exposure_pln(
        self,
        positions: Iterable[ForexPosition],
        rates: ForexRateBook,
    ) -> dict[str, Decimal]:
        exposure: dict[str, Decimal] = defaultdict(Decimal)
        for position in positions:
            base_amount = position.units
            quote_amount = position.units * position.current_price
            exposure[position.pair.base_currency] += abs(rates.convert(
                base_amount,
                position.pair.base_currency,
                self.policy.account_currency,
            ))
            exposure[position.pair.quote_currency] += abs(rates.convert(
                quote_amount,
                position.pair.quote_currency,
                self.policy.account_currency,
            ))
        return dict(exposure)

    @staticmethod
    def _deny(code: str, reason: str) -> ForexRiskDecision:
        return ForexRiskDecision(False, code, reason)


__all__ = [
    "ForexPaperPolicy",
    "ForexPortfolioRiskEngine",
    "ForexRateBook",
    "ForexRiskDecision",
]
