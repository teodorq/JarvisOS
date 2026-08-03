from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QLineEdit

from app.core.user_text import naturalize_user_text


def clean_user_visible_widgets(root: Any) -> None:
    """Remove internal milestone codes from already constructed widgets."""
    for widget in root.findChildren(QLabel):
        cleaned = naturalize_user_text(widget.text())
        if cleaned and cleaned != widget.text():
            widget.setText(cleaned)
    for widget in root.findChildren(QAbstractButton):
        cleaned = naturalize_user_text(widget.text())
        if cleaned and cleaned != widget.text():
            widget.setText(cleaned)
    for widget in root.findChildren(QGroupBox):
        cleaned = naturalize_user_text(widget.title())
        if cleaned and cleaned != widget.title():
            widget.setTitle(cleaned)
    for widget in root.findChildren(QLineEdit):
        placeholder = widget.placeholderText()
        cleaned = naturalize_user_text(placeholder)
        if cleaned and cleaned != placeholder:
            widget.setPlaceholderText(cleaned)


__all__ = ["clean_user_visible_widgets", "naturalize_user_text"]
