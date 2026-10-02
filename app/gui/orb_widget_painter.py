from __future__ import annotations

from time import perf_counter

from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from app.gui.cinematic_orb_renderer import CinematicOrbRenderer
from app.gui.orb_frame_budget import OrbFrameBudget


def paint_orb_frame(
    widget: QWidget,
    *,
    renderer: CinematicOrbRenderer,
    frame_budget: OrbFrameBudget,
    state: str,
    color_hex: str,
    angle: float,
    pulse_phase: float,
    scan: float,
    progress: int,
    intensity: float,
    active: bool,
) -> None:
    """Paint and measure one orb frame without leaking QPainter state."""
    render_started = perf_counter()
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing, True)
    try:
        renderer.paint(
            painter=painter,
            width=widget.width(),
            height=widget.height(),
            state=state,
            color_hex=color_hex,
            angle=angle,
            pulse_phase=pulse_phase,
            scan=scan,
            progress=progress,
            intensity=intensity,
            particle_stride_multiplier=frame_budget.stride_multiplier,
        )
    finally:
        painter.end()
    frame_budget.observe(
        (perf_counter() - render_started) * 1000.0,
        active=active,
    )
