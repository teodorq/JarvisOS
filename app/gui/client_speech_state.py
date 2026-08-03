from __future__ import annotations

from typing import Any


def speak_with_client_state(window: Any, text: object) -> None:
    """Queue speech and mirror its real lifecycle on the active client orb."""
    voice = getattr(window, "voice", None)
    if voice is None:
        return
    try:
        accepted = voice.say(str(text or ""))
        if accepted is False:
            return
        client = getattr(window, "client_window", None)
        mode = getattr(client, "window_mode", None)
        tts = getattr(voice, "tts", None)
        if mode is not None and tts is not None:
            mode.begin_speaking(tts)
    except Exception as error:
        print("Voice output error:", error)


__all__ = ["speak_with_client_state"]
