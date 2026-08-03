from __future__ import annotations

import os
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QProgressBar, QWidget
    from app.gui.client_state_presenter import ClientStatePresenter
    from app.gui.halo_widget import HaloWidget
    HAS_QT = True
except Exception:
    QApplication = None
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 is unavailable")
class B1653UiBriefStatePolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _presenter(self):
        parent = QWidget()
        halo = HaloWidget()
        state = QLabel()
        message = QLabel()
        activity = QLabel()
        progress = QProgressBar()
        confirm = QFrame()
        presenter = ClientStatePresenter(
            parent, halo, state, message, activity, progress, confirm
        )
        return parent, presenter, halo, state, message, activity, progress, confirm

    def test_regular_brief_is_not_a_confirmation_state(self) -> None:
        widgets = self._presenter()
        parent, presenter, halo, state, _, activity, progress, confirm = widgets
        presenter.apply_event({
            "state": "brief",
            "message": "Brief dnia: spokojny dzień.",
            "progress": 0,
            "requires_confirmation": False,
        })
        self.assertEqual(presenter.state, "brief")
        self.assertEqual(state.text(), "BRIEF DNIA")
        self.assertEqual(activity.text(), "Najważniejsze informacje na dziś.")
        self.assertFalse(progress.isVisible())
        self.assertFalse(confirm.isVisible())
        self.assertFalse(presenter.busy)
        self.assertEqual(halo.state, "brief")
        parent.deleteLater()

    def test_important_brief_uses_attention_without_decision_language(self) -> None:
        widgets = self._presenter()
        parent, presenter, halo, state, _, activity, progress, confirm = widgets
        presenter.apply_event({
            "state": "important",
            "message": "Masz konflikt w kalendarzu.",
            "progress": 0,
        })
        self.assertEqual(state.text(), "WAŻNE")
        self.assertEqual(activity.text(), "Sprawdź tę ważną informację.")
        self.assertNotIn("decyzj", activity.text().casefold())
        self.assertFalse(progress.isVisible())
        self.assertFalse(confirm.isVisible())
        self.assertFalse(presenter.busy)
        self.assertEqual(halo.state, "important")
        parent.deleteLater()

    def test_proactive_mixin_emits_brief_specific_states(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/gui/client_online_mixin.py").read_text(encoding="utf-8")
        self.assertIn('state = "important" if level in {"high", "critical"} else "brief"', source)
        self.assertIn('"progress": 0', source)
        self.assertIn('"requires_confirmation": False', source)
        self.assertNotIn('state = "warning" if level', source)


if __name__ == "__main__":
    unittest.main()
