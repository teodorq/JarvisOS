from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.gui.client_experience_window import ClientExperienceWindow
from app.gui.client_voice_mixin import ClientVoiceMixin


class _NoDiskController:
    @staticmethod
    def set_halo(*_args, **_kwargs) -> None:
        raise AssertionError("live UI state must not write to the runtime store")


class _Label:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, value: object) -> None:  # noqa: N802 - Qt-compatible fake
        self.value = str(value)


def test_client_event_updates_presenter_without_runtime_store_write() -> None:
    seen: list[object] = []
    window = SimpleNamespace(
        presenter=SimpleNamespace(
            apply_event=lambda event: seen.append(event) or dict(event),
        ),
        controller=_NoDiskController(),
    )

    ClientExperienceWindow._on_client_event(
        window,
        {"state": "acting", "message": "Działam"},
    )

    assert seen == [{"state": "acting", "message": "Działam"}]


def test_client_click_schedules_work_without_runtime_store_write() -> None:
    presenter = SimpleNamespace(busy=False, begin_command=lambda: None)
    window = SimpleNamespace(
        presenter=presenter,
        controller=_NoDiskController(),
        owner_window=SimpleNamespace(
            pending_thought=None,
            process_client_command=lambda _command: None,
        ),
        activity_label=_Label(),
    )

    with patch(
        "app.gui.client_experience_window.QTimer.singleShot"
    ) as schedule:
        ClientExperienceWindow._submit_text(window, "status asystenta")

    schedule.assert_called_once()


def test_voice_state_updates_presenter_without_runtime_store_write() -> None:
    label = _Label()
    presenter = SimpleNamespace(
        show=lambda *_args, **_kwargs: None,
        begin_command=lambda: None,
    )
    voice = SimpleNamespace(
        manual_active=False,
        listen_once=lambda: True,
    )
    window = SimpleNamespace(
        owner_window=SimpleNamespace(voice=voice),
        presenter=presenter,
        controller=_NoDiskController(),
        listen_button=label,
        state_label=_Label(),
        message_label=_Label(),
        activity_label=_Label(),
    )

    ClientVoiceMixin._listen_hint(window)
    ClientVoiceMixin.handle_voice_state(window, "recognized")

    assert label.value == "MÓW"
