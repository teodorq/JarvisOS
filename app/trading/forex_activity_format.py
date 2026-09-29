"""Safe owner-facing formatting for Forex PAPER activity."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def realized_r_text(value: object) -> str:
    if value is None or str(value).strip() == "":
        return ""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if not number.is_finite() or abs(number) > Decimal("1000000"):
        return ""
    return f"{number:.4f}"


__all__ = ["realized_r_text"]
