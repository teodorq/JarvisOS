from __future__ import annotations

import time


def dispatch_voice_text(window, text: str) -> None:
    raw_value = str(text).strip()
    if not raw_value:
        return
    client = getattr(window, "client_window", None)
    if raw_value.casefold().startswith("[voice_state]"):
        state = raw_value.split("]", 1)[-1].strip()
        if client is not None and hasattr(client, "handle_voice_state"):
            client.handle_voice_state(state)
        return
    if raw_value.casefold().startswith("[voice_error]"):
        detail = raw_value.split("]", 1)[-1].strip()
        if client is not None and hasattr(client, "handle_voice_state"):
            client.handle_voice_state("error")
        window.console_page.append(f"Jarvis: Głos wymaga uwagi: {detail}")
        window.console_page.set_state("GŁOS WYMAGA UWAGI", "danger")
        print("Voice runtime diagnostic:", detail)
        return
    key = raw_value.casefold()
    now = time.monotonic()
    previous = getattr(window, "_last_voice_dispatch", ("", 0.0))
    if key == previous[0] and now - float(previous[1]) < 3.0:
        return
    window._last_voice_dispatch = (key, now)
    if client is not None and (
        client.isVisible()
        or client.controller.status().get("runtime", {}).get("mode") == "CLIENT"
    ):
        window.process_client_command(raw_value)
        return
    window.process_command(raw_value.casefold(), source="Ty głosem")
