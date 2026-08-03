from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class ClientHudBackdrop(QWidget):
    """Subtle HUD grid and central light field for the client experience."""

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#02060D"))

        center = QPointF(self.width() / 2.0, self.height() * 0.43)
        glow = QRadialGradient(center, max(self.width(), self.height()) * 0.62)
        glow.setColorAt(0.0, QColor(9, 73, 114, 105))
        glow.setColorAt(0.32, QColor(5, 38, 68, 68))
        glow.setColorAt(1.0, QColor(2, 6, 13, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawRect(self.rect())

        spacing = 42
        for x in range(0, self.width() + spacing, spacing):
            major = (x // spacing) % 4 == 0
            painter.setPen(QPen(QColor(49, 173, 224, 28 if major else 13), 1))
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height() + spacing, spacing):
            major = (y // spacing) % 4 == 0
            painter.setPen(QPen(QColor(49, 173, 224, 25 if major else 11), 1))
            painter.drawLine(0, y, self.width(), y)

        hud = QPen(QColor(63, 190, 235, 30), 1.0)
        painter.setPen(hud)
        painter.drawLine(0, int(center.y()), self.width(), int(center.y()))
        for diameter in (360, 470, 610):
            radius = diameter / 2.0
            ring = QRectF(
                center.x() - radius,
                center.y() - radius,
                diameter,
                diameter,
            )
            painter.drawArc(ring, 18 * 16, 52 * 16)
            painter.drawArc(ring, 198 * 16, 52 * 16)

        accent = QPen(QColor(66, 207, 255, 105), 1.4)
        painter.setPen(accent)
        edge = 34
        length = 84
        painter.drawLine(edge, edge, edge + length, edge)
        painter.drawLine(edge, edge, edge, edge + length)
        painter.drawLine(self.width() - edge, edge, self.width() - edge - length, edge)
        painter.drawLine(self.width() - edge, edge, self.width() - edge, edge + length)
