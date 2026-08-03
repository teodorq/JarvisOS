from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar

from app.core.user_text import naturalize_user_text
from app.gui.client_sound_theme import ClientSoundTheme
from app.jarvis_experience.isolation import ClientIsolationPolicy


class ClientStatePresenter(QObject):
    """Keeps all public client states consistent and free of technical data."""

    LABELS = {
        "idle": "JESTEM GOTOWY",
        "listening": "SŁUCHAM",
        "thinking": "ANALIZUJĘ",
        "acting": "DZIAŁAM",
        "success": "GOTOWE",
        "brief": "BRIEF DNIA",
        "important": "WAŻNE",
        "warning": "POTRZEBUJĘ DECYZJI",
        "error": "WYMAGANA UWAGA",
    }
    ACTIVITY = {
        "idle": "Gotowy do działania.",
        "listening": "Nasłuchuję Twojego polecenia…",
        "thinking": "Rozumiem cel i wybieram najlepszy sposób działania…",
        "acting": "Wykonuję zadanie i sprawdzam rezultat…",
        "success": "Zadanie zakończone.",
        "brief": "Najważniejsze informacje na dziś.",
        "important": "Sprawdź tę ważną informację.",
        "warning": "Czekam na Twoją decyzję.",
        "error": "Nie udało się zakończyć zadania.",
    }
    ACTIVE = {"thinking", "acting", "warning"}

    def __init__(
        self,
        parent: QObject,
        halo: Any,
        state_label: QLabel,
        message_label: QLabel,
        activity_label: QLabel,
        activity_progress: QProgressBar,
        confirm_frame: QFrame,
    ) -> None:
        super().__init__(parent)
        self.halo = halo
        self.state_label = state_label
        self.message_label = message_label
        self.activity_label = activity_label
        self.activity_progress = activity_progress
        self.confirm_frame = confirm_frame
        self._state = "idle"
        self._settle_generation = 0
        controller = getattr(parent, "controller", None)
        project_root = getattr(controller, "project_root", None)
        self.sound_theme = ClientSoundTheme(self, project_root)
        QTimer.singleShot(220, self.sound_theme.startup)

    @property
    def state(self) -> str:
        return self._state

    @property
    def busy(self) -> bool:
        return self._state in self.ACTIVE

    def begin_command(self) -> None:
        self.show(
            "thinking",
            "Analizuję polecenie…",
            progress=8,
        )

    def listen(self) -> None:
        self.show(
            "listening",
            "Powiedz „Jarvis”, a potem swoje polecenie.",
            progress=0,
        )

    def apply_event(self, raw_event: object) -> dict[str, Any]:
        payload = raw_event if isinstance(raw_event, dict) else {}
        event = ClientIsolationPolicy.sanitize_event(dict(payload))
        self.show(
            event.get("state", "idle"),
            str(event.get("message", "")),
            progress=event.get("progress", 0),
            requires_confirmation=bool(
                event.get("requires_confirmation", False)
            ),
            view_mode=str(event.get("view_mode", "")),
        )
        return event

    def show(
        self,
        state: object,
        message: object,
        *,
        progress: object = 0,
        requires_confirmation: bool = False,
        view_mode: str = "",
    ) -> None:
        value = str(state or "idle").lower()
        if value not in self.LABELS:
            value = "acting"
        try:
            percent = max(0, min(100, int(progress)))
        except (TypeError, ValueError):
            percent = 0

        self._state = value
        self._settle_generation += 1
        generation = self._settle_generation
        self.halo.set_state(value, percent)
        self.state_label.setText(self.LABELS[value])
        self.sound_theme.play(value)
        self.message_label.setText(naturalize_user_text(
            message or self.ACTIVITY[value]
        ))
        self.activity_label.setText(self.ACTIVITY[value])
        self.confirm_frame.setVisible(requires_confirmation)
        self._update_progress(value, percent)
        window_mode = getattr(self.parent(), "window_mode", None)
        if window_mode is not None:
            window_mode.update_state(value, percent, view_mode)

        if value == "success":
            QTimer.singleShot(
                1900,
                lambda token=generation: self._settle_halo(token),
            )

    def reset_idle(self, message: str = "Powiedz lub wpisz, czego potrzebujesz.") -> None:
        self.show("idle", message, progress=0)

    def _update_progress(self, state: str, percent: int) -> None:
        visible = state in self.ACTIVE
        self.activity_progress.setVisible(visible)
        if not visible:
            self.activity_progress.setRange(0, 100)
            self.activity_progress.setValue(100 if state == "success" else 0)
            return
        if percent <= 0 and state in {"thinking", "acting"}:
            self.activity_progress.setRange(0, 0)
            self.activity_progress.setFormat("")
            return
        self.activity_progress.setRange(0, 100)
        self.activity_progress.setValue(percent)
        self.activity_progress.setFormat("%p%")

    def _settle_halo(self, generation: int) -> None:
        if generation != self._settle_generation or self._state != "success":
            return
        window_mode = getattr(self.parent(), "window_mode", None)
        if window_mode is not None:
            window_mode.settle_success()
        else:
            self.halo.set_state("idle", 0)
