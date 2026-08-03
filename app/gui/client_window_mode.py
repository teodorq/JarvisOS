from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from app.gui.halo_widget import HaloWidget


class FloatingJarvisEye(QWidget):
    """Małe, pływające oko pokazywane podczas wykonywania zadania."""

    restore_requested = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setObjectName("FloatingJarvisEye")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(164, 164)
        self.setToolTip("JARVIS pracuje. Kliknij, aby wrócić do rozmowy.")
        self.setStyleSheet(
            "QWidget#FloatingJarvisEye {"
            "background-color: rgba(2, 10, 19, 232);"
            "border: 1px solid rgba(74, 207, 255, 150);"
            "border-radius: 81px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        self.halo = HaloWidget()
        self.halo.set_animation_active(False)
        self.halo.setFixedSize(150, 150)
        layout.addWidget(self.halo)
        self._press_global: QPoint | None = None
        self._press_window: QPoint | None = None

    def set_state(self, state: object, progress: object) -> None:
        self.halo.set_state(state, progress)
        color = HaloWidget.COLORS[self.halo.state]
        self.setStyleSheet(
            "QWidget#FloatingJarvisEye {"
            "background-color: rgba(2, 10, 19, 232);"
            f"border: 1px solid {color};"
            "border-radius: 81px; }"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_window = self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._press_global is not None and self._press_window is not None:
            self.move(
                self._press_window
                + event.globalPosition().toPoint()
                - self._press_global
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and self._press_global is not None:
            moved = (
                event.globalPosition().toPoint() - self._press_global
            ).manhattanLength()
            self._press_global = None
            self._press_window = None
            if moved < 7:
                self.restore_requested.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ClientWindowModeRuntime(QObject):
    """Przełącza pełną rozmowę na małe oko na czas pracy JARVISA."""

    WORKING_STATES = {"thinking", "acting"}

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.eye = FloatingJarvisEye()
        self.eye.restore_requested.connect(self._restore_manually)
        self._working = False
        self._keep_conversation_open = False
        self._pupil_session = False
        self._transition_generation = 0
        self._speech_generation = 0
        self._speech_active = False

        self._main_eye_size = 0
    @property
    def compact(self) -> bool:
        return self.eye.isVisible()

    def show_conversation(self) -> None:
        self._working = False
        self._keep_conversation_open = False
        self._pupil_session = False
        self.window.halo.set_animation_active(True)
        self._transition_generation += 1
        generation = self._transition_generation
        self._size_main_eye()
        status = getattr(self.window, "stable_label", None)
        if status is not None:
            status.setText("JARVIS DOSTĘPNY")
        if self.window.isFullScreen():
            self.window.show()
        else:
            self.window.showFullScreen()
        self.window.raise_()
        QTimer.singleShot(
            90,
            lambda token=generation: self._hide_eye_after_restore(token),
        )

    def update_state(
        self, state: object, progress: object = 0, view_mode: object = ""
    ) -> None:
        value = str(state or "idle").casefold()
        self.eye.set_state(value, progress)
        requested = str(view_mode or "").casefold() == "pupil"
        if requested:
            self._pupil_session = True
            self._working = value in self.WORKING_STATES
            self._keep_conversation_open = False
            if self.window.isVisible() or self.eye.isVisible():
                self.show_working()
            return
        if self._pupil_session:
            self._working = value in self.WORKING_STATES
            return
        self._working = False
        if self.eye.isVisible() or not self.window.isVisible():
            self.show_conversation()

    def begin_speaking(self, tts: Any) -> None:
        if not (self.eye.isVisible() or self.window.isVisible()):
            return
        self._speech_generation += 1
        token = self._speech_generation
        self._speech_active = True
        self.eye.set_state("speaking", 100)
        self.window.halo.set_state("speaking", 100)
        QTimer.singleShot(100, lambda: self._poll_speaking(token, tts, 0))

    def settle_success(self) -> None:
        if self._speech_active:
            return
        self.eye.set_state("idle", 0)
        self.window.halo.set_state("idle", 0)

    def _poll_speaking(self, token: int, tts: Any, attempts: int) -> None:
        if token != self._speech_generation:
            return
        busy = bool(getattr(tts, "busy", False))
        if busy or attempts < 2:
            QTimer.singleShot(
                100,
                lambda: self._poll_speaking(token, tts, attempts + 1),
            )
            return
        self._speech_active = False
        if self._pupil_session and self.eye.isVisible():
            self.eye.set_state("idle", 0)
        else:
            self.window.halo.set_state("idle", 0)

    def show_working(self) -> None:
        self._working = True
        self._pupil_session = True
        self._transition_generation += 1
        generation = self._transition_generation
        self.eye.halo.set_animation_active(True)
        self._place_eye()
        self.eye.show()
        self.eye.raise_()
        status = getattr(self.window, "stable_label", None)
        if status is not None:
            status.setText("JARVIS DZIAŁA W TLE")
        self._hide_main_after_eye(generation)

    def leave(self) -> None:
        self._working = False
        self._keep_conversation_open = False
        self._pupil_session = False
        self._transition_generation += 1
        self.eye.hide()
        self.eye.halo.set_animation_active(False)
        self.window.halo.set_animation_active(False)

    def close(self) -> None:
        self._working = False
        self._keep_conversation_open = False
        self._pupil_session = False
        self._transition_generation += 1
        self.eye.halo.set_animation_active(False)
        self.window.halo.set_animation_active(False)
        self.eye.close()

    def _size_main_eye(self) -> None:
        screen = self.window.screen() or QApplication.primaryScreen()
        height = screen.availableGeometry().height() if screen else 900
        size = max(420, min(860, int(height * 0.60)))
        if size == self._main_eye_size:
            return
        self.window.halo.setMinimumSize(size, size)
        self.window.halo.setMaximumSize(size + 36, size + 36)
        self._main_eye_size = size

    def _hide_main_after_eye(self, generation: int) -> None:
        if (
            generation != self._transition_generation
            or not self._pupil_session
            or self._keep_conversation_open
            or not self.eye.isVisible()
        ):
            return
        self.window.halo.set_animation_active(False)
        self.window.hide()

    def _hide_eye_after_restore(self, generation: int) -> None:
        if generation != self._transition_generation:
            return
        self.eye.hide()
        self.eye.halo.set_animation_active(False)

    def _restore_manually(self) -> None:
        self._working = False
        self._keep_conversation_open = True
        self._pupil_session = False
        self._transition_generation += 1
        self.window.halo.set_animation_active(True)
        self._size_main_eye()
        if self.window.isFullScreen():
            self.window.show()
        else:
            self.window.showFullScreen()
        self.window.raise_()
        status = getattr(self.window, "stable_label", None)
        if status is not None:
            status.setText("JARVIS DOSTĘPNY")
        self.eye.hide()
        self.eye.halo.set_animation_active(False)

    def _place_eye(self) -> None:
        screen = self.window.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        margin = 26
        self.eye.move(
            area.right() - self.eye.width() - margin,
            area.bottom() - self.eye.height() - margin,
        )


__all__ = ["ClientWindowModeRuntime", "FloatingJarvisEye"]
