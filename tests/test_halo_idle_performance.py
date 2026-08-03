from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from app.gui.halo_widget import HaloWidget

    HAS_QT = True
except Exception:
    QApplication = None
    HaloWidget = None
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 is unavailable")
class HaloIdlePerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_idle_states_use_a_lighter_frame_rate(self) -> None:
        halo = HaloWidget()
        try:
            self.assertEqual(
                halo._timer.interval(),  # noqa: SLF001 - focused runtime check
                halo.IDLE_FRAME_INTERVAL_MS,
            )

            halo.set_state("thinking")
            self.assertEqual(
                halo._timer.interval(),  # noqa: SLF001 - focused runtime check
                halo.ACTIVE_FRAME_INTERVAL_MS,
            )

            halo.set_state("success")
            self.assertEqual(
                halo._timer.interval(),  # noqa: SLF001 - focused runtime check
                halo.IDLE_FRAME_INTERVAL_MS,
            )
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()


if __name__ == "__main__":
    unittest.main()
