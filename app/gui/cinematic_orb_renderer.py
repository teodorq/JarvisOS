from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)


@dataclass(frozen=True, slots=True)
class _Particle:
    x: float
    y: float
    z: float
    shimmer: float


class CinematicOrbRenderer:
    """Gęsta, przestrzenna kula cząsteczkowa inspirowana filmowym JARVISEM."""

    PARTICLE_COUNT = 1800

    def __init__(self) -> None:
        self._particles = self._build_particles(self.PARTICLE_COUNT)

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
        if size <= 2:
            return
        center = QPointF(width / 2.0, height / 2.0)
        pulse = (math.sin(pulse_phase) + 1.0) / 2.0
        color = QColor(color_hex)

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Screen)
        self._draw_ambient_glow(
            painter, center, size, color, pulse, intensity
        )
        self._draw_corona_wisps(
            painter, center, size, color, angle, pulse_phase, intensity
        )
        self._draw_orbits(painter, center, size, color, angle, intensity)
        self._draw_sphere_body(
            painter, center, size, color, pulse, intensity
        )
        self._draw_particle_sphere(
            painter,
            center,
            size,
            color,
            state,
            angle,
            pulse_phase,
            intensity,
        )
        self._draw_energy_filaments(
            painter, center, size, color, angle, pulse_phase, intensity
        )
        self._draw_shell_refraction(
            painter, center, size, color, angle, pulse, intensity
        )
        self._draw_progress_ring(
            painter, center, size, color, state, progress, scan
        )
        self._draw_core(painter, center, size, color, pulse, intensity)
        self._draw_state_accent(
            painter, center, size, color, state, pulse, pulse_phase, scan
        )
        painter.restore()

    @staticmethod
    def _build_particles(count: int) -> tuple[_Particle, ...]:
        golden_angle = math.pi * (3.0 - math.sqrt(5.0))
        particles: list[_Particle] = []
        for index in range(count):
            y = 1.0 - 2.0 * (index + 0.5) / count
            radius = math.sqrt(max(0.0, 1.0 - y * y))
            theta = index * golden_angle
            jitter = 1.0 + 0.026 * math.sin(index * 12.9898)
            distribution = (math.sin(index * 4.731) + 1.0) / 2.0
            if index % 5 in {0, 1, 2}:
                shell = 0.92 + distribution * 0.075
            else:
                shell = 0.38 + (distribution ** 0.42) * 0.58
            scale = shell * jitter
            particles.append(
                _Particle(
                    x=math.cos(theta) * radius * scale,
                    y=y * scale,
                    z=math.sin(theta) * radius * scale,
                    shimmer=(math.sin(index * 7.417) + 1.0) / 2.0,
                )
            )
        return tuple(particles)

    @staticmethod
    def _draw_ambient_glow(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        pulse: float,
        intensity: float,
    ) -> None:
        radius = size * (0.48 + pulse * 0.015)
        glow = QRadialGradient(center, radius)
        alpha = int(100 * intensity)
        glow.setColorAt(0.0, QColor(225, 250, 255, min(190, alpha + 60)))
        glow.setColorAt(
            0.12,
            QColor(color.red(), color.green(), color.blue(), alpha),
        )
        glow.setColorAt(
            0.48,
            QColor(color.red(), color.green(), color.blue(), alpha // 3),
        )
        glow.setColorAt(
            0.78,
            QColor(color.red(), color.green(), color.blue(), alpha // 9),
        )
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, radius, radius)

    @staticmethod
    def _draw_corona_wisps(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        angle: float,
        pulse_phase: float,
        intensity: float,
    ) -> None:
        """Draw continuously flowing energy without a loop boundary."""
        phase = math.radians(angle * 0.14) + pulse_phase * 0.11
        painter.setBrush(Qt.NoBrush)
        for arm in range(7):
            path = QPainterPath()
            arm_phase = phase + arm * math.tau / 7.0
            for step in range(42):
                travel = step / 41.0
                theta = arm_phase + travel * (1.15 + 0.08 * arm)
                wave = math.sin(travel * math.tau * 1.5 + arm_phase)
                radius = size * (0.305 + travel * 0.155 + wave * 0.008)
                squash = 0.72 + 0.08 * math.sin(arm_phase * 0.7)
                point = QPointF(
                    center.x() + math.cos(theta) * radius,
                    center.y() + math.sin(theta) * radius * squash,
                )
                if step == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            wisp = QColor(color)
            wisp.setAlpha(int((18 + (arm % 3) * 9) * intensity))
            painter.setPen(
                QPen(
                    wisp,
                    max(0.55, min(1.35, size / (760.0 - arm * 28.0))),
                    Qt.SolidLine,
                    Qt.RoundCap,
                )
            )
            painter.drawPath(path)

    @staticmethod
    def _draw_orbits(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        angle: float,
        intensity: float,
    ) -> None:
        radii = (0.385, 0.435, 0.475)
        spans = (118, 72, 42)
        for index, factor in enumerate(radii):
            radius = size * factor
            rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2.0,
                radius * 2.0,
            )
            orbit = QColor(color)
            orbit.setAlpha(int((92 - index * 22) * intensity))
            width = max(0.7, min(1.8, size / (490.0 + index * 150.0)))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(orbit, width, Qt.SolidLine, Qt.RoundCap))
            direction = 0.52 if index % 2 == 0 else -0.31
            offset = angle * direction
            painter.drawArc(
                rect,
                int((24 + index * 87 + offset) * 16),
                int(spans[index] * 16),
            )
            painter.drawArc(
                rect,
                int((205 + index * 39 + offset) * 16),
                int((spans[index] * 0.52) * 16),
            )

        tick = QColor(color)
        tick.setAlpha(int(145 * intensity))
        painter.setPen(QPen(tick, max(1.0, size / 520.0), Qt.SolidLine))
        for index in range(18):
            theta = math.radians(index * 20.0 + angle * 0.22)
            if index % 3:
                continue
            inner = size * 0.452
            outer = size * (0.462 if index % 2 else 0.472)
            painter.drawLine(
                QPointF(
                    center.x() + math.cos(theta) * inner,
                    center.y() + math.sin(theta) * inner,
                ),
                QPointF(
                    center.x() + math.cos(theta) * outer,
                    center.y() + math.sin(theta) * outer,
                ),
            )

    @staticmethod
    def _draw_sphere_body(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        pulse: float,
        intensity: float,
    ) -> None:
        radius = size * (0.326 + 0.006 * pulse)
        sphere = QRadialGradient(
            QPointF(center.x() - radius * 0.18, center.y() - radius * 0.22),
            radius * 1.18,
        )
        sphere.setColorAt(0.0, QColor(135, 234, 255, int(74 * intensity)))
        sphere.setColorAt(
            0.3,
            QColor(color.red(), color.green(), color.blue(), int(52 * intensity)),
        )
        sphere.setColorAt(0.72, QColor(2, 24, 52, int(92 * intensity)))
        sphere.setColorAt(1.0, QColor(0, 4, 13, 8))
        painter.setPen(Qt.NoPen)
        painter.setBrush(sphere)
        painter.drawEllipse(center, radius, radius)

    def _draw_particle_sphere(
        self,
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        state: str,
        angle: float,
        pulse_phase: float,
        intensity: float,
    ) -> None:
        radius = size * (0.322 + 0.006 * math.sin(pulse_phase))
        yaw = math.radians(angle * 0.31)
        pitch = math.radians(-8.0 + math.sin(pulse_phase * 0.42) * 3.2)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        stride = 3 if size < 220 else (2 if size < 390 else 1)
        if state in {"idle", "brief", "success"}:
            stride = max(stride, 2)
        batches: list[list[QPointF]] = [[], [], [], []]
        corona: list[QPointF] = []
        energy = 1.12 if state in {"listening", "thinking", "acting"} else 1.0
        flow_phase = math.radians(angle * 0.045) + pulse_phase * 0.19

        for index in range(0, len(self._particles), stride):
            particle = self._particles[index]
            organic = 0.018 * math.sin(
                flow_phase
                + particle.shimmer * math.tau
                + particle.y * 3.6
                + particle.z * 1.8
            )
            lateral = 0.012 * math.sin(
                flow_phase * 0.73 + particle.shimmer * 9.0 + particle.x * 2.4
            )
            radial = 1.0 + organic
            px = particle.x * radial + lateral * particle.z
            py = particle.y * (1.0 + organic * 0.58)
            pz = particle.z * radial - lateral * particle.x
            x1 = px * cy + pz * sy
            z1 = -px * sy + pz * cy
            y2 = py * cp - z1 * sp
            z2 = py * sp + z1 * cp
            perspective = 0.91 + z2 * 0.085
            point = QPointF(
                center.x() + x1 * radius * perspective,
                center.y() + y2 * radius * perspective,
            )
            twinkle = 0.13 * math.sin(
                pulse_phase * 1.35 + particle.shimmer * math.tau
            )
            tone = max(0.0, min(0.999, (z2 + 1.0) * 0.5 + twinkle))
            batches[min(3, int(tone * 4.0))].append(point)
            if index % 29 == 0 and z2 > -0.4:
                halo_scale = 1.12 + 0.075 * math.sin(
                    flow_phase * 0.61 + particle.shimmer * math.tau
                )
                corona.append(
                    QPointF(
                        center.x() + x1 * radius * perspective * halo_scale,
                        center.y() + y2 * radius * perspective * halo_scale,
                    )
                )

        base_width = max(0.65, min(1.45, size / 530.0))
        alpha_values = (42, 76, 132, 224)
        width_values = (0.72, 0.95, 1.28, 1.85)
        for points, alpha, width_factor in zip(
            batches, alpha_values, width_values, strict=True
        ):
            if not points:
                continue
            particle_color = QColor(color)
            particle_color.setAlpha(
                min(255, int(alpha * intensity * energy))
            )
            painter.setPen(
                QPen(
                    particle_color,
                    base_width * width_factor,
                    Qt.SolidLine,
                    Qt.RoundCap,
                )
            )
            painter.drawPoints(QPolygonF(points))
        if corona:
            spark = QColor(190, 242, 255, int(118 * intensity))
            painter.setPen(
                QPen(spark, max(0.7, size / 520.0), Qt.SolidLine, Qt.RoundCap)
            )
            painter.drawPoints(QPolygonF(corona))

    def _draw_energy_filaments(
        self,
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        angle: float,
        pulse_phase: float,
        intensity: float,
    ) -> None:
        radius = size * 0.324
        yaw = math.radians(angle * 0.31)
        pitch = math.radians(-8.0 + math.sin(pulse_phase * 0.42) * 3.2)
        for band in range(5):
            path = QPainterPath()
            first = True
            for step in range(73):
                longitude = math.tau * step / 72.0
                latitude = (
                    (band - 2) * 0.19
                    + 0.05
                    * math.sin(
                        longitude * (2.0 + (band % 2))
                        + pulse_phase * (0.43 + band * 0.04)
                        + band
                    )
                )
                x = math.cos(latitude) * math.cos(longitude)
                y = math.sin(latitude)
                z = math.cos(latitude) * math.sin(longitude)
                point, depth = self._project(
                    center, radius, x, y, z, yaw, pitch
                )
                if depth < -0.15:
                    first = True
                    continue
                if first:
                    path.moveTo(point)
                    first = False
                else:
                    path.lineTo(point)
            filament = QColor(color)
            filament.setAlpha(int((32 + band * 7) * intensity))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(
                QPen(
                    filament,
                    max(0.6, min(1.6, size / 590.0)),
                    Qt.SolidLine,
                    Qt.RoundCap,
                )
            )
            painter.drawPath(path)

    @staticmethod
    def _draw_shell_refraction(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        angle: float,
        pulse: float,
        intensity: float,
    ) -> None:
        painter.setBrush(Qt.NoBrush)
        for layer in range(3):
            radius = size * (0.334 + layer * 0.009 + pulse * 0.0015)
            rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2.0,
                radius * 2.0,
            )
            rim = QColor(color).lighter(145)
            rim.setAlpha(int((52 - layer * 12) * intensity))
            painter.setPen(
                QPen(
                    rim,
                    max(0.65, size / (720.0 + layer * 180.0)),
                    Qt.SolidLine,
                    Qt.RoundCap,
                )
            )
            start = 198.0 + layer * 77.0 + angle * (0.12 - layer * 0.025)
            painter.drawArc(rect, int(start * 16), int((44 - layer * 7) * 16))
            painter.drawArc(
                rect, int((start + 164.0) * 16), int((24 + layer * 4) * 16)
            )

    @staticmethod
    def _project(
        center: QPointF,
        radius: float,
        x: float,
        y: float,
        z: float,
        yaw: float,
        pitch: float,
    ) -> tuple[QPointF, float]:
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        x1 = x * cy + z * sy
        z1 = -x * sy + z * cy
        y2 = y * cp - z1 * sp
        z2 = y * sp + z1 * cp
        perspective = 0.91 + z2 * 0.085
        return (
            QPointF(
                center.x() + x1 * radius * perspective,
                center.y() + y2 * radius * perspective,
            ),
            z2,
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
        radius = size * 0.405
        rect = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2.0,
            radius * 2.0,
        )
        track = QColor(color)
        track.setAlpha(28)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(track, max(1.0, size / 520.0)))
        painter.drawArc(rect, 90 * 16, -360 * 16)
        active = QColor(color)
        active.setAlpha(205)
        painter.setPen(
            QPen(active, max(1.5, size / 330.0), Qt.SolidLine, Qt.RoundCap)
        )
        if progress > 0:
            start, span = 90.0, max(18, int(360 * progress / 100.0))
        else:
            start, span = 90.0 - scan, 82
        painter.drawArc(rect, int(start * 16), -span * 16)

    @staticmethod
    def _draw_core(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        pulse: float,
        intensity: float,
    ) -> None:
        radius = size * (0.068 + 0.006 * pulse)
        core = QRadialGradient(center, radius)
        core.setColorAt(0.0, QColor(255, 255, 255, 252))
        core.setColorAt(0.16, QColor(206, 248, 255, 245))
        core.setColorAt(
            0.45,
            QColor(color.red(), color.green(), color.blue(), int(218 * intensity)),
        )
        core.setColorAt(
            0.82,
            QColor(color.red(), color.green(), color.blue(), int(62 * intensity)),
        )
        core.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(core)
        painter.drawEllipse(center, radius, radius)
        halo_radius = radius * (1.55 + pulse * 0.08)
        core_halo = QRadialGradient(center, halo_radius)
        core_halo.setColorAt(0.0, QColor(255, 255, 255, 88))
        core_halo.setColorAt(
            0.42,
            QColor(color.red(), color.green(), color.blue(), int(72 * intensity)),
        )
        core_halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(core_halo)
        painter.drawEllipse(center, halo_radius, halo_radius)
        hot = QColor(235, 253, 255, int(205 * intensity))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(hot, max(0.7, size / 610.0)))
        ring_radius = radius * (0.67 + pulse * 0.04)
        painter.drawEllipse(center, ring_radius, ring_radius)

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
        wave.setAlpha(230)
        painter.setPen(
            QPen(wave, max(1.8, size / 190.0), Qt.SolidLine, Qt.RoundCap)
        )
        spacing = size * 0.026
        for index in range(-3, 4):
            height = size * (
                0.016
                + 0.032
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
        mark.setAlpha(245)
        painter.setPen(
            QPen(
                mark,
                max(2.5, size / 125.0),
                Qt.SolidLine,
                Qt.RoundCap,
                Qt.RoundJoin,
            )
        )
        path = QPainterPath()
        path.moveTo(center.x() - size * 0.029, center.y())
        path.lineTo(center.x() - size * 0.006, center.y() + size * 0.022)
        path.lineTo(center.x() + size * 0.041, center.y() - size * 0.034)
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
        mark.setAlpha(int(180 + 70 * pulse))
        painter.setPen(
            QPen(mark, max(2.5, size / 135.0), Qt.SolidLine, Qt.RoundCap)
        )
        painter.drawLine(
            QPointF(center.x(), center.y() - size * 0.034),
            QPointF(center.x(), center.y() + size * 0.012),
        )
        painter.drawPoint(QPointF(center.x(), center.y() + size * 0.039))

    @staticmethod
    def _draw_error_mark(
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
    ) -> None:
        mark = QColor(color)
        mark.setAlpha(240)
        painter.setPen(
            QPen(mark, max(2.5, size / 135.0), Qt.SolidLine, Qt.RoundCap)
        )
        radius = size * 0.031
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
        theta = math.radians(scan)
        length = size * 0.29
        end = QPointF(
            center.x() + math.cos(theta) * length,
            center.y() + math.sin(theta) * length,
        )
        scanner = QColor(color)
        scanner.setAlpha(86)
        painter.setPen(
            QPen(scanner, max(0.8, size / 520.0), Qt.SolidLine, Qt.RoundCap)
        )
        painter.drawLine(center, end)


__all__ = ["CinematicOrbRenderer"]
