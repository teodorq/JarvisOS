from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient


@dataclass(frozen=True, slots=True)
class _EntityParticle:
    x: float
    y: float
    depth: float
    phase: float


class CinematicEntityRenderer:
    """Original particle entity used as the full-screen JARVIS OS presence."""

    def __init__(self) -> None:
        self._particles = self._build_entity()

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
        if min(width, height) < 4:
            return
        color = QColor(color_hex)
        center = QPointF(width * 0.5, height * 0.50)
        scale = min(width * 0.80, height * 0.91)
        pulse = (math.sin(pulse_phase) + 1.0) * 0.5
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Screen)
        self._ambient(painter, center, scale, color, pulse, intensity)
        self._floor(painter, center, scale, color, angle, intensity)
        self._ribbons(painter, center, scale, color, angle, pulse_phase, intensity)
        self._body(painter, center, scale, color, angle, pulse_phase, intensity)
        self._core(painter, center, scale, color, pulse, intensity)
        self._state(painter, center, scale, color, state, scan, progress)
        painter.restore()

    @classmethod
    def _build_entity(cls) -> tuple[_EntityParticle, ...]:
        particles: list[_EntityParticle] = []
        cls._ellipse(particles, 170, 0.0, -0.54, 0.115, 0.135, 1.0)
        cls._torso(particles, 360)
        cls._limb(particles, 125, -0.15, -0.25, -0.30, 0.12, -0.40, 0.31)
        cls._limb(particles, 125, 0.15, -0.25, 0.30, 0.12, 0.40, 0.31)
        cls._limb(particles, 155, -0.08, 0.20, -0.15, 0.55, -0.18, 0.82)
        cls._limb(particles, 155, 0.08, 0.20, 0.15, 0.55, 0.18, 0.82)
        return tuple(particles)

    @staticmethod
    def _noise(index: int, factor: float) -> float:
        return math.sin(index * factor) * 0.5 + math.sin(index * factor * 0.37) * 0.5

    @classmethod
    def _ellipse(
        cls,
        target: list[_EntityParticle],
        count: int,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        depth_scale: float,
    ) -> None:
        golden = math.pi * (3.0 - math.sqrt(5.0))
        for index in range(count):
            radius = math.sqrt((index + 0.5) / count)
            theta = index * golden
            target.append(_EntityParticle(
                cx + math.cos(theta) * rx * radius,
                cy + math.sin(theta) * ry * radius,
                math.sin(theta) * depth_scale,
                (index * 0.173) % math.tau,
            ))

    @classmethod
    def _torso(cls, target: list[_EntityParticle], count: int) -> None:
        golden = math.pi * (3.0 - math.sqrt(5.0))
        for index in range(count):
            unit = (index + 0.5) / count
            y = -0.36 + unit * 0.61
            shoulder = 0.19 - unit * 0.075
            waist = shoulder * (0.78 + 0.22 * abs(math.cos(unit * math.pi)))
            theta = index * golden
            radius = math.sqrt((index * 0.61803398875) % 1.0)
            target.append(_EntityParticle(
                math.cos(theta) * waist * radius,
                y + cls._noise(index, 1.731) * 0.006,
                math.sin(theta),
                (index * 0.113) % math.tau,
            ))

    @classmethod
    def _limb(
        cls,
        target: list[_EntityParticle],
        count: int,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> None:
        for index in range(count):
            t = (index + 0.5) / count
            if t < 0.55:
                local = t / 0.55
                x = x0 + (x1 - x0) * local
                y = y0 + (y1 - y0) * local
            else:
                local = (t - 0.55) / 0.45
                x = x1 + (x2 - x1) * local
                y = y1 + (y2 - y1) * local
            thickness = (1.0 - abs(t - 0.48)) * 0.017
            target.append(_EntityParticle(
                x + cls._noise(index, 2.417) * thickness,
                y + cls._noise(index, 3.191) * thickness,
                math.sin(index * 1.117),
                (index * 0.197) % math.tau,
            ))

    @staticmethod
    def _ambient(
        painter: QPainter,
        center: QPointF,
        scale: float,
        color: QColor,
        pulse: float,
        intensity: float,
    ) -> None:
        glow_center = QPointF(center.x(), center.y() - scale * 0.08)
        radius = scale * (0.46 + pulse * 0.018)
        glow = QRadialGradient(glow_center, radius)
        glow.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), int(125 * intensity)))
        glow.setColorAt(0.35, QColor(16, 109, 166, int(64 * intensity)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(glow_center, radius, radius)

    @staticmethod
    def _floor(
        painter: QPainter,
        center: QPointF,
        scale: float,
        color: QColor,
        angle: float,
        intensity: float,
    ) -> None:
        floor_center = QPointF(center.x(), center.y() + scale * 0.40)
        for index, factor in enumerate((0.20, 0.28, 0.38)):
            pen = QColor(color)
            pen.setAlpha(int((78 - index * 18) * intensity))
            painter.setPen(QPen(pen, 1.0))
            rect = QRectF(
                floor_center.x() - scale * factor,
                floor_center.y() - scale * factor * 0.16,
                scale * factor * 2,
                scale * factor * 0.32,
            )
            painter.drawArc(rect, int((12 + angle * 0.4) * 16), 138 * 16)
            painter.drawArc(rect, int((205 - angle * 0.3) * 16), 94 * 16)

    @staticmethod
    def _ribbons(
        painter: QPainter,
        center: QPointF,
        scale: float,
        color: QColor,
        angle: float,
        phase: float,
        intensity: float,
    ) -> None:
        for ribbon in range(4):
            path = QPainterPath()
            for step in range(90):
                t = step / 89.0
                y = center.y() + scale * (-0.64 + t * 1.25)
                radius = scale * (0.24 - 0.08 * abs(t - 0.50))
                theta = t * math.tau * (1.15 + ribbon * 0.12) + ribbon * 1.31 + angle * 0.012
                x = center.x() + math.sin(theta + phase * 0.22) * radius
                point = QPointF(x, y)
                path.moveTo(point) if step == 0 else path.lineTo(point)
            ink = QColor(color)
            ink.setAlpha(int((27 + ribbon * 7) * intensity))
            painter.setPen(QPen(ink, 0.8 + ribbon * 0.22, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

    def _body(
        self,
        painter: QPainter,
        center: QPointF,
        scale: float,
        color: QColor,
        angle: float,
        phase: float,
        intensity: float,
    ) -> None:
        sway = math.sin(phase * 0.45) * scale * 0.008
        groups: list[list[QPointF]] = [[], [], [], []]
        for particle in self._particles:
            shimmer = (math.sin(phase * 1.4 + particle.phase) + 1.0) * 0.5
            depth = (particle.depth + 1.0) * 0.5
            x = center.x() + particle.x * scale + sway * (0.4 + particle.y)
            x += math.sin(particle.phase + angle * 0.018) * scale * 0.003
            y = center.y() + particle.y * scale
            band = min(3, int((depth * 0.68 + shimmer * 0.32) * 4))
            groups[band].append(QPointF(x, y))
        for points, alpha, width in zip(groups, (68, 112, 184, 255), (1.05, 1.45, 2.0, 2.75), strict=True):
            ink = QColor(color)
            ink.setAlpha(int(alpha * intensity))
            painter.setPen(QPen(ink, width, Qt.SolidLine, Qt.RoundCap))
            painter.drawPoints(QPolygonF(points))

    @staticmethod
    def _core(
        painter: QPainter,
        center: QPointF,
        scale: float,
        color: QColor,
        pulse: float,
        intensity: float,
    ) -> None:
        chest = QPointF(center.x(), center.y() - scale * 0.14)
        radius = scale * (0.045 + pulse * 0.007)
        core = QRadialGradient(chest, radius)
        core.setColorAt(0.0, QColor(255, 255, 255, 250))
        core.setColorAt(0.25, QColor(160, 241, 255, 235))
        core.setColorAt(0.62, QColor(color.red(), color.green(), color.blue(), int(165 * intensity)))
        core.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(core)
        painter.drawEllipse(chest, radius, radius)

    @staticmethod
    def _state(
        painter: QPainter,
        center: QPointF,
        scale: float,
        color: QColor,
        state: str,
        scan: float,
        progress: int,
    ) -> None:
        if state not in {"thinking", "acting", "listening", "warning"}:
            return
        ink = QColor(color)
        ink.setAlpha(175)
        painter.setPen(QPen(ink, 1.2, Qt.SolidLine, Qt.RoundCap))
        value = progress if progress > 0 else int(scan % 100)
        radius = scale * 0.33
        rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        painter.drawArc(rect, 88 * 16, -max(24, int(value * 2.7)) * 16)


__all__ = ["CinematicEntityRenderer"]
