from __future__ import annotations
from PySide6.QtCore import QSize, QTimer
from PySide6.QtWidgets import QWidget

from app.core.performance_profile import PerformanceProfile, load_performance_profile
from app.gui.cinematic_orb_renderer import CinematicOrbRenderer
from app.gui.orb_frame_budget import OrbFrameBudget
from app.gui.orb_widget_painter import paint_orb_frame

class HaloWidget(QWidget):
    """Filmowa kula cząsteczkowa JARVISA z czytelnymi stanami pracy."""

    COLORS = {
        "idle": "#43B9FF",
        "listening": "#4DEBFF",
        "thinking": "#669DFF",
        "acting": "#53CCFF",
        "speaking": "#B47CFF",
        "success": "#53E6BD",
        "brief": "#43B9FF",
        "important": "#FFB454",
        "warning": "#FF9D57",
        "error": "#FF6678",
    }
    SPEEDS = {
        "idle": 0.42,
        "listening": 0.92,
        "thinking": 1.28,
        "acting": 1.72,
        "speaking": 0.82,
        "success": 0.58,
        "brief": 0.48,
        "important": 0.74,
        "warning": 1.05,
        "error": 0.45,
    }
    ACCESSIBLE = {
        "idle": "Jarvis jest gotowy",
        "listening": "Jarvis słucha",
        "thinking": "Jarvis analizuje",
        "acting": "Jarvis wykonuje zadanie",
        "speaking": "Jarvis odpowiada",
        "success": "Jarvis zakończył zadanie",
        "brief": "Jarvis pokazuje brief dnia",
        "important": "Jarvis pokazuje ważną informację",
        "warning": "Jarvis czeka na decyzję",
        "error": "Jarvis wymaga uwagi",
    }
    INTENSITY = {
        "idle": 0.8,
        "listening": 1.0,
        "thinking": 0.94,
        "acting": 1.0,
        "speaking": 0.96,
        "success": 0.88,
        "brief": 0.8,
        "important": 0.92,
        "warning": 0.96,
        "error": 0.84,
    }
    ACTIVE_FRAME_INTERVAL_MS = 33
    IDLE_FRAME_INTERVAL_MS = 50
    IDLE_STATES = frozenset({"idle", "brief", "success"})

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
        if self._state in self.IDLE_STATES:
            return self.performance_profile.idle_frame_interval_ms
        return self.performance_profile.active_frame_interval_ms

    def _tick(self) -> None:
        speed = self.SPEEDS[self._state]
        self._angle += speed
        self._pulse += 0.038 * max(speed, 0.65)
        self._scan += 1.8 * max(speed, 0.65)
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
