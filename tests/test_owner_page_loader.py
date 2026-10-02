from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from app.gui.owner_page_loader import ensure_owner_page


def test_forex_page_replaces_placeholder_only_when_requested() -> None:
    app = QApplication.instance() or QApplication([])
    placeholder = QWidget()
    replacement = QWidget()
    stack = QStackedWidget()
    stack.addWidget(placeholder)
    trading = SimpleNamespace(forex_dashboard=object(), forex_activity=object())
    window = SimpleNamespace(
        pages={"forex": placeholder},
        stack=stack,
        _loaded_owner_pages=set(),
        assistant=SimpleNamespace(trading=trading),
    )
    with patch(
        "app.gui.forex_paper_page.ForexPaperPage",
        return_value=replacement,
    ) as factory:
        selected = ensure_owner_page(window, "forex")
        repeated = ensure_owner_page(window, "forex")
    assert selected is replacement
    assert repeated is replacement
    assert window.pages["forex"] is replacement
    assert window.forex_page is replacement
    assert "forex" in window._loaded_owner_pages
    factory.assert_called_once_with(
        trading.forex_dashboard, activity=trading.forex_activity
    )
    stack.deleteLater()
