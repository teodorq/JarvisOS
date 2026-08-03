from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)


class HaloRenderer:
    """Side-effect-free painter for the client JARVIS orb."""

    def paint(
        self,
        *,
        painter: QPainter,
        width: int,
        height: int,
        state: str,
        color_hex: str,
        angle: float,
        pulse_phase: float,
        scan: float,
        progress: int,
        intensity: float,
    ) -> None:
        size = float(min(width, height))
        center = QPointF(width / 2.0, height / 2.0)
        pulse = (math.sin(pulse_phase) + 1.0) / 2.0
        color = QColor(color_hex)
        self._draw_glow(painter, center, size, color, pulse, intensity)
        self._draw_rings(painter, center, size, color, pulse, angle, intensity)
        self._draw_progress_ring(
            painter, center, size, color, state, progress, scan
        )
        self._draw_core(painter, center, size, color, pulse)
        self._draw_particles(
            painter, center, size, color, state, angle, pulse_phase
        )
        self._draw_state_accent(
            painter, center, size, color, state, pulse, pulse_phase, scan
        )

    @staticmethod
    def _draw_glow(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        pulse: float,
        intensity: float,
    ) -> None:
        radius = size * (0.47 + 0.015 * pulse)
        glow = QRadialGradient(center, radius)
        alpha = int(70 * intensity)
        glow.setColorAt(
            0.0,
            QColor(color.red(), color.green(), color.blue(), alpha),
        )
        glow.setColorAt(
            0.43,
            QColor(color.red(), color.green(), color.blue(), alpha // 3),
        )
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, radius, radius)

    @staticmethod
    def _draw_rings(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        pulse: float,
        angle: float,
        intensity: float,
    ) -> None:
        base_radius = size * (0.27 + pulse * 0.012)
        widths = (5.6, 3.0, 1.5, 0.9)
        spans = (212, 126, 92, 48)
        for index, width in enumerate(widths):
            radius = base_radius + index * size * 0.052
            rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2.0,
                radius * 2.0,
            )
            ring = QColor(color)
            ring.setAlpha(max(48, int((235 - index * 47) * intensity)))
            painter.setPen(QPen(ring, width, Qt.SolidLine, Qt.RoundCap))
            direction = 1.0 if index % 2 == 0 else -0.72
            offset = angle * direction
            painter.drawArc(
                rect,
                int((24 + offset + index * 61) * 16),
                int(spans[index] * 16),
            )
            painter.drawArc(
                rect,
                int((214 + offset + index * 37) * 16),
                int((62 + index * 6) * 16),
            )

    @staticmethod
    def _draw_progress_ring(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        state: str,
        progress: int,
        scan: float,
    ) -> None:
        if state not in {"thinking", "acting", "warning"}:
            return
        radius = size * 0.415
        rect = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2.0,
            radius * 2.0,
        )
        track = QColor(color)
        track.setAlpha(32)
        painter.setPen(QPen(track, 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, -360 * 16)
        value = progress if progress > 0 else int(scan % 100)
        active = QColor(color)
        active.setAlpha(205)
        painter.setPen(QPen(active, 2.7, Qt.SolidLine, Qt.RoundCap))
        span = max(20, int(360 * value / 100.0))
        painter.drawArc(rect, 90 * 16, -span * 16)

    @staticmethod
    def _draw_core(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        pulse: float,
    ) -> None:
        core_radius = size * (0.108 + pulse * 0.008)
        core = QRadialGradient(center, core_radius)
        core.setColorAt(0.0, QColor(250, 253, 255, 250))
        core.setColorAt(
            0.2,
            QColor(color.red(), color.green(), color.blue(), 238),
        )
        core.setColorAt(
            0.68,
            QColor(color.red(), color.green(), color.blue(), 112),
        )
        core.setColorAt(
            1.0,
            QColor(color.red(), color.green(), color.blue(), 10),
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(core)
        painter.drawEllipse(center, core_radius, core_radius)

    @staticmethod
    def _draw_particles(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        state: str,
        angle_value: float,
        pulse_phase: float,
    ) -> None:
        particle = QColor(color)
        particle.setAlpha(180)
        painter.setPen(QPen(particle, 2.6, Qt.SolidLine, Qt.RoundCap))
        count = 12 if state in {"listening", "thinking", "acting"} else 8
        for index in range(count):
            angle = math.radians(
                angle_value * (1.45 if index % 2 else -0.82)
                + index * 360 / count
            )
            radius = size * (
                0.35 + 0.018 * math.sin(pulse_phase + index * 0.7)
            )
            point = QPointF(
                center.x() + math.cos(angle) * radius,
                center.y() + math.sin(angle) * radius,
            )
            painter.drawPoint(point)

    def _draw_state_accent(
        self,
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        state: str,
        pulse: float,
        pulse_phase: float,
        scan: float,
    ) -> None:
        if state == "listening":
            self._draw_listening_wave(
                painter, center, size, color, pulse, pulse_phase
            )
        elif state == "success":
            self._draw_success_mark(painter, center, size, color)
        elif state == "warning":
            self._draw_warning_mark(painter, center, size, color, pulse)
        elif state == "error":
            self._draw_error_mark(painter, center, size, color)
        elif state == "acting":
            self._draw_scanner(painter, center, size, color, scan)

    @staticmethod
    def _draw_listening_wave(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        pulse: float,
        pulse_phase: float,
    ) -> None:
        wave = QColor(color)
        wave.setAlpha(215)
        painter.setPen(QPen(wave, 3.0, Qt.SolidLine, Qt.RoundCap))
        spacing = size * 0.032
        for index in range(-3, 4):
            height = size * (
                0.025
                + 0.045
                * abs(math.sin(pulse_phase * 1.7 + index * 0.75))
                * (0.7 + 0.3 * pulse)
            )
            x = center.x() + index * spacing
            painter.drawLine(
                QPointF(x, center.y() - height),
                QPointF(x, center.y() + height),
            )

    @staticmethod
    def _draw_success_mark(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
    ) -> None:
        mark = QColor(color)
        mark.setAlpha(235)
        painter.setPen(
            QPen(mark, 4.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        )
        path = QPainterPath()
        path.moveTo(center.x() - size * 0.035, center.y())
        path.lineTo(center.x() - size * 0.008, center.y() + size * 0.027)
        path.lineTo(center.x() + size * 0.047, center.y() - size * 0.04)
        painter.drawPath(path)

    @staticmethod
    def _draw_warning_mark(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        pulse: float,
    ) -> None:
        mark = QColor(color)
        mark.setAlpha(int(170 + 70 * pulse))
        painter.setPen(QPen(mark, 4.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(
            QPointF(center.x(), center.y() - size * 0.036),
            QPointF(center.x(), center.y() + size * 0.014),
        )
        painter.drawPoint(QPointF(center.x(), center.y() + size * 0.043))

    @staticmethod
    def _draw_error_mark(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
    ) -> None:
        mark = QColor(color)
        mark.setAlpha(230)
        painter.setPen(QPen(mark, 4.0, Qt.SolidLine, Qt.RoundCap))
        radius = size * 0.035
        painter.drawLine(
            QPointF(center.x() - radius, center.y() - radius),
            QPointF(center.x() + radius, center.y() + radius),
        )
        painter.drawLine(
            QPointF(center.x() + radius, center.y() - radius),
            QPointF(center.x() - radius, center.y() + radius),
        )

    @staticmethod
    def _draw_scanner(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        scan: float,
    ) -> None:
        angle = math.radians(scan)
        length = size * 0.24
        end = QPointF(
            center.x() + math.cos(angle) * length,
            center.y() + math.sin(angle) * length,
        )
        scanner = QColor(color)
        scanner.setAlpha(115)
        painter.setPen(QPen(scanner, 1.6, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(center, end)
