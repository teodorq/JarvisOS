from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.gui.client_forex_activity import ClientForexActivityRuntime
from app.gui.main_window_runtime import _show_forex_paper_activity


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback


class _Timer:
    single_shot = None

    def __init__(self, _parent) -> None:
        self.timeout = _Signal()
        self.active = False
        self.interval = 0

    def setInterval(self, value: int) -> None:  # noqa: N802 - Qt API
        self.interval = value

    def isActive(self) -> bool:  # noqa: N802 - Qt API
        return self.active

    def start(self) -> None:
        self.active = True

    @classmethod
    def singleShot(cls, delay: int, callback) -> None:  # noqa: N802 - Qt API
        cls.single_shot = (delay, callback)


def test_client_runtime_arms_once_and_delivers_through_idle_policy() -> None:
    event = {"state": "important", "message": "Forex PAPER"}
    feed = SimpleNamespace(poll=Mock(return_value=event))
    safe = SimpleNamespace(deliver=Mock())
    window = SimpleNamespace(
        owner_window=SimpleNamespace(
            assistant=SimpleNamespace(
                trading=SimpleNamespace(forex_activity=feed)
            )
        ),
        _safe_proactivity_runtime=Mock(return_value=safe),
    )

    with patch("app.gui.client_forex_activity.QTimer", _Timer):
        runtime = ClientForexActivityRuntime(window)
        runtime.arm()
        runtime.arm()
        runtime.poll()

    assert runtime.timer.interval == 30_000
    assert _Timer.single_shot is not None
    safe.deliver.assert_called_once_with(
        event, priority=30, kind="forex_paper"
    )


def test_owner_runtime_displays_and_forwards_activity() -> None:
    event = {"state": "brief", "message": "Dane Forex PAPER są gotowe."}
    window = SimpleNamespace(
        assistant=SimpleNamespace(
            trading=SimpleNamespace(
                forex_activity=SimpleNamespace(poll=Mock(return_value=event))
            )
        ),
        _interface_ready=True,
        console_page=SimpleNamespace(append=Mock()),
        client_event_signal=SimpleNamespace(emit=Mock()),
    )

    _show_forex_paper_activity(window)

    window.console_page.append.assert_called_once_with(
        "Jarvis: Dane Forex PAPER są gotowe."
    )
    window.client_event_signal.emit.assert_called_once_with(event)
