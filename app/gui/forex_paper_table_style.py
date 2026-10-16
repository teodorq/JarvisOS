"""Shared table presentation for the read-only Forex PAPER dashboard."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QTableWidget


_TABLE_STYLE = """
    QTableWidget {
        background-color: #08101C;
        alternate-background-color: #0B1626;
        color: #E8EEF8;
        border: 1px solid #22314A;
        border-radius: 8px;
        selection-background-color: #174B66;
        selection-color: #FFFFFF;
        outline: none;
    }
    QTableWidget::item {
        border-bottom: 1px solid #17263D;
        padding: 7px;
    }
    QHeaderView::section {
        background-color: #111D2F;
        color: #8FDCFF;
        border: none;
        border-right: 1px solid #22314A;
        border-bottom: 1px solid #2B4568;
        padding: 8px;
        font-weight: 700;
    }
    QTableCornerButton::section {
        background-color: #111D2F;
        border: none;
    }
"""


def configure_forex_table(table: QTableWidget) -> None:
    """Apply the common non-editable table behavior and visual style."""

    table.setStyleSheet(_TABLE_STYLE)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().setDefaultSectionSize(42)
    table.setMinimumHeight(190)


__all__ = ["configure_forex_table"]
