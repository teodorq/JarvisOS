"""Conservative hard limits for the JARVIS OS paper-trading environment."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.trading.models import TradingValidationError, normalized_currency


def _bounded_decimal(
    value: Decimal,
    name: str,
    *,
    minimum: Decimal,
    maximum: Decimal,
) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TradingValidationError(f"{name}: invalid")
    if value < minimum or value > maximum:
        raise TradingValidationError(f"{name}: outside_safe_range")
    return value


@dataclass(frozen=True, slots=True)
class PaperTradingPolicy:
    base_currency: str = "PLN"
    initial_cash: Decimal = Decimal("100000")
    max_order_notional_pct: Decimal = Decimal("0.02")
    max_position_pct: Decimal = Decimal("0.05")
    max_gross_exposure_pct: Decimal = Decimal("0.20")
    max_daily_loss_pct: Decimal = Decimal("0.01")
    max_spread_pct: Decimal = Decimal("0.02")
    max_orders_per_day: int = 20
    max_quote_age_seconds: int = 30
    slippage_bps: Decimal = Decimal("5")
    commission_bps: Decimal = Decimal("2")
    minimum_commission: Decimal = Decimal("0.01")
    live_trading_enabled: bool = field(default=False, init=False)
    short_selling_enabled: bool = field(default=False, init=False)
    leverage_enabled: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_currency", normalized_currency(self.base_currency))
        _bounded_decimal(
            self.initial_cash,
            "initial_cash",
            minimum=Decimal("100"),
            maximum=Decimal("10000000"),
        )
        for name, value, maximum in (
            ("max_order_notional_pct", self.max_order_notional_pct, Decimal("0.05")),
            ("max_position_pct", self.max_position_pct, Decimal("0.10")),
            ("max_gross_exposure_pct", self.max_gross_exposure_pct, Decimal("0.50")),
            ("max_daily_loss_pct", self.max_daily_loss_pct, Decimal("0.05")),
            ("max_spread_pct", self.max_spread_pct, Decimal("0.10")),
        ):
            _bounded_decimal(
                value,
                name,
                minimum=Decimal("0.0001"),
                maximum=maximum,
            )
        if self.max_position_pct < self.max_order_notional_pct:
            raise TradingValidationError("max_position_pct: below_order_limit")
        if self.max_gross_exposure_pct < self.max_position_pct:
            raise TradingValidationError("max_gross_exposure_pct: below_position_limit")
        if not 1 <= self.max_orders_per_day <= 100:
            raise TradingValidationError("max_orders_per_day: outside_safe_range")
        if not 1 <= self.max_quote_age_seconds <= 300:
            raise TradingValidationError("max_quote_age_seconds: outside_safe_range")
        for name, value in (
            ("slippage_bps", self.slippage_bps),
            ("commission_bps", self.commission_bps),
        ):
            _bounded_decimal(
                value,
                name,
                minimum=Decimal("0"),
                maximum=Decimal("100"),
            )
        _bounded_decimal(
            self.minimum_commission,
            "minimum_commission",
            minimum=Decimal("0"),
            maximum=Decimal("100"),
        )

    def status(self) -> dict[str, Any]:
        return {
            "mode": "PAPER_ONLY",
            "base_currency": self.base_currency,
            "initial_cash": str(self.initial_cash),
            "max_order_notional_pct": str(self.max_order_notional_pct),
            "max_position_pct": str(self.max_position_pct),
            "max_gross_exposure_pct": str(self.max_gross_exposure_pct),
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "max_spread_pct": str(self.max_spread_pct),
            "max_orders_per_day": self.max_orders_per_day,
            "max_quote_age_seconds": self.max_quote_age_seconds,
            "live_trading_enabled": False,
            "short_selling_enabled": False,
            "leverage_enabled": False,
        }


__all__ = ["PaperTradingPolicy"]
