from __future__ import annotations

from PySide6.QtGui import QPainter

from app.gui.cinematic_entity_renderer import CinematicEntityRenderer
from app.gui.halo_widget import HaloWidget


class CinematicEntityWidget(HaloWidget):
    """State-compatible main-screen entity; compact mode keeps the old orb."""

    def __init__(self) -> None:
        super().__init__()
        self._entity_renderer = CinematicEntityRenderer()
        self.setAccessibleName("Postać energetyczna JARVIS OS")

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self._entity_renderer.paint(
            painter=painter,
            width=self.width(),
            height=self.height(),
            state=self._state,
            color_hex=self.COLORS[self._state],
            angle=self._angle,
            pulse_phase=self._pulse,
            scan=self._scan,
            progress=self._progress,
            intensity=self._intensity,
        )


__all__ = ["CinematicEntityWidget"]
