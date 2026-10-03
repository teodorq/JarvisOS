from __future__ import annotations

import subprocess
import sys
from unittest.mock import Mock

from app.voice.lazy_listener import LazyVoiceListener


def test_proxy_construction_does_not_import_audio_stack() -> None:
    code = (
        "import sys; "
        "from app.voice.lazy_listener import LazyVoiceListener; "
        "voice=LazyVoiceListener(settings={'continuous_mode': False}); "
        "assert not voice.loaded; "
        "assert 'app.voice.voice_listener' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_stop_does_not_load_unused_voice_runtime() -> None:
    factory = Mock()
    voice = LazyVoiceListener(factory=factory)

    voice.stop()

    factory.assert_not_called()
    assert not voice.loaded


def test_first_voice_action_loads_once_and_forwards_calls() -> None:
    listener = Mock()
    listener.say.return_value = True
    factory = Mock(return_value=listener)
    voice = LazyVoiceListener(
        on_text=Mock(), settings={"language": "pl-PL"}, factory=factory,
    )

    assert voice.say("Gotowe")
    assert voice.say("Działam")

    factory.assert_called_once()
    assert voice.loaded
    assert listener.say.call_count == 2


def test_continuous_mode_is_visible_without_loading_listener() -> None:
    voice = LazyVoiceListener(settings={"continuous_mode": True})

    assert voice.continuous_mode
    assert not voice.loaded
