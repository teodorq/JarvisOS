"""Small formatting helpers for the read-only Forex PAPER page."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


def fill_forex_positions(
    table: QTableWidget,
    positions: list[dict[str, Any]],
    *,
    column_count: int,
    empty_message: str = "BRAK OTWARTYCH POZYCJI PAPER",
) -> None:
    table.clearSpans()
    if not positions:
        table.setRowCount(1)
        item = QTableWidgetItem(empty_message)
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(0, 0, item)
        table.setSpan(0, 0, 1, column_count)
        return
    table.setRowCount(len(positions))
    keys = (
        "pair", "side", "units", "entry_price", "current_price",
        "stop_loss", "take_profit", "initial_risk_pln",
    )
    for row, position in enumerate(positions):
        values = [str(position.get(key, "—")) for key in keys]
        values[0] = values[0].replace("_", "/")
        values[1] = (
            "KUPNO / LONG" if values[1] == "LONG" else "SPRZEDAŻ / SHORT"
        )
        values[-1] = (
            f"{values[-1]} PLN"
            if position.get("risk_recorded") else "BRAK ZAPISU"
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, column, item)


def visible_forex_time(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "lokalna księga"
    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        ).astimezone().strftime("%d.%m.%Y %H:%M:%S")
    except ValueError:
        return text[:32]


def forex_pnl_hint(value: object) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        number = Decimal("0")
    if not number.is_finite():
        number = Decimal("0")
    if number > 0:
        return "ZYSK"
    if number < 0:
        return "STRATA"
    return "BEZ ZMIAN"


__all__ = ["fill_forex_positions", "forex_pnl_hint", "visible_forex_time"]
