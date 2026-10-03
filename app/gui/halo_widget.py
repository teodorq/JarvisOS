from __future__ import annotations
from time import perf_counter

from PySide6.QtCore import QSize, QTimer
from PySide6.QtWidgets import QWidget

from app.core.performance_profile import PerformanceProfile, load_performance_profile
from app.gui.cinematic_orb_renderer import CinematicOrbRenderer
from app.gui.orb_frame_budget import OrbFrameBudget
from app.gui.orb_widget_painter import paint_orb_frame
from app.gui.halo_visual_profile import ACCESSIBLE, COLORS, INTENSITY, SPEEDS

class HaloWidget(QWidget):
    """Filmowa kula cząsteczkowa JARVISA z czytelnymi stanami pracy."""

    COLORS = COLORS
    SPEEDS = SPEEDS
    ACCESSIBLE = ACCESSIBLE
    INTENSITY = INTENSITY
    ACTIVE_FRAME_INTERVAL_MS = 33
    IDLE_FRAME_INTERVAL_MS = 50
    IDLE_STATES = frozenset({"idle", "brief", "success"})
    ACTIVE_ADAPTIVE_STEP_MS = 10
    IDLE_ADAPTIVE_STEP_MS = 15
    MAX_FRAME_INTERVAL_MS = 100
    MAX_MOTION_FRAME_MULTIPLIER = 2.5

    def __init__(self, performance_profile: PerformanceProfile | None = None) -> None:
        super().__init__()
        self.performance_profile = performance_profile or load_performance_profile()
        self.setMinimumSize(400, 400)
        self.setMaximumSize(860, 860)
        self._state = "idle"
        self._angle = 0.0
        self._pulse = 0.0
        self._scan = 0.0
        self._progress = 0
        self._intensity = self.INTENSITY["idle"]
        self._target_intensity = self._intensity
        self._renderer = CinematicOrbRenderer()
        self._frame_budget = OrbFrameBudget(initial_stride_multiplier=self.performance_profile.orb_stride_multiplier)
        self._baseline_stride_multiplier = self._frame_budget.stride_multiplier
        self._last_tick_at = perf_counter()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._frame_interval_ms())
        self.setAccessibleName("Rdzeń JARVIS")
        self.setAccessibleDescription(self.ACCESSIBLE["idle"])

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(640, 640)

    @property
    def state(self) -> str:
        return self._state

    @property
    def progress(self) -> int:
        return self._progress

    @property
    def animation_running(self) -> bool:
        return self._timer.isActive()

    @property
    def particle_stride_multiplier(self) -> int:
        return self._frame_budget.stride_multiplier

    def set_animation_active(self, active: bool) -> None:
        """Pause work for a hidden orb and resume without rebuilding it."""
        if active:
            if not self._timer.isActive():
                self._last_tick_at = perf_counter()
                self._timer.start(self._frame_interval_ms())
            self.update()
            return
        self._timer.stop()

    def set_state(self, state: object, progress: object | None = None) -> None:
        value = str(state or "idle").lower()
        self._state = value if value in self.COLORS else "idle"
        if progress is not None:
            self.set_progress(progress)
        self._target_intensity = self.INTENSITY[self._state]
        self.setAccessibleDescription(self.ACCESSIBLE[self._state])
        if self._timer.isActive():
            self._timer.setInterval(self._frame_interval_ms())
        self.update()

    def set_progress(self, progress: object) -> None:
        try:
            self._progress = max(0, min(100, int(progress)))
        except (TypeError, ValueError):
            self._progress = 0
        self.update()

    def _frame_interval_ms(self) -> int:
        base = self._base_frame_interval_ms()
        extra_detail_reduction = max(
            0,
            self._frame_budget.stride_multiplier
            - self._baseline_stride_multiplier,
        )
        step = (
            self.IDLE_ADAPTIVE_STEP_MS
            if self._state in self.IDLE_STATES
            else self.ACTIVE_ADAPTIVE_STEP_MS
        )
        return min(
            self.MAX_FRAME_INTERVAL_MS,
            base + extra_detail_reduction * step,
        )

    def _base_frame_interval_ms(self) -> int:
        if self._state in self.IDLE_STATES:
            return self.performance_profile.idle_frame_interval_ms
        return self.performance_profile.active_frame_interval_ms

    def _tick(self) -> None:
        now = perf_counter()
        elapsed_ms = max(0.0, (now - self._last_tick_at) * 1000.0)
        self._last_tick_at = now
        nominal_ms = float(self._base_frame_interval_ms())
        if elapsed_ms < nominal_ms * 0.5:
            elapsed_ms = float(self._timer.interval() or nominal_ms)
        motion_scale = min(
            self.MAX_MOTION_FRAME_MULTIPLIER,
            elapsed_ms / nominal_ms,
        )
        speed = self.SPEEDS[self._state]
        self._angle += speed * motion_scale
        self._pulse += 0.038 * max(speed, 0.65) * motion_scale
        self._scan += 1.8 * max(speed, 0.65) * motion_scale
        self._intensity += (
            self._target_intensity - self._intensity
        ) * 0.08
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        paint_orb_frame(
            self,
            renderer=self._renderer,
            frame_budget=self._frame_budget,
            state=self._state,
            color_hex=self.COLORS[self._state],
            angle=self._angle,
            pulse_phase=self._pulse,
            scan=self._scan,
            progress=self._progress,
            intensity=self._intensity,
            active=self._state not in self.IDLE_STATES,
        )
        if self._timer.isActive():
            interval = self._frame_interval_ms()
            if self._timer.interval() != interval:
                self._timer.setInterval(interval)
